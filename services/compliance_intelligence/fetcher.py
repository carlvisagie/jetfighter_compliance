"""Lawful HTTP fetcher for public compliance sources."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from . import snapshots
from .schemas import FetchResult, SourceRecord
from . import telemetry

DEFAULT_UA = "KeepYourContracts-ComplianceIntel/1.0 (+https://keepyourcontracts.com; compliance monitoring)"
TIMEOUT = 30.0
MAX_RETRIES = 2


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_source(source: SourceRecord, *, client: Optional[httpx.Client] = None) -> FetchResult:
    """Fetch one source; never raises."""
    telemetry.emit("fetch_started", metadata={"source_id": source.source_id})
    headers = {
        "User-Agent": source.user_agent or DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified

    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            if client is not None:
                resp = client.get(source.url, headers=headers, timeout=TIMEOUT, follow_redirects=True)
            else:
                with httpx.Client(follow_redirects=True) as c:
                    resp = c.get(source.url, headers=headers, timeout=TIMEOUT)
            fetched = _utc()
            if resp.status_code == 304:
                telemetry.emit(
                    "fetch_completed",
                    metadata={"source_id": source.source_id, "not_modified": True},
                )
                return FetchResult(
                    source_id=source.source_id,
                    ok=True,
                    status_code=304,
                    fetched_at_utc=fetched,
                    not_modified=True,
                    etag=source.etag,
                )
            if resp.status_code >= 400:
                telemetry.emit(
                    "fetch_failed",
                    success=False,
                    severity="warning",
                    message=f"HTTP {resp.status_code}",
                    metadata={"source_id": source.source_id},
                )
                return FetchResult(
                    source_id=source.source_id,
                    ok=False,
                    status_code=resp.status_code,
                    fetched_at_utc=fetched,
                    error=f"http_{resp.status_code}",
                )
            body = resp.text or ""
            etag = resp.headers.get("etag", "") or source.etag
            last_mod = resp.headers.get("last-modified", "") or source.last_modified
            result = snapshots.save_snapshot(
                source.source_id,
                body=body,
                status_code=resp.status_code,
                fetched_at_utc=fetched,
                etag=etag,
            )
            result.etag = etag
            result.last_modified = last_mod
            telemetry.emit(
                "fetch_completed",
                metadata={"source_id": source.source_id, "sha256": result.sha256[:16]},
            )
            return result
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * (attempt + 1))
    telemetry.emit(
        "fetch_failed",
        success=False,
        severity="warning",
        message=last_err,
        metadata={"source_id": source.source_id},
    )
    return FetchResult(
        source_id=source.source_id,
        ok=False,
        fetched_at_utc=_utc(),
        error=last_err or "fetch_failed",
    )

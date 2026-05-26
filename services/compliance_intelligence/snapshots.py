"""Append-only compliance source snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import FetchResult


def _root() -> Path:
    from ..config import DATA

    d = DATA / "compliance_intelligence" / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_content(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t[:500_000]


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_content(text).encode("utf-8", errors="replace")).hexdigest()


def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]{1,200})</title>", html or "", re.I)
    return (m.group(1).strip() if m else "")[:200]


def excerpt(text: str, limit: int = 1200) -> str:
    t = normalize_content(re.sub(r"<[^>]+>", " ", text))
    if len(t) > limit:
        return t[: limit - 3] + "..."
    return t


def save_snapshot(
    source_id: str,
    *,
    body: str,
    status_code: int,
    fetched_at_utc: str,
    etag: str = "",
) -> FetchResult:
    root = _root() / source_id
    root.mkdir(parents=True, exist_ok=True)
    sha = content_hash(body)
    fname = f"{fetched_at_utc.replace(':', '').replace('-', '')}_{sha[:12]}.html"
    path = root / fname
    path.write_text(body[:2_000_000], encoding="utf-8", errors="replace")
    meta = {
        "source_id": source_id,
        "fetched_at_utc": fetched_at_utc,
        "status_code": status_code,
        "sha256": sha,
        "content_excerpt": excerpt(body),
        "snapshot_path": str(path),
        "title": extract_title(body),
        "etag": etag,
    }
    index = root / "index.jsonl"
    with index.open("a", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    return FetchResult(
        source_id=source_id,
        ok=True,
        status_code=status_code,
        fetched_at_utc=fetched_at_utc,
        sha256=sha,
        content_length=len(body),
        excerpt=meta["content_excerpt"],
        snapshot_path=str(path),
        etag=etag,
    )


def latest_snapshot_meta(source_id: str) -> Optional[Dict[str, Any]]:
    index = _root() / source_id / "index.jsonl"
    if not index.is_file():
        return None
    last = None
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    return last


def previous_snapshot_meta(source_id: str) -> Optional[Dict[str, Any]]:
    index = _root() / source_id / "index.jsonl"
    if not index.is_file():
        return None
    rows: List[Dict[str, Any]] = []
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if len(rows) < 2:
        return None
    return rows[-2]

"""Detect content changes between snapshots."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import ChangeRecord, FetchResult
from . import snapshots

PHRASE_WATCH = [
    "cmmc",
    "800-171",
    "800-53",
    "dfars",
    "cui",
    "itar",
    "digital product passport",
    "espr",
    "cybersecurity advisory",
    "nist",
]


def _root() -> Path:
    from ..config import DATA

    d = DATA / "compliance_intelligence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_change(record: ChangeRecord) -> None:
    path = _root() / "changes.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")


def load_changes(limit: int = 200) -> List[Dict[str, Any]]:
    path = _root() / "changes.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def _phrase_delta(old: str, new: str) -> List[str]:
    old_l = (old or "").lower()
    new_l = (new or "").lower()
    added = [p for p in PHRASE_WATCH if p in new_l and p not in old_l]
    return added[:8]


def detect_change(
    source_id: str,
    fetch: FetchResult,
    *,
    prior_hash: str = "",
    prior_title: str = "",
) -> Optional[ChangeRecord]:
    if fetch.not_modified:
        return None
    if not fetch.ok:
        if fetch.status_code in (404, 410):
            cid = f"CHG-{uuid.uuid4().hex[:12]}"
            rec = ChangeRecord(
                change_id=cid,
                source_id=source_id,
                change_type="removed_content",
                old_hash=prior_hash,
                new_hash="",
                diff_summary="Source returned not found — possible removal or URL change.",
                confidence=0.85,
                detected_at_utc=_utc(),
            )
            append_change(rec)
            return rec
        return None

    new_hash = fetch.sha256
    if not prior_hash:
        cid = f"CHG-{uuid.uuid4().hex[:12]}"
        rec = ChangeRecord(
            change_id=cid,
            source_id=source_id,
            change_type="new_page",
            new_hash=new_hash,
            diff_summary="First snapshot recorded for this source.",
            confidence=0.9,
            detected_at_utc=_utc(),
        )
        append_change(rec)
        return rec

    if new_hash == prior_hash:
        return None

    latest = snapshots.latest_snapshot_meta(source_id) or {}
    prev = snapshots.previous_snapshot_meta(source_id) or {}
    title_new = latest.get("title", "")
    title_old = prev.get("title", prior_title)
    change_type = "changed_content"
    summary_parts = ["Content hash changed since last check."]
    if title_new and title_old and title_new != title_old:
        change_type = "title_change"
        summary_parts.append(f"Title changed: {title_old!r} → {title_new!r}")
    phrases = _phrase_delta(prev.get("content_excerpt", ""), latest.get("content_excerpt", ""))
    if phrases:
        change_type = "phrase_change"
        summary_parts.append("New watch phrases: " + ", ".join(phrases))

    cid = f"CHG-{uuid.uuid4().hex[:12]}"
    rec = ChangeRecord(
        change_id=cid,
        source_id=source_id,
        change_type=change_type,
        old_hash=prior_hash,
        new_hash=new_hash,
        diff_summary=" ".join(summary_parts)[:500],
        confidence=0.82,
        detected_at_utc=_utc(),
        title_old=title_old,
        title_new=title_new,
    )
    append_change(rec)
    return rec

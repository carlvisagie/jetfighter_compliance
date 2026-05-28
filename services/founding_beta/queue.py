"""Founding Beta operator review queue — triage without heavy imports."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..lazy_io import iter_jsonl_lines

from .classification import (
    DOC_UNKNOWN,
    classify_intake,
    load_classification,
)
from . import intake as _intake_mod
from .intake import _intake_dir, _load_intake

QUEUE_BACKLOG_PRESSURE = 5
URGENT_PRESSURE = 1


def _risk_score(*, urgent: bool, missing: List[str], file_count: int, review_status: str) -> float:
    score = 0.2
    if urgent:
        score += 0.35
    score += min(0.25, len(missing) * 0.08)
    if file_count <= 0:
        score += 0.2
    elif file_count == 1:
        score += 0.08
    if review_status in ("needs_info", "pending_review"):
        score += 0.1
    if review_status == "high_value":
        score = max(score, 0.55)
    return round(min(1.0, score), 3)


def _queue_row(intake_id: str) -> Optional[Dict[str, Any]]:
    try:
        rec = _load_intake(intake_id)
    except Exception:
        return None

    clf = load_classification(intake_id)
    if not clf and (rec.get("files") or rec.get("file_count")):
        try:
            clf = classify_intake(intake_id)
        except Exception:
            clf = {}

    clf = clf or {}
    files = rec.get("files") or []
    ext_types = sorted({f.get("ext") or "?" for f in files})
    file_count = int(rec.get("file_count") or len(files))
    total_bytes = int(rec.get("total_bytes") or sum(int(f.get("size") or 0) for f in files))
    review_status = str(rec.get("review_status") or rec.get("status") or "pending_review")
    missing = list(clf.get("missing_items") or [])
    confidence = float(clf.get("confidence_score") or 0.35)
    primary = str(clf.get("primary_category") or DOC_UNKNOWN)

    return {
        "intake_id": intake_id,
        "created_utc": rec.get("created_at_utc") or rec.get("created_utc"),
        "company": rec.get("company") or "",
        "contact": rec.get("email") or rec.get("phone") or "",
        "file_count": file_count,
        "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        "file_types": ext_types,
        "urgent_flag": bool(rec.get("urgent")),
        "deadline": rec.get("deadline") or "",
        "review_status": review_status,
        "risk_score": _risk_score(
            urgent=bool(rec.get("urgent")),
            missing=missing,
            file_count=file_count,
            review_status=review_status,
        ),
        "confidence_score": confidence,
        "missing_items": missing,
        "suggested_next_action": clf.get("suggested_next_action")
        or "Review uploaded paperwork",
        "primary_category": primary,
        "classified_file_types": list(clf.get("file_types") or []),
        "context_preview": (rec.get("context") or "")[:160],
    }


def _created_ts(row: Dict[str, Any]) -> float:
    from datetime import datetime, timezone

    raw = str(row.get("created_utc") or "")
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0.0


def _sort_key(row: Dict[str, Any]) -> tuple:
    return (
        0 if row.get("urgent_flag") else 1,
        -_created_ts(row),
        -float(row.get("confidence_score") or 0),
    )


def get_operator_review_queue(*, limit: int = 40, include_archived: bool = False) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for idx in iter_jsonl_lines(_intake_mod.INDEX_JSONL, tail_lines=max(limit * 3, 120)):
        iid = idx.get("intake_id")
        if not iid or iid in seen:
            continue
        seen.add(str(iid))
        item = _queue_row(str(iid))
        if not item:
            continue
        if not include_archived and item.get("review_status") == "archived":
            continue
        rows.append(item)

    root = _intake_mod.INTAKES_ROOT
    if root.is_dir():
        for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime if p.is_dir() else 0, reverse=True):
            if not path.is_dir() or not path.name.startswith("FB-"):
                continue
            if path.name in seen:
                continue
            item = _queue_row(path.name)
            if item:
                rows.append(item)
                seen.add(path.name)

    rows.sort(key=_sort_key)
    rows = rows[:limit]

    pending = [r for r in rows if r.get("review_status") in ("pending_review", "needs_info")]
    urgent = [r for r in rows if r.get("urgent_flag")]
    return {
        "ok": True,
        "queue": rows,
        "queue_depth": len(pending),
        "urgent_count": len(urgent),
        "backlog_pressure": len(pending) >= QUEUE_BACKLOG_PRESSURE,
        "uploads_per_hour_estimate": _uploads_per_hour_estimate(),
    }


def _uploads_per_hour_estimate() -> float:
    """Rough rate from index tail — bounded scan only."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    count = 0
    for row in iter_jsonl_lines(_intake_mod.INDEX_JSONL, tail_lines=80):
        ts = row.get("created_at_utc") or ""
        try:
            t = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if (now - t).total_seconds() <= 3600:
            count += 1
    return float(count)


def queue_flow_metrics() -> Dict[str, Any]:
    """Extended metrics for COTE upload + learning nodes."""
    q = get_operator_review_queue(limit=50)
    depth = int(q.get("queue_depth") or 0)
    urgent = int(q.get("urgent_count") or 0)
    uph = float(q.get("uploads_per_hour_estimate") or 0)
    pressure = min(1.0, depth / float(QUEUE_BACKLOG_PRESSURE) + urgent / 3.0)
    activity = min(1.0, uph / 5.0 + depth / 20.0)
    glow = min(1.0, activity * 0.6 + (0.25 if depth else 0))
    return {
        "queue_depth": depth,
        "urgent_count": urgent,
        "uploads_per_hour": uph,
        "backlog_pressure": bool(q.get("backlog_pressure")),
        "pressure": pressure,
        "activity": activity,
        "glow_intensity": glow,
        "pending_review": depth,
    }

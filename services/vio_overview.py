"""VIO 2.0 — aggregate company awareness data for the visual timeline interface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── state priority (lower = more urgent) ──────────────────────────────────────
_STATE_PRIORITY = {
    "error": 0,
    "stuck": 1,
    "gap": 2,
    "waiting": 3,
    "analyzing": 4,
    "active": 5,
    "payment_pending": 6,
    "new": 7,
    "complete": 8,
}


def _ts_age_hours(utc_str: str) -> float:
    """Return how many hours ago a UTC ISO string was."""
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 0.0


def _initials(name: str) -> str:
    parts = (name or "?").split()
    return "".join(p[0].upper() for p in parts[:2]) or "?"


def _calc_state(row: Dict, ei: Dict) -> str:
    review_status = row.get("review_status", "")
    files_up = ei.get("files_uploaded", 0)
    files_an = ei.get("files_analyzed", 0)
    gaps = ei.get("missing_item_count", 0)
    failures = ei.get("extraction_failures", 0)
    pending = ei.get("pending_analysis", 0)
    confirm_needed = len(ei.get("confirmation_needed") or [])

    if review_status == "archived":
        return "complete"
    if failures > 0:
        return "error"
    if review_status in ("approved", "payment_sent"):
        return "payment_pending"
    if confirm_needed:
        return "waiting"
    if files_up > 0 and gaps > 0:
        return "gap"
    if files_up > 0 and (files_an < files_up or pending > 0):
        return "analyzing"
    if files_up > 0:
        return "active"
    # Stale pending_review with no uploads → stuck
    age = _ts_age_hours(row.get("created_utc") or row.get("submitted_utc") or "")
    if age > 48 and review_status == "pending_review":
        return "stuck"
    return "new"


def _build_timeline(row: Dict, ei: Dict, state: str) -> List[Dict]:
    segments: List[Dict] = []

    # 1. Intake always present
    segments.append({
        "type": "intake",
        "status": "complete",
        "label": "Intake received",
        "utc": row.get("created_utc") or row.get("submitted_utc") or "",
        "detail": {
            "company": row.get("company_name") or row.get("company"),
            "email": row.get("contact_email") or row.get("email"),
            "review_status": row.get("review_status"),
        },
    })

    # 2. Documents uploaded
    files_up = ei.get("files_uploaded", 0)
    if files_up:
        doc_types = ei.get("document_types") or []
        up_status = "complete" if ei.get("files_analyzed", 0) > 0 else "active"
        if ei.get("extraction_failures", 0):
            up_status = "error"
        segments.append({
            "type": "upload",
            "status": up_status,
            "label": f"{files_up} file{'s' if files_up != 1 else ''} uploaded",
            "detail": {
                "files_uploaded": files_up,
                "files_analyzed": ei.get("files_analyzed", 0),
                "pending": ei.get("pending_analysis", 0),
                "failures": ei.get("extraction_failures", 0),
                "doc_types": [
                    {"file": d.get("file"), "type": d.get("type"), "confidence": d.get("confidence")}
                    for d in doc_types[:10]
                ],
            },
        })

    # 3. Analysis complete
    if ei.get("files_analyzed", 0):
        profile = ei.get("profile") or {}
        segments.append({
            "type": "analysis",
            "status": "complete",
            "label": f"{ei['files_analyzed']} analyzed",
            "detail": {
                "entity_count": ei.get("entity_count", 0),
                "company_names": (profile.get("company_names") or [])[:3],
                "emails": (profile.get("emails") or [])[:3],
                "technologies": (profile.get("technologies") or [])[:5],
                "compliance_references": (profile.get("compliance_references") or [])[:5],
            },
        })

    # 4. Gaps
    gaps = ei.get("gaps") or []
    if gaps:
        high = [g for g in gaps if g.get("priority") == "high"]
        segments.append({
            "type": "gap",
            "status": "active" if state not in ("complete",) else "resolved",
            "label": f"{len(gaps)} gap{'s' if len(gaps) != 1 else ''} — {len(high)} high priority",
            "detail": {
                "gaps": [
                    {"id": g.get("gap_id"), "label": g.get("label"), "priority": g.get("priority")}
                    for g in gaps[:8]
                ],
            },
        })

    # 5. Customer confirmation needed
    confirm = ei.get("confirmation_needed") or []
    if confirm:
        segments.append({
            "type": "confirmation",
            "status": "waiting",
            "label": f"{len(confirm)} item{'s' if len(confirm) != 1 else ''} need confirmation",
            "detail": {
                "items": [
                    {"field": c.get("field"), "value": c.get("value"), "status": c.get("status")}
                    for c in confirm[:5]
                ],
            },
        })

    # 6. Payment
    if row.get("review_status") in ("approved", "payment_sent", "archived"):
        segments.append({
            "type": "payment",
            "status": "complete" if row.get("review_status") == "archived" else "active",
            "label": "Payment link dispatched",
            "detail": {"review_status": row.get("review_status")},
        })

    # 7. Extraction errors (inline warning node)
    if ei.get("extraction_failures", 0):
        segments.append({
            "type": "error",
            "status": "error",
            "label": f"{ei['extraction_failures']} extraction failure{'s' if ei['extraction_failures'] != 1 else ''}",
            "detail": {
                "unsupported": (ei.get("unsupported_files") or [])[:5],
            },
        })

    # 8. Complete
    if row.get("review_status") == "archived":
        segments.append({
            "type": "complete",
            "status": "complete",
            "label": "Engagement complete",
            "detail": {},
        })

    return segments


def _priority_score(state: str, created_utc: str) -> float:
    """Lower is more urgent — used for secondary sort within same state."""
    age = _ts_age_hours(created_utc)
    return _STATE_PRIORITY.get(state, 9) * 1000 - age


def _build_company_row(row: Dict, ei: Dict) -> Dict:
    pid = row.get("project_id") or row.get("intake_id") or ""
    name = row.get("company_name") or row.get("company") or "Unknown"
    state = _calc_state(row, ei)
    timeline = _build_timeline(row, ei, state)
    created = row.get("created_utc") or row.get("submitted_utc") or ""

    return {
        "project_id": pid,
        "company_name": name,
        "initials": _initials(name),
        "contact_email": row.get("contact_email") or row.get("email") or "",
        "created_utc": created,
        "age_hours": round(_ts_age_hours(created), 1),
        "review_status": row.get("review_status") or "",
        "state": state,
        "priority_score": _priority_score(state, created),
        "timeline": timeline,
        "quick_stats": {
            "files_uploaded": ei.get("files_uploaded", 0),
            "files_analyzed": ei.get("files_analyzed", 0),
            "gaps": ei.get("missing_item_count", 0),
            "failures": ei.get("extraction_failures", 0),
            "pending": ei.get("pending_analysis", 0),
            "confirmation_needed": len(ei.get("confirmation_needed") or []),
            "entity_count": ei.get("entity_count", 0),
        },
        "next_action": ((ei.get("next_actions") or [None])[0]),
        "ei_ok": ei.get("ok", False),
    }


def build_vio_overview(limit: int = 60) -> Dict:
    """Aggregate all company rows for VIO 2.0 rendering."""
    from services.intake.queue import get_operator_review_queue

    try:
        queue_data = get_operator_review_queue(limit=min(limit, 100), include_archived=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "companies": [], "organism_health": {}}

    rows = queue_data.get("queue") or []
    companies: List[Dict] = []

    for row in rows:
        pid = row.get("project_id") or row.get("intake_id") or ""
        ei: Dict = {}
        if pid:
            try:
                from services.evidence_intelligence import get_operator_evidence_intelligence
                ei = get_operator_evidence_intelligence(pid) or {}
            except Exception:
                ei = {}
        companies.append(_build_company_row(row, ei))

    companies.sort(key=lambda c: c["priority_score"])

    state_counts: Dict[str, int] = {}
    for c in companies:
        s = c["state"]
        state_counts[s] = state_counts.get(s, 0) + 1

    return {
        "ok": True,
        "companies": companies,
        "organism_health": {
            "total": len(companies),
            **state_counts,
        },
        "queue_depth": queue_data.get("queue_depth", 0),
        "urgent_count": queue_data.get("urgent_count", 0),
    }

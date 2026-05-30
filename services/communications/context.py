"""Contextual communications fetch — only when operator review is relevant."""
from __future__ import annotations

from typing import Any, Dict, List

from .delay import build_delay_report
from .search import search_communications

_RELEVANT_REASONS = frozenset(
    {
        "delay",
        "dispute",
        "missing_document",
        "customer_question",
        "escalation",
    }
)

_REASON_CHANNELS = {
    "delay": {"document_request", "customer_response", "email", "phone", "portal"},
    "dispute": {"email", "phone", "portal", "operator_note", "meeting_note"},
    "missing_document": {"document_request", "customer_response", "email"},
    "customer_question": {"email", "portal", "sms", "phone"},
    "escalation": {"email", "phone", "operator_note", "meeting_note", "portal"},
}


def get_contextual_communications(
    *,
    intake_id: str,
    reason: str = "",
    limit: int = 50,
) -> Dict[str, Any]:
    """Return communications only for relevant operator contexts (not full cockpit feed)."""
    iid = intake_id.strip()
    r = (reason or "").strip().lower()
    if not iid:
        return {"ok": False, "error": "intake_id required"}
    if r and r not in _RELEVANT_REASONS:
        return {"ok": False, "error": f"unsupported reason: {reason}"}

    all_rows = search_communications(intake_id=iid, limit=500).get("communications") or []
    if not r:
        filtered = [c for c in all_rows if str(c.get("delay_relevance") or "").lower() == "yes"]
    else:
        allowed = _REASON_CHANNELS.get(r, set())
        filtered = [
            c
            for c in all_rows
            if str(c.get("channel") or "").lower() in allowed
            or str(c.get("delay_relevance") or "").lower() == "yes"
            or (r == "missing_document" and str(c.get("channel") or "") == "document_request")
        ]

    cap = min(max(limit, 1), 200)
    if len(filtered) > cap:
        filtered = filtered[-cap:]

    delay_report = build_delay_report(intake_id=iid) if r in ("delay", "missing_document", "") else None

    return {
        "ok": True,
        "intake_id": iid,
        "reason": r or "relevant_only",
        "count": len(filtered),
        "communications": filtered,
        "delay_report": delay_report,
    }

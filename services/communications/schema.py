"""Communication record schema and validation."""
from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, Optional

DIRECTIONS: FrozenSet[str] = frozenset({"inbound", "outbound", "internal"})
DELAY_RELEVANCE: FrozenSet[str] = frozenset({"yes", "no", "unknown"})
DELAY_CATEGORIES: FrozenSet[str] = frozenset(
    {
        "missing_document",
        "client_response_pending",
        "scheduling",
        "approval",
        "payment",
        "escalation",
        "other",
    }
)
CHANNELS: FrozenSet[str] = frozenset(
    {
        "email",
        "phone",
        "voicemail",
        "sms",
        "portal",
        "operator_note",
        "ai_followup",
        "document_request",
        "customer_response",
        "meeting_note",
    }
)

_REQUIRED = frozenset({"intake_id", "direction", "channel", "timestamp", "sender", "recipient"})


def derive_company_id(*, company: str = "", email: str = "", intake_id: str = "") -> str:
    name = (company or "").strip().lower()
    if name:
        slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")[:80]
        if slug:
            return f"co-{slug}"
    em = (email or "").strip().lower()
    if "@" in em:
        domain = em.split("@", 1)[1]
        domain_slug = re.sub(r"[^a-z0-9]+", "-", domain).strip("-")[:80]
        if domain_slug:
            return f"co-{domain_slug}"
    iid = (intake_id or "").strip()
    if iid:
        return f"co-{iid[:12].lower()}"
    return "co-unknown"


def normalize_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    rec = dict(raw)
    for key in ("subject", "body", "delay_reason", "related_timeline_segment", "project_id", "delay_event_id"):
        if rec.get(key) is None:
            rec[key] = ""
    rec["related_document_ids"] = list(rec.get("related_document_ids") or [])
    rec["attachments"] = list(rec.get("attachments") or [])
    rec["delay_relevance"] = str(rec.get("delay_relevance") or "unknown").lower()
    if rec["delay_relevance"] not in DELAY_RELEVANCE:
        rec["delay_relevance"] = "unknown"
    rec["direction"] = str(rec.get("direction") or "").lower()
    rec["channel"] = str(rec.get("channel") or "").lower()
    return rec


def validate_record(rec: Dict[str, Any]) -> Optional[str]:
    for field in _REQUIRED:
        if not str(rec.get(field) or "").strip():
            return f"{field} required"
    if rec["direction"] not in DIRECTIONS:
        return f"invalid direction: {rec['direction']}"
    if rec["channel"] not in CHANNELS:
        return f"invalid channel: {rec['channel']}"
    if rec["delay_relevance"] not in DELAY_RELEVANCE:
        return f"invalid delay_relevance: {rec['delay_relevance']}"
    cat = str(rec.get("delay_category") or "").strip().lower()
    if cat and cat not in DELAY_CATEGORIES:
        return f"invalid delay_category: {cat}"
    return None

"""Delay attribution engine — cite communications as evidence for client-caused delays."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .ledger import load_communications_for_intake
from .search import search_communications

_OPENING_CHANNELS = frozenset({"document_request", "email", "phone", "voicemail", "sms", "portal", "ai_followup"})
_CLOSING_CHANNELS = frozenset({"customer_response"})


def _parse_utc(ts: str) -> Optional[datetime]:
    raw = (ts or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _fmt_short_date(ts: str) -> str:
    dt = _parse_utc(ts)
    if not dt:
        return (ts or "")[:10]
    return dt.strftime("%B %d").replace(" 0", " ")


def _delay_days(opened_at: str, closed_at: str) -> int:
    o = _parse_utc(opened_at)
    c = _parse_utc(closed_at)
    if not o or not c:
        return 0
    delta = c - o
    return max(0, delta.days)


def _opens_delay_segment(comm: Dict[str, Any]) -> bool:
    if str(comm.get("delay_relevance") or "").lower() == "no":
        return False
    channel = str(comm.get("channel") or "").lower()
    if channel == "document_request":
        return True
    if str(comm.get("delay_relevance") or "").lower() == "yes" and channel in _OPENING_CHANNELS:
        return bool(comm.get("delay_category") or comm.get("delay_reason") or comm.get("subject"))
    return False


def _closes_delay_segment(comm: Dict[str, Any]) -> bool:
    channel = str(comm.get("channel") or "").lower()
    if channel in _CLOSING_CHANNELS:
        return True
    if str(comm.get("delay_relevance") or "").lower() == "yes" and channel == "customer_response":
        return True
    return False


def _build_narrative(
    *,
    delay_days: int,
    reason: str,
    opened_at: str,
    closed_at: Optional[str],
) -> str:
    reason_text = reason.strip() or "client action pending"
    opened_label = _fmt_short_date(opened_at)
    if closed_at:
        closed_label = _fmt_short_date(closed_at)
        return (
            f"Client delay: {delay_days} days — {reason_text} on {opened_label}, "
            f"received {closed_label}."
        )
    return f"Client delay: open — {reason_text} since {opened_label}."


def build_delay_report(*, intake_id: str = "", project_id: str = "") -> Dict[str, Any]:
    """Build delay attributions with communication evidence citations."""
    iid = intake_id.strip()
    pid = project_id.strip()
    if iid:
        comms = load_communications_for_intake(iid, limit=2000)
    elif pid:
        comms = search_communications(project_id=pid, limit=2000).get("communications") or []
    else:
        return {"ok": False, "error": "intake_id or project_id required", "attributions": []}

    open_segments: List[Dict[str, Any]] = []
    attributions: List[Dict[str, Any]] = []

    for comm in comms:
        if _opens_delay_segment(comm):
            cid = str(comm.get("communication_id") or "")
            delay_event_id = str(comm.get("delay_event_id") or f"delay-{cid}")
            reason = (
                str(comm.get("delay_reason") or "").strip()
                or str(comm.get("subject") or "").strip()
                or str(comm.get("body") or "")[:120].strip()
            )
            segment = {
                "delay_event_id": delay_event_id,
                "intake_id": comm.get("intake_id"),
                "project_id": comm.get("project_id") or "",
                "opening_communication_id": cid,
                "closing_communication_id": None,
                "opened_at_utc": comm.get("timestamp"),
                "closed_at_utc": None,
                "delay_category": comm.get("delay_category") or "missing_document",
                "delay_reason": reason,
                "delay_relevance": comm.get("delay_relevance") or "yes",
                "evidence_communication_ids": [cid],
            }
            open_segments.append(segment)

        if _closes_delay_segment(comm):
            target_delay_id = str(comm.get("delay_event_id") or "").strip()
            closed = False
            for seg in reversed(open_segments):
                if seg.get("closed_at_utc"):
                    continue
                if target_delay_id and seg.get("delay_event_id") != target_delay_id:
                    continue
                seg["closed_at_utc"] = comm.get("timestamp")
                seg["closing_communication_id"] = str(comm.get("communication_id") or "")
                seg["evidence_communication_ids"].append(seg["closing_communication_id"])
                closed = True
                break
            if not closed and not target_delay_id:
                for seg in reversed(open_segments):
                    if not seg.get("closed_at_utc"):
                        seg["closed_at_utc"] = comm.get("timestamp")
                        seg["closing_communication_id"] = str(comm.get("communication_id") or "")
                        seg["evidence_communication_ids"].append(seg["closing_communication_id"])
                        break

    for seg in open_segments:
        if str(seg.get("delay_relevance") or "").lower() == "no":
            continue
        opened = str(seg.get("opened_at_utc") or "")
        closed = seg.get("closed_at_utc")
        days = _delay_days(opened, closed) if closed else _delay_days(opened, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        narrative = _build_narrative(
            delay_days=days,
            reason=str(seg.get("delay_reason") or ""),
            opened_at=opened,
            closed_at=closed,
        )
        attributions.append(
            {
                **seg,
                "delay_days": days,
                "narrative": narrative,
            }
        )

    return {
        "ok": True,
        "intake_id": iid or None,
        "project_id": pid or None,
        "attribution_count": len(attributions),
        "open_delay_count": sum(1 for a in attributions if not a.get("closed_at_utc")),
        "attributions": attributions,
    }

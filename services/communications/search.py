"""Search communications ledger by company, intake, document, delay, contact, date, channel."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .ledger import _load_all_rows
from .schema import derive_company_id


def _in_date_range(ts: str, date_from: Optional[str], date_to: Optional[str]) -> bool:
    if date_from and ts < date_from:
        return False
    if date_to and ts > date_to:
        return False
    return True


def search_communications(
    *,
    company_id: str = "",
    company: str = "",
    intake_id: str = "",
    project_id: str = "",
    document_id: str = "",
    delay_event_id: str = "",
    delay_relevance: str = "",
    contact: str = "",
    date_from: str = "",
    date_to: str = "",
    channel: str = "",
    limit: int = 200,
) -> Dict[str, Any]:
    rows = _load_all_rows()
    rows.sort(key=lambda r: str(r.get("timestamp") or ""))

    cid_filter = company_id.strip()
    if not cid_filter and company.strip():
        cid_filter = derive_company_id(company=company.strip())

    iid = intake_id.strip()
    pid = project_id.strip()
    doc = document_id.strip()
    delay_id = delay_event_id.strip()
    delay_rel = delay_relevance.strip().lower()
    contact_q = contact.strip().lower()
    ch = channel.strip().lower()
    df = date_from.strip()
    dt = date_to.strip()

    matched: List[Dict[str, Any]] = []
    for row in rows:
        if cid_filter and str(row.get("company_id") or "") != cid_filter:
            continue
        if iid and str(row.get("intake_id") or "") != iid:
            continue
        if pid and str(row.get("project_id") or "") != pid:
            continue
        if doc:
            docs = [str(x) for x in (row.get("related_document_ids") or [])]
            if doc not in docs:
                continue
        if delay_id and str(row.get("delay_event_id") or "") != delay_id:
            continue
        if delay_rel and str(row.get("delay_relevance") or "").lower() != delay_rel:
            continue
        if ch and str(row.get("channel") or "").lower() != ch:
            continue
        if contact_q:
            sender = str(row.get("sender") or "").lower()
            recipient = str(row.get("recipient") or "").lower()
            if contact_q not in sender and contact_q not in recipient:
                continue
        ts = str(row.get("timestamp") or "")
        if not _in_date_range(ts, df or None, dt or None):
            continue
        matched.append(row)

    cap = min(max(limit, 1), 2000)
    if len(matched) > cap:
        matched = matched[-cap:]

    return {
        "ok": True,
        "count": len(matched),
        "communications": matched,
    }

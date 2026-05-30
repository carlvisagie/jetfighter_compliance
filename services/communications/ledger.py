"""Append-only communications ledger — no silent deletion."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.intake.storage import load_intake_record

from .hashing import compute_record_hash
from .schema import derive_company_id, normalize_record, validate_record


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _data_root() -> Path:
    from services.intake.storage import _data_root as intake_data_root

    return intake_data_root()


def communications_root() -> Path:
    p = _data_root() / "communications"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ledger_path() -> Path:
    p = communications_root() / "communications_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_all_rows(*, tail_lines: int = 100000) -> List[Dict[str, Any]]:
    path = ledger_path()
    if not path.is_file():
        return []
    from services.lazy_io import iter_jsonl_lines

    return list(iter_jsonl_lines(path, max_bytes=50 * 1024 * 1024, tail_lines=tail_lines))


def _latest_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cid = str(row.get("communication_id") or "")
        if cid:
            by_id[cid] = row
    return by_id


def append_communication(
    payload: Dict[str, Any],
    *,
    recorded_by: str = "operator",
) -> Dict[str, Any]:
    """Append one communication event. Raises ValueError on validation failure."""
    rec = normalize_record(payload)
    err = validate_record(rec)
    if err:
        raise ValueError(err)

    intake_id = str(rec["intake_id"]).strip()
    company_id = str(rec.get("company_id") or "").strip()
    if not company_id:
        email = ""
        company = ""
        try:
            intake_rec = load_intake_record(intake_id, persist_recovery=False)
            email = str(intake_rec.get("email") or "")
            company = str(intake_rec.get("company") or "")
        except Exception:
            pass
        company_id = derive_company_id(company=company, email=email, intake_id=intake_id)
        rec["company_id"] = company_id
    else:
        rec["company_id"] = company_id

    if not rec.get("communication_id"):
        rec["communication_id"] = f"comm-{uuid.uuid4().hex[:12]}"

    if rec["channel"] == "document_request" and rec["delay_relevance"] == "yes":
        if not rec.get("delay_event_id"):
            rec["delay_event_id"] = f"delay-{rec['communication_id']}"

    rec["recorded_at_utc"] = _utc_now()
    rec["recorded_by"] = recorded_by
    rec["record_hash"] = compute_record_hash(rec)

    path = ledger_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def get_communication(communication_id: str) -> Optional[Dict[str, Any]]:
    cid = communication_id.strip()
    if not cid:
        return None
    for row in reversed(_load_all_rows()):
        if str(row.get("communication_id") or "") == cid:
            return row
    return None


def load_communications_for_intake(intake_id: str, *, limit: int = 500) -> List[Dict[str, Any]]:
    iid = intake_id.strip()
    rows = [r for r in _load_all_rows() if str(r.get("intake_id") or "") == iid]
    rows.sort(key=lambda r: str(r.get("timestamp") or ""))
    return rows[-limit:]

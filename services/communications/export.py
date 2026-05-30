"""Forensic export of communications ledger with chain-of-custody metadata."""
from __future__ import annotations

from typing import Any, Dict, List

from .delay import build_delay_report
from .hashing import verify_record_hash
from .reconcile import reconcile_communications_ledger
from .search import search_communications


def export_communications_forensic(
    *,
    intake_id: str = "",
    project_id: str = "",
    company_id: str = "",
    include_delay_report: bool = True,
) -> Dict[str, Any]:
    """Export communications with hash verification and optional delay attributions."""
    iid = intake_id.strip()
    pid = project_id.strip()
    cid = company_id.strip()
    if not iid and not pid and not cid:
        return {"ok": False, "error": "intake_id, project_id, or company_id required"}

    found = search_communications(
        intake_id=iid,
        project_id=pid,
        company_id=cid,
        limit=5000,
    )
    rows: List[Dict[str, Any]] = found.get("communications") or []

    exported: List[Dict[str, Any]] = []
    for row in rows:
        exported.append(
            {
                **row,
                "hash_verified": verify_record_hash(row),
                "chain_of_custody": {
                    "recorded_at_utc": row.get("recorded_at_utc"),
                    "recorded_by": row.get("recorded_by"),
                    "record_hash": row.get("record_hash"),
                },
            }
        )

    reconcile = reconcile_communications_ledger()
    delay_report = None
    if include_delay_report and iid:
        delay_report = build_delay_report(intake_id=iid)
    elif include_delay_report and pid:
        delay_report = build_delay_report(project_id=pid)

    hash_failures = sum(1 for r in exported if not r.get("hash_verified"))

    return {
        "ok": hash_failures == 0 and reconcile.get("ok", True),
        "intake_id": iid or None,
        "project_id": pid or None,
        "company_id": cid or None,
        "communication_count": len(exported),
        "hash_verified_count": len(exported) - hash_failures,
        "hash_failure_count": hash_failures,
        "ledger_reconcile": reconcile,
        "communications": exported,
        "delay_report": delay_report,
    }

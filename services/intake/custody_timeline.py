"""Custody timeline — merge transaction log, registry, audit, operator, kickoff events."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .evidence_registry import lookup_by_intake
from .retention import load_audit_receipt
from .storage import load_intake_record
from .transactions import load_transaction_log

_PHASE_TO_EVENT = {
    "upload_received": "upload_received",
    "files_persisted": "file_persisted",
    "hash_verified": "hash_verified",
    "audit_written": "audit_written",
    "intake_committed": "index_committed",
    "index_committed": "index_committed",
    "forensic_recovered": "forensic_recovered",
    "recovered_on_startup": "recovered_on_startup",
    "classification_complete": "classification_complete",
    "integrity_failure": "integrity_failure",
}


def build_custody_timeline(intake_id: str) -> Dict[str, Any]:
    """Ordered custody events for operator forensic review."""
    events: List[Dict[str, Any]] = []

    for row in load_transaction_log(intake_id, tail=500):
        phase = str(row.get("phase") or "")
        event_type = _PHASE_TO_EVENT.get(phase, phase)
        events.append(
            {
                "event": event_type,
                "at_utc": row.get("at_utc"),
                "source": "transaction_lifecycle",
                "phase": phase,
                "ok": row.get("ok", True),
                "metadata": row.get("metadata") or {},
            }
        )

    receipt = load_audit_receipt(intake_id)
    if receipt:
        events.append(
            {
                "event": "audit_written",
                "at_utc": receipt.get("created_utc"),
                "source": "audit_receipt",
                "metadata": {
                    "file_count": len(receipt.get("file_hashes") or {}),
                    "integrity_ok": receipt.get("integrity_ok"),
                },
            }
        )

    for reg in lookup_by_intake(intake_id):
        events.append(
            {
                "event": "evidence_registered",
                "at_utc": reg.get("registered_at_utc") or reg.get("received_timestamp"),
                "source": "evidence_registry",
                "metadata": {
                    "evidence_id": reg.get("evidence_id"),
                    "stored_filename": reg.get("stored_filename"),
                    "sha256": reg.get("sha256"),
                    "current_status": reg.get("current_status"),
                },
            }
        )
        if reg.get("verified_timestamp"):
            events.append(
                {
                    "event": "hash_verified",
                    "at_utc": reg.get("verified_timestamp"),
                    "source": "evidence_registry",
                    "metadata": {
                        "evidence_id": reg.get("evidence_id"),
                        "stored_filename": reg.get("stored_filename"),
                    },
                }
            )

    try:
        record = load_intake_record(intake_id, persist_recovery=False)
    except Exception:
        record = {}

    custody = record.get("upload_custody") or {}
    if custody.get("newest_upload_at_utc"):
        events.append(
            {
                "event": "upload_received",
                "at_utc": custody.get("newest_upload_at_utc"),
                "source": "upload_custody",
                "metadata": {
                    "submission_method": custody.get("submission_method"),
                    "upload_session_id": custody.get("upload_session_id"),
                },
            }
        )

    if record.get("operator_note") or record.get("review_status") not in (
        None,
        "",
        "pending_review",
        "received",
        "submitted",
        "new",
    ):
        events.append(
            {
                "event": "operator_reviewed",
                "at_utc": record.get("updated_at_utc"),
                "source": "intake_record",
                "metadata": {
                    "review_status": record.get("review_status"),
                    "operator_note": (record.get("operator_note") or "")[:200],
                },
            }
        )

    if record.get("project_id"):
        events.append(
            {
                "event": "project_created",
                "at_utc": record.get("updated_at_utc"),
                "source": "intake_record",
                "metadata": {"project_id": record.get("project_id")},
            }
        )

    def _sort_key(e: Dict[str, Any]) -> str:
        return str(e.get("at_utc") or "")

    events.sort(key=_sort_key)

    seen: set[tuple[str, str, str]] = set()
    deduped: List[Dict[str, Any]] = []
    for e in events:
        key = (str(e.get("event")), str(e.get("at_utc")), str(e.get("source")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    return {
        "ok": True,
        "intake_id": intake_id,
        "event_count": len(deduped),
        "events": deduped,
        "custody_status": record.get("custody_status"),
    }

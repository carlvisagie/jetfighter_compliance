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
    "evidence_intelligence_completed": "evidence_intelligence_completed",
    "evidence_intelligence_failed":    "evidence_intelligence_failed",
    "operator_action_approve_review":  "operator_approved",
    "operator_action_request_more_info": "operator_request_more_info",
    "operator_action_mark_high_value": "operator_mark_high_value",
    "operator_action_archive":         "operator_archived",
    "operator_payment_link_sent":      "payment_link_sent",
    "binder_exported":                 "binder_exported",
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

    try:
        from services.communications.search import search_communications
        from services.communications.delay import build_delay_report

        comm_rows = search_communications(intake_id=intake_id, limit=500).get("communications") or []
        for comm in comm_rows:
            events.append(
                {
                    "event": "communication",
                    "at_utc": comm.get("timestamp"),
                    "source": "communications_ledger",
                    "marker_type": "message",
                    "communication_id": comm.get("communication_id"),
                    "metadata": {
                        "channel": comm.get("channel"),
                        "direction": comm.get("direction"),
                        "subject": (comm.get("subject") or "")[:120],
                        "delay_relevance": comm.get("delay_relevance"),
                        "delay_category": comm.get("delay_category"),
                        "body_preview": (comm.get("body") or "")[:200],
                    },
                }
            )

        delay_report = build_delay_report(intake_id=intake_id)
        for attr in delay_report.get("attributions") or []:
            if attr.get("delay_relevance") == "no":
                continue
            events.append(
                {
                    "event": "client_delay_segment",
                    "at_utc": attr.get("opened_at_utc"),
                    "source": "delay_attribution",
                    "marker_type": "delay",
                    "delay_event_id": attr.get("delay_event_id"),
                    "metadata": {
                        "narrative": attr.get("narrative"),
                        "delay_days": attr.get("delay_days"),
                        "closed_at_utc": attr.get("closed_at_utc"),
                        "opening_communication_id": attr.get("opening_communication_id"),
                        "closing_communication_id": attr.get("closing_communication_id"),
                        "evidence_communication_ids": [
                            x
                            for x in [
                                attr.get("opening_communication_id"),
                                attr.get("closing_communication_id"),
                            ]
                            if x
                        ],
                    },
                }
            )
            if attr.get("closed_at_utc"):
                events.append(
                    {
                        "event": "client_delay_closed",
                        "at_utc": attr.get("closed_at_utc"),
                        "source": "delay_attribution",
                        "marker_type": "delay_end",
                        "delay_event_id": attr.get("delay_event_id"),
                        "metadata": {"narrative": attr.get("narrative")},
                    }
                )
    except Exception:
        pass

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

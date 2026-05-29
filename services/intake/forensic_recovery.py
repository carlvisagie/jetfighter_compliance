"""Forensic intake recovery — reconstruct metadata from disk + audit + transaction logs."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evidence_registry import (
    STATUS_RECOVERED,
    derive_evidence_registry_for_intake,
    lookup_by_intake,
    update_evidence_status,
)
from .retention import hash_uploads_on_disk, load_audit_receipt, require_upload_durability_verified
from .storage import (
    intake_dir,
    intake_json_path,
    latest_index_row,
    load_intake_record,
    normalize_intake_record,
)
from .transactions import PHASE_FORENSIC_RECOVERED, append_transaction_event, load_transaction_log

logger = logging.getLogger(__name__)


def recover_intake_forensic(intake_id: str) -> Dict[str, Any]:
    """
    Reconstruct intake visibility from disk + audit + transaction logs when
    index/queue/telemetry/operator record may be missing or incomplete.
    """
    from .intake import _apply_custody_status, _commit_intake_state
    from .integrity import (
        STATE_PERSISTED,
        build_integrity_report,
        merge_batch_lifecycle,
        new_lifecycle_entry,
    )
    from .reconcile import reconcile_intake

    idir = intake_dir(intake_id)
    if not idir.is_dir():
        return {"ok": False, "error": "intake_dir_missing", "intake_id": intake_id}

    uploads = idir / "uploads"
    disk_names = sorted(p.name for p in uploads.iterdir() if p.is_file()) if uploads.is_dir() else []
    if not disk_names:
        return {"ok": False, "error": "no_files_on_disk", "intake_id": intake_id}

    pre_reconcile = reconcile_intake(intake_id)
    audit = load_audit_receipt(intake_id)
    tx_log = load_transaction_log(intake_id, tail=200)

    try:
        record = load_intake_record(intake_id, persist_recovery=True)
    except Exception:
        record = normalize_intake_record({"intake_id": intake_id}, intake_id=intake_id)

    files_on_record = list(record.get("files") or [])
    known = {str(f.get("name")) for f in files_on_record}
    recovered_evidence: List[Dict[str, Any]] = []
    for name in disk_names:
        if name not in known:
            path = uploads / name
            entry = {
                "name": name,
                "original_name": name,
                "size": path.stat().st_size if path.is_file() else 0,
                "ext": Path(name).suffix.lower(),
                "recovered_from_disk": True,
            }
            files_on_record.append(entry)
            recovered_evidence.append(entry)
    record["files"] = files_on_record
    record["file_count"] = len(files_on_record)
    record["recovered_forensic"] = True

    lifecycle = [
        new_lifecycle_entry(str(f.get("original_name") or f.get("name") or ""), state=STATE_PERSISTED)
        for f in files_on_record
    ]
    for entry, f in zip(lifecycle, files_on_record):
        entry["stored_name"] = f.get("name")

    prior = list((record.get("upload_integrity") or {}).get("file_lifecycle") or [])
    merged = merge_batch_lifecycle(prior, lifecycle)
    custody = dict(record.get("upload_custody") or {})
    expected = int(
        custody.get("total_expected_count")
        or (record.get("upload_integrity") or {}).get("expected_file_count")
        or len(files_on_record)
    )

    integrity = build_integrity_report(
        expected_file_count=expected,
        expected_file_names=[str(f.get("original_name") or f.get("name") or "") for f in files_on_record],
        lifecycle=merged,
        received_file_count=len(files_on_record),
        batch_complete=bool(custody.get("batch_complete", True)),
    )

    durability = require_upload_durability_verified(
        intake_id,
        saved_files=files_on_record,
        integrity=integrity,
    )
    if durability.get("integrity"):
        integrity = durability["integrity"]

    _apply_custody_status(
        record,
        integrity,
        durability_ok=bool(durability.get("durability_verified")),
    )
    committed = bool(durability.get("durability_verified"))
    _commit_intake_state(intake_id, record, integrity=integrity, committed=committed)

    derive_evidence_registry_for_intake(intake_id, write=True)
    registered = lookup_by_intake(intake_id)
    for row in lookup_by_intake(intake_id):
        eid = str(row.get("evidence_id") or "")
        if eid and row.get("current_status") != STATUS_RECOVERED:
            try:
                update_evidence_status(eid, STATUS_RECOVERED, detail="forensic_recovery")
            except (KeyError, ValueError):
                pass

    append_transaction_event(
        intake_id,
        PHASE_FORENSIC_RECOVERED,
        metadata={
            "disk_files": len(disk_names),
            "recovered_evidence_count": len(recovered_evidence),
            "committed": committed,
            "pre_issues": pre_reconcile.get("issues") or [],
        },
    )

    post_reconcile = reconcile_intake(intake_id)
    recovery_report = {
        "pre_issues": pre_reconcile.get("issues") or [],
        "post_issues": post_reconcile.get("issues") or [],
        "index_row_exists": latest_index_row(intake_id) is not None,
        "intake_json_exists": intake_json_path(intake_id).is_file(),
        "transaction_phases": [r.get("phase") for r in tx_log],
        "registry_entries_added": len(registered),
        "on_disk_hashes": hash_uploads_on_disk(intake_id),
    }

    return {
        "ok": True,
        "intake_id": intake_id,
        "recovered_intake": record,
        "recovered_evidence": recovered_evidence,
        "recovery_report": recovery_report,
        "custody_status": record.get("custody_status"),
        "committed": committed,
    }

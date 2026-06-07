"""Repair stale intake integrity metadata from durable disk truth."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evidence_registry import derive_evidence_registry_for_intake, lookup_by_intake
from .retention import hash_uploads_on_disk, require_upload_durability_verified
from .storage import intake_dir, load_intake_record
from .transactions import PHASE_INTEGRITY_REPAIRED, append_transaction_event

logger = logging.getLogger(__name__)

ROOT_CAUSE_STALE_EXPECTED = "stale_expected_from_prior_upload_batch"
ROOT_CAUSE_DISK_MISMATCH = "disk_metadata_mismatch"
ROOT_CAUSE_MISSING_FILES = "files_missing_on_disk"


def _promoted_file_count(intake_id: str) -> int:
    from services.durable_storage import active_data_root

    evidence_dir = active_data_root() / "projects" / intake_id / "evidence"
    if not evidence_dir.is_dir():
        return 0
    return sum(1 for p in evidence_dir.iterdir() if p.is_file())


def _processed_file_count(intake_id: str) -> int:
    try:
        from services.evidence_intelligence import storage as ei_storage

        extractions = ei_storage.load_jsonl(intake_id, "extractions.jsonl", limit=500)
        sources = {
            str(e.get("source_file") or e.get("artifact_id") or "")
            for e in extractions
            if str(e.get("source_file") or e.get("artifact_id") or "")
        }
        return len(sources)
    except Exception:
        return 0


def intake_integrity_truth(intake_id: str) -> Dict[str, Any]:
    """Gather reconciled counts from disk, intake record, registry, and EI."""
    from .reconcile import reconcile_intake

    on_disk = hash_uploads_on_disk(intake_id)
    disk_names = sorted(on_disk.keys())

    record: Dict[str, Any] = {}
    try:
        record = load_intake_record(intake_id, persist_recovery=False)
    except Exception:
        record = {}

    ui = record.get("upload_integrity") or {}
    files_on_record = list(record.get("files") or [])
    record_names = {str(f.get("name") or "") for f in files_on_record}
    disk_set = set(disk_names)

    stale_expected = int(ui.get("expected_file_count") or 0)
    received = int(ui.get("received_file_count") or 0)
    persisted = int(ui.get("persisted_file_count") or 0)
    verified = int(ui.get("verified_file_count") or 0)
    hash_verified = verified
    promoted = _promoted_file_count(intake_id)
    processed = _processed_file_count(intake_id)

    missing_on_disk = sorted(record_names - disk_set - {""})
    extra_on_disk = sorted(disk_set - record_names)

    registry = lookup_by_intake(intake_id)
    registry_verified = sum(
        1 for r in registry if str(r.get("current_status") or "").lower() == "verified"
    )

    reconcile = reconcile_intake(intake_id)

    return {
        "intake_id": intake_id,
        "expected_count": stale_expected,
        "received_count": received,
        "persisted_count": persisted,
        "hash_verified_count": hash_verified,
        "promoted_count": promoted,
        "processed_count": processed,
        "on_disk_count": len(disk_names),
        "file_count": int(record.get("file_count") or len(files_on_record)),
        "registry_verified_count": registry_verified,
        "disk_file_names": disk_names,
        "missing_files": missing_on_disk,
        "extra_files": extra_on_disk,
        "custody_status": record.get("custody_status") or ui.get("custody_status"),
        "reconcile_issues": list(reconcile.get("issues") or []),
        "disk_agrees": _disk_counts_agree(
            on_disk_count=len(disk_names),
            received=received,
            persisted=persisted,
            verified=verified,
            file_count=int(record.get("file_count") or len(files_on_record)),
            failed=int(ui.get("failed_file_count") or 0),
        ),
    }


def _disk_counts_agree(
    *,
    on_disk_count: int,
    received: int,
    persisted: int,
    verified: int,
    file_count: int,
    failed: int,
) -> bool:
    if on_disk_count <= 0:
        return False
    return (
        failed == 0
        and received == on_disk_count
        and persisted == on_disk_count
        and verified == on_disk_count
        and file_count == on_disk_count
    )


def _emit_operator_review(intake_id: str, *, reason: str, truth: Dict[str, Any]) -> None:
    try:
        from .telemetry import emit_intake_event

        emit_intake_event(
            "operator_review_needed",
            message=f"Integrity repair marked {intake_id} partial: {reason}",
            metadata={
                "intake_id": intake_id,
                "reason": reason,
                "truth": {
                    k: truth.get(k)
                    for k in (
                        "expected_count",
                        "received_count",
                        "persisted_count",
                        "hash_verified_count",
                        "on_disk_count",
                        "missing_files",
                        "extra_files",
                    )
                },
            },
        )
    except Exception as exc:
        logger.warning("operator_review emit failed for %s: %s", intake_id, exc)


def repair_intake_integrity_mismatch(intake_id: str) -> Dict[str, Any]:
    """
    Repair stale expected/received metadata when durable disk truth confirms
    all customer files are present and hash-verified. Never deletes files or
    inflates counts without disk evidence.
    """
    from .intake import _apply_custody_status, _commit_intake_state
    from .integrity import build_integrity_report, merge_batch_lifecycle
    from .reconcile import reconcile_intake

    idir = intake_dir(intake_id)
    if not idir.is_dir():
        return {"ok": False, "error": "intake_dir_missing", "intake_id": intake_id}

    pre_truth = intake_integrity_truth(intake_id)
    pre_reconcile = reconcile_intake(intake_id)
    pre_issues = list(pre_reconcile.get("issues") or [])
    stale_expected = (
        int(pre_truth.get("expected_count") or 0) > 0
        and int(pre_truth.get("received_count") or 0) > 0
        and int(pre_truth.get("expected_count") or 0)
        != int(pre_truth.get("received_count") or 0)
        and bool(pre_truth.get("disk_agrees"))
    )

    if "expected_received_mismatch" not in pre_issues and not stale_expected:
        return {
            "ok": True,
            "action": "no_repair_needed",
            "intake_id": intake_id,
            "before": pre_truth,
            "after": pre_truth,
            "root_cause": None,
            "repair_applied": None,
            "plain_english": (
                f"{intake_id} has no expected/received mismatch; durable counts already agree."
            ),
        }

    try:
        record = load_intake_record(intake_id, persist_recovery=True)
    except Exception as exc:
        return {"ok": False, "error": f"intake_load_failed:{exc}", "intake_id": intake_id}

    on_disk = hash_uploads_on_disk(intake_id)
    disk_count = len(on_disk)
    files_on_record = list(record.get("files") or [])

    if pre_truth.get("missing_files"):
        record["custody_status"] = "partial_upload"
        record["review_status"] = "partial_upload"
        record["status"] = "partial_upload"
        record["urgent"] = True
        from .intake import _commit_intake_state

        _commit_intake_state(intake_id, record, integrity=record.get("upload_integrity") or {}, committed=True)
        _emit_operator_review(intake_id, reason=ROOT_CAUSE_MISSING_FILES, truth=pre_truth)
        post_truth = intake_integrity_truth(intake_id)
        return {
            "ok": False,
            "action": "marked_partial",
            "intake_id": intake_id,
            "before": pre_truth,
            "after": post_truth,
            "root_cause": ROOT_CAUSE_MISSING_FILES,
            "repair_applied": "marked_partial_upload_with_operator_review",
            "plain_english": (
                f"{intake_id} is PARTIAL: metadata references files not found on durable disk "
                f"({', '.join(pre_truth['missing_files'])})."
            ),
        }

    if not pre_truth.get("disk_agrees"):
        record["custody_status"] = "partial_upload"
        record["review_status"] = "partial_upload"
        record["status"] = "partial_upload"
        record["urgent"] = True
        from .intake import _commit_intake_state

        _commit_intake_state(intake_id, record, integrity=record.get("upload_integrity") or {}, committed=True)
        _emit_operator_review(intake_id, reason=ROOT_CAUSE_DISK_MISMATCH, truth=pre_truth)
        post_truth = intake_integrity_truth(intake_id)
        return {
            "ok": False,
            "action": "marked_partial",
            "intake_id": intake_id,
            "before": pre_truth,
            "after": post_truth,
            "root_cause": ROOT_CAUSE_DISK_MISMATCH,
            "repair_applied": "marked_partial_upload_with_operator_review",
            "plain_english": (
                f"{intake_id} is PARTIAL: received/persisted/verified counts do not match "
                f"durable disk ({disk_count} files on disk)."
            ),
        }

    stale_expected = int(pre_truth.get("expected_count") or 0)
    received = int(pre_truth.get("received_count") or 0)
    root_cause = ROOT_CAUSE_STALE_EXPECTED
    extra_files = list(pre_truth.get("extra_files") or [])
    if stale_expected >= received and not extra_files:
        root_cause = ROOT_CAUSE_DISK_MISMATCH

    prior_lifecycle = list((record.get("upload_integrity") or {}).get("file_lifecycle") or [])
    expected_names = [
        str(f.get("original_name") or f.get("name") or "")
        for f in files_on_record
        if str(f.get("original_name") or f.get("name") or "")
    ]

    integrity = build_integrity_report(
        expected_file_count=disk_count,
        expected_file_names=expected_names,
        lifecycle=prior_lifecycle,
        received_file_count=disk_count,
        batch_complete=True,
    )

    durability = require_upload_durability_verified(
        intake_id,
        saved_files=files_on_record,
        integrity=integrity,
    )
    if durability.get("integrity"):
        integrity = durability["integrity"]

    repair_event = append_transaction_event(
        intake_id,
        PHASE_INTEGRITY_REPAIRED,
        metadata={
            "before_expected": stale_expected,
            "after_expected": disk_count,
            "received": received,
            "disk_files": disk_count,
            "root_cause": root_cause,
        },
    )
    custody = dict(record.get("upload_custody") or {})
    custody.update(
        {
            "total_expected_count": disk_count,
            "batch_complete": True,
            "cumulative_received_count": disk_count,
            "integrity_repair_at_utc": repair_event.get("at_utc"),
            "integrity_repair_note": (
                "expected_file_count synced from durable disk after multi-batch upload"
            ),
        }
    )
    record["upload_custody"] = custody
    record["file_count"] = disk_count

    _apply_custody_status(
        record,
        integrity,
        durability_ok=bool(durability.get("durability_verified")),
    )
    committed = bool(durability.get("durability_verified"))
    _commit_intake_state(intake_id, record, integrity=integrity, committed=committed)
    derive_evidence_registry_for_intake(intake_id, write=True)

    post_truth = intake_integrity_truth(intake_id)
    post_reconcile = reconcile_intake(intake_id)
    custody_status = str(record.get("custody_status") or "")

    extra_note = ""
    if extra_files:
        extra_note = f" Extra files vs first-batch manifest: {', '.join(extra_files)}."

    plain_english = (
        f"{intake_id}: customer uploaded in multiple batches; first batch declared "
        f"{stale_expected} file(s) but {disk_count} file(s) are on durable disk, all "
        f"hash-verified. Metadata expected count was repaired to {disk_count}. "
        f"Custody status: {custody_status}.{extra_note}"
    )

    if custody_status == "partial_upload":
        _emit_operator_review(intake_id, reason="post_repair_partial_custody", truth=post_truth)

    return {
        "ok": bool(post_reconcile.get("ok")),
        "action": "metadata_repaired_from_disk",
        "intake_id": intake_id,
        "before": pre_truth,
        "after": post_truth,
        "root_cause": root_cause,
        "repair_applied": "synced_expected_from_disk_truth",
        "pre_issues": pre_issues,
        "post_issues": list(post_reconcile.get("issues") or []),
        "custody_status": custody_status,
        "committed": committed,
        "plain_english": plain_english,
    }

"""
Canonical intake inventory — single source of truth for all operator diagnostics.

Every endpoint that reports intake_directories, upload_files, queue depth, or
retention counts MUST derive from build_intake_inventory().
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .storage import (
    count_upload_files,
    index_intake_ids,
    index_jsonl,
    intake_dir,
    intake_json_path,
    intakes_root,
    is_pending_review,
    latest_index_row,
    list_intake_ids,
    load_intake_record,
    max_index_file_count,
)


def ghost_intake_reasons(intake_id: str, *, record: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    SEV-1 reasons when a pending intake has no payload on disk but evidence says files existed.
    """
    from .file_durability import list_durability_sidecars, sidecar_orphan_reasons
    from .hash_ledger import ledger_entries_for_intake
    from .quarantine import load_quarantine_manifest
    from .retention import hash_uploads_on_disk, load_audit_receipt
    from .transactions import (
        PHASE_AUDIT_WRITTEN,
        PHASE_FILES_PERSISTED,
        PHASE_HASH_VERIFIED,
        load_transaction_log,
    )

    if record is None:
        try:
            record = load_intake_record(intake_id, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            record = {}

    if not is_pending_review(record.get("review_status")):
        return []

    on_disk = hash_uploads_on_disk(intake_id)
    disk_count = len(on_disk)
    if disk_count > 0:
        return []

    reasons: List[str] = list(sidecar_orphan_reasons(intake_id))

    ui = record.get("upload_integrity") or {}
    verified = int(ui.get("verified_file_count") or 0)
    persisted = int(ui.get("persisted_file_count") or 0)
    meta_count = int(record.get("file_count") or len(record.get("files") or []))
    audit = load_audit_receipt(intake_id)

    if verified > 0 or persisted > 0 or meta_count > 0:
        reasons.append("metadata_claims_files_disk_empty")
    if audit:
        reasons.append("audit_receipt_without_files")
    if verified > 0 and not audit:
        reasons.append("verified_without_audit_receipt")

    if ledger_entries_for_intake(intake_id):
        reasons.append("hash_ledger_without_files")

    manifest = load_quarantine_manifest(intake_id)
    if manifest and int(manifest.get("file_count") or 0) > 0:
        reasons.append("quarantine_manifest_without_files")

    phases = {str(r.get("phase")) for r in load_transaction_log(intake_id)}
    if phases & {PHASE_FILES_PERSISTED, PHASE_HASH_VERIFIED, PHASE_AUDIT_WRITTEN}:
        reasons.append("transaction_log_claims_persisted_disk_empty")

    if max_index_file_count(intake_id) > 0:
        reasons.append("index_claims_files_disk_empty")

    from .transactions import intake_commit_complete

    queue_visible = False
    try:
        from .queue import get_operator_review_queue

        q = get_operator_review_queue(limit=200, persist_recovery=False)
        queue_visible = intake_id in {r.get("intake_id") for r in q.get("queue") or []}
    except Exception:
        queue_visible = False

    if (
        queue_visible
        and not intake_commit_complete(intake_id)
        and int(record.get("file_count") or 0) == 0
    ):
        reasons.append("queue_visible_uncommitted_no_payload")

    custody = record.get("upload_custody") or {}
    if custody.get("newest_upload_at_utc") and not meta_count:
        reasons.append("custody_upload_timestamp_without_files")

    # Sidecar records prove write occurred even if metadata stripped
    for sc in list_durability_sidecars(intake_id):
        name = str(sc.get("filename") or "")
        if name and not (intake_dir(intake_id) / "uploads" / name).is_file():
            tag = f"durability_sidecar_proves_write:{name}"
            if tag not in reasons:
                reasons.append(tag)

    return reasons


def is_ghost_intake(intake_id: str, *, record: Optional[Dict[str, Any]] = None) -> bool:
    return len(ghost_intake_reasons(intake_id, record=record)) > 0


def detect_ghost_intakes(*, limit: int = 500) -> List[Dict[str, Any]]:
    """
    SEV-1: pending/review intakes whose metadata, ledger, or audit claims files but uploads/ is empty.
    """
    from .retention import hash_uploads_on_disk, load_audit_receipt

    ghosts: List[Dict[str, Any]] = []
    for iid in list_intake_ids(limit=limit):
        try:
            rec = load_intake_record(iid, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        if not is_pending_review(rec.get("review_status")):
            continue
        reasons = ghost_intake_reasons(iid, record=rec)
        if not reasons:
            continue
        on_disk = hash_uploads_on_disk(iid)
        ui = rec.get("upload_integrity") or {}
        ghosts.append(
            {
                "intake_id": iid,
                "reasons": reasons,
                "verified_file_count": int(ui.get("verified_file_count") or 0),
                "persisted_file_count": int(ui.get("persisted_file_count") or 0),
                "metadata_file_count": int(rec.get("file_count") or len(rec.get("files") or [])),
                "on_disk_file_count": len(on_disk),
                "audit_receipt_exists": load_audit_receipt(iid) is not None,
            }
        )
    return ghosts


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_intake_inventory(*, limit: int = 500, intake_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Live filesystem + index inventory. Never cached.
    """
    from services.durable_storage import active_data_root

    data_root = active_data_root().resolve()
    roots = intakes_root()
    scan_at = _utc_now()

    if intake_id:
        disk_ids = [intake_id.strip()]
    else:
        disk_ids = list_intake_ids(limit=limit)

    index_ids = set(index_intake_ids(tail_lines=max(limit, 500)))
    only_disk = sorted(set(disk_ids) - index_ids) if not intake_id else []
    only_index = sorted(index_ids - set(disk_ids)) if not intake_id else []

    intake_json_count = 0
    file_count = 0
    pending_review_count = 0
    pending_ids: List[str] = []

    from .file_durability import is_upload_payload_file

    for iid in disk_ids:
        if intake_json_path(iid).is_file():
            intake_json_count += 1
        uploads = intake_dir(iid) / "uploads"
        if uploads.is_dir():
            file_count += sum(1 for p in uploads.iterdir() if p.is_file() and is_upload_payload_file(p.name))
        try:
            rec = load_intake_record(iid, persist_recovery=False)
            if is_pending_review(rec.get("review_status")):
                pending_review_count += 1
                pending_ids.append(iid)
        except (FileNotFoundError, ValueError, OSError):
            continue

    return {
        "ok": True,
        "scan_type": "live",
        "scan_at_utc": scan_at,
        "data_root": str(data_root),
        "write_root": str(data_root),
        "read_root": str(data_root),
        "intakes_root": str(roots.resolve()),
        "index_jsonl": str(index_jsonl().resolve()),
        "intake_directories": len(disk_ids),
        "intake_json_files": intake_json_count,
        "upload_files": file_count,
        "index_tail_unique_ids": len(index_ids),
        "pending_review_count": pending_review_count,
        "pending_intake_ids_sample": pending_ids[:25],
        "intake_ids_sample": disk_ids[:25],
        "only_on_disk_not_in_index": only_disk[:50],
        "only_in_index_not_on_disk": only_index[:50],
        "index_disk_agree": not only_disk and not only_index,
    }


def verify_inventory_agreement(
    *,
    inventory: Optional[Dict[str, Any]] = None,
    queue_depth: Optional[int] = None,
    retention_scan: Optional[Dict[str, Any]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    live_boot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Prove all inventory sources report identical counts.
    """
    inv = inventory or build_intake_inventory()
    disagreements: List[Dict[str, Any]] = []

    canonical_dirs = int(inv.get("intake_directories") or 0)
    canonical_files = int(inv.get("upload_files") or 0)
    canonical_pending = int(inv.get("pending_review_count") or 0)

    def _check(source: str, dirs: Optional[int], files: Optional[int], pending: Optional[int] = None) -> None:
        if dirs is not None and int(dirs) != canonical_dirs:
            disagreements.append(
                {"source": source, "field": "intake_directories", "expected": canonical_dirs, "actual": int(dirs)}
            )
        if files is not None and int(files) != canonical_files:
            disagreements.append(
                {"source": source, "field": "upload_files", "expected": canonical_files, "actual": int(files)}
            )
        if pending is not None and int(pending) != canonical_pending:
            disagreements.append(
                {"source": source, "field": "pending_review_count", "expected": canonical_pending, "actual": int(pending)}
            )

    count_via_helper = count_upload_files()
    if count_via_helper != canonical_files:
        disagreements.append(
            {
                "source": "count_upload_files",
                "field": "upload_files",
                "expected": canonical_files,
                "actual": count_via_helper,
            }
        )

    if queue_depth is not None:
        _check("queue", None, None, queue_depth)

    if retention_scan is not None:
        _check(
            "retention_scan",
            int(retention_scan.get("intake_directories") or 0),
            int(retention_scan.get("upload_files") or 0),
            None,
        )

    if diagnostics is not None:
        _check(
            "diagnostics",
            int(diagnostics.get("intake_directories_found") or 0),
            int(diagnostics.get("upload_files_on_disk") or 0),
            int(diagnostics.get("pending_review_count") or 0),
        )

    if live_boot is not None:
        _check(
            "live_boot",
            int(live_boot.get("intake_directories") or 0),
            int(live_boot.get("upload_files") or 0),
            None,
        )
        live_scan = live_boot.get("live_scan") or {}
        _check(
            "live_boot.live_scan",
            int(live_scan.get("intake_directories") or 0),
            int(live_scan.get("upload_files") or 0),
            None,
        )

    ghosts = detect_ghost_intakes()
    if ghosts:
        disagreements.append(
            {
                "source": "ghost_intakes",
                "field": "upload_files",
                "ghost_count": len(ghosts),
                "ghosts": ghosts[:25],
            }
        )

    ok = len(disagreements) == 0 and bool(inv.get("index_disk_agree", True))
    live_scan_status = "healthy" if ok and not ghosts else "critical"
    return {
        "ok": ok,
        "scan_at_utc": inv.get("scan_at_utc"),
        "canonical": {
            "intake_directories": canonical_dirs,
            "upload_files": canonical_files,
            "pending_review_count": canonical_pending,
        },
        "disagreements": disagreements,
        "ghost_intakes": ghosts,
        "ghost_intake_count": len(ghosts),
        "live_scan_status": live_scan_status,
    }

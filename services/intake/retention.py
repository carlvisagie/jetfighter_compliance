"""Founding beta durable retention — filesystem is source of truth; audit receipts prove writes."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from services.durable_storage import active_data_root
from services.production import is_production

from .classification import load_classification
from .storage import (
    all_intake_ids,
    index_intake_ids,
    index_jsonl,
    intake_dir,
    intake_json_path,
    intakes_root,
    is_pending_review,
    list_intake_ids,
    load_intake_record,
)

logger = logging.getLogger(__name__)

AUDIT_FILENAME = "intake_audit.json"
_STARTUP_SCAN: Optional[Dict[str, Any]] = None
_LAST_INVENTORY: Optional[Dict[str, int]] = None
_PUBLIC_DURABILITY_DETAIL = (
    "Your files could not be verified on secure storage. "
    "Please try again or contact support@keepyourcontracts.com."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit_sev1_data_loss_suspected(message: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """SEV-1 — unexplained intake disappearance or inventory drop."""
    logger.critical("[SEV-1] intake_data_loss_suspected %s detail=%s", message, detail)
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "intake",
            "intake_data_loss_suspected",
            message=message[:240],
            metadata=detail or {},
            severity="critical",
        )
    except Exception:
        pass


def resolved_write_root() -> Path:
    return active_data_root().resolve()


def resolved_read_root() -> Path:
    return active_data_root().resolve()


def assert_read_write_roots_match() -> None:
    write = resolved_write_root()
    read = resolved_read_root()
    if write != read:
        msg = f"intake data root mismatch write={write} read={read}"
        logger.critical(msg)
        raise HTTPException(
            status_code=503,
            detail="Paperwork storage configuration error.",
            headers={"X-KYC-Error-Code": "data_root_mismatch"},
        )


def audit_receipt_path(intake_id: str) -> Path:
    return intake_dir(intake_id) / AUDIT_FILENAME


def classification_path(intake_id: str) -> Path:
    return intake_dir(intake_id) / "classification.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_uploads_on_disk(intake_id: str) -> Dict[str, str]:
    from .file_durability import is_upload_payload_file

    uploads = intake_dir(intake_id) / "uploads"
    out: Dict[str, str] = {}
    if not uploads.is_dir():
        return out
    for p in sorted(uploads.iterdir()):
        if p.is_file() and is_upload_payload_file(p.name):
            try:
                out[p.name] = sha256_file(p)
            except OSError as exc:
                logger.warning("hash failed %s: %s", p, exc)
    return out


def expected_payload_file_count(
    intake_id: str, *, receipt: Optional[Dict[str, Any]] = None
) -> int:
    """How many upload payload files this intake is expected to have on disk."""
    rec = receipt if receipt is not None else load_audit_receipt(intake_id)
    if rec:
        file_hashes = rec.get("file_hashes") or {}
        if file_hashes:
            return len(file_hashes)
        files_written = rec.get("files_written") or []
        if files_written:
            return len(files_written)
        return max(
            int(rec.get("verified_file_count") or 0),
            int(rec.get("persisted_file_count") or 0),
        )
    record: Dict[str, Any] = {}
    try:
        record = load_intake_record(intake_id, persist_recovery=False)
    except (FileNotFoundError, ValueError, OSError):
        record = {}
    ui = record.get("upload_integrity") or {}
    return max(
        int(ui.get("verified_file_count") or 0),
        int(ui.get("persisted_file_count") or 0),
        int(ui.get("expected_file_count") or 0),
        int(record.get("file_count") or len(record.get("files") or [])),
    )


def audit_hashes_match(intake_id: str, *, on_disk: Optional[Dict[str, str]] = None) -> bool:
    """True when on-disk upload hashes match the durable audit receipt."""
    from .file_durability import sidecar_orphan_reasons
    from .hash_ledger import ledger_entries_for_intake

    receipt = load_audit_receipt(intake_id)
    disk = on_disk if on_disk is not None else hash_uploads_on_disk(intake_id)
    ledger = ledger_entries_for_intake(intake_id)
    expected_count = expected_payload_file_count(intake_id, receipt=receipt)
    if expected_count > 0 and not disk:
        return False
    if not receipt:
        if ledger or sidecar_orphan_reasons(intake_id):
            return False
        if expected_count > 0:
            return False
        return len(disk) == 0
    if not disk:
        return False
    if receipt.get("file_hashes"):
        for name, expected in (receipt.get("file_hashes") or {}).items():
            actual = disk.get(name)
            if actual is None or actual != expected:
                return False
        return True
    for entry in receipt.get("files_written") or []:
        name = str(entry.get("name") or "")
        exp = str(entry.get("sha256") or "")
        if exp and disk.get(name) != exp:
            return False
    return bool(disk)


def build_audit_receipt(
    intake_id: str,
    *,
    files_written: List[Dict[str, Any]],
    created_utc: Optional[str] = None,
    integrity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    assert_read_write_roots_match()
    root = resolved_write_root()
    idir = intake_dir(intake_id).resolve()
    ij = intake_json_path(intake_id).resolve()
    clf = classification_path(intake_id).resolve()
    file_hashes: Dict[str, str] = {}
    for entry in files_written:
        name = str(entry.get("name") or "")
        if not name:
            continue
        dest = idir / "uploads" / name
        if dest.is_file():
            file_hashes[name] = sha256_file(dest)
        elif entry.get("sha256"):
            file_hashes[name] = str(entry["sha256"])
    receipt: Dict[str, Any] = {
        "intake_id": intake_id,
        "created_utc": created_utc or _utc_now(),
        "data_root": str(root),
        "intake_dir": str(idir),
        "files_written": [
            {
                "name": e.get("name"),
                "size": e.get("size"),
                "sha256": file_hashes.get(str(e.get("name") or ""), ""),
            }
            for e in files_written
        ],
        "file_hashes": file_hashes,
        "classification_path": str(clf),
        "intake_json_path": str(ij),
    }
    if integrity:
        receipt.update(
            {
                "expected_file_count": integrity.get("expected_file_count"),
                "received_file_count": integrity.get("received_file_count"),
                "persisted_file_count": integrity.get("persisted_file_count"),
                "verified_file_count": integrity.get("verified_file_count"),
                "integrity_ok": integrity.get("integrity_ok"),
                "expected_files": integrity.get("expected_files"),
                "verified_files": integrity.get("verified_files"),
                "missing_files": integrity.get("missing_files"),
                "rejected_files": integrity.get("rejected_files"),
                "file_lifecycle": integrity.get("file_lifecycle"),
            }
        )
    return receipt


def write_audit_receipt(intake_id: str, receipt: Dict[str, Any]) -> Path:
    from .storage import atomic_write_json

    path = audit_receipt_path(intake_id)
    from .storage import assert_canonical_write_path

    assert_canonical_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, receipt)
    return path


def load_audit_receipt(intake_id: str) -> Optional[Dict[str, Any]]:
    path = audit_receipt_path(intake_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def verify_intake_durability(
    intake_id: str,
    *,
    expected_files: List[Dict[str, Any]],
    require_classification: bool = False,
    pre_commit: bool = False,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify filesystem SoT after upload. Returns (ok, detail dict).
    pre_commit=True: verify disk + hashes only (intake.json not yet updated with files).
    """
    detail: Dict[str, Any] = {
        "intake_id": intake_id,
        "write_root": str(resolved_write_root()),
        "read_root": str(resolved_read_root()),
        "roots_match": resolved_write_root() == resolved_read_root(),
    }
    if not detail["roots_match"]:
        detail["error"] = "read_write_root_mismatch"
        return False, detail

    idir = intake_dir(intake_id)
    detail["intake_dir_exists"] = idir.is_dir()
    ij = intake_json_path(intake_id)
    detail["intake_json_exists"] = ij.is_file()

    uploads = idir / "uploads"
    on_disk = hash_uploads_on_disk(intake_id)
    detail["upload_files_on_disk"] = list(on_disk.keys())

    missing: List[str] = []
    hash_mismatch: List[str] = []
    for entry in expected_files:
        name = str(entry.get("name") or "")
        if not name:
            continue
        dest = uploads / name
        if not dest.is_file():
            missing.append(name)
            continue
        expected_hash = entry.get("sha256")
        actual = on_disk.get(name) or sha256_file(dest)
        if expected_hash and expected_hash != actual:
            hash_mismatch.append(name)
        entry["sha256"] = actual

    detail["missing_files"] = missing
    detail["hash_mismatches"] = hash_mismatch
    detail["upload_files_found"] = len(missing) == 0 and len(expected_files) > 0

    if ij.is_file():
        try:
            meta = json.loads(ij.read_text(encoding="utf-8"))
            meta_count = int(meta.get("file_count") or len(meta.get("files") or []))
            detail["intake_json_file_count"] = meta_count
            detail["intake_json_matches_disk"] = meta_count >= len(on_disk)
        except (json.JSONDecodeError, OSError):
            detail["intake_json_matches_disk"] = False
    else:
        detail["intake_json_matches_disk"] = False

    clf_path = classification_path(intake_id)
    detail["classification_exists"] = clf_path.is_file()
    if require_classification and not detail["classification_exists"]:
        detail["error"] = "classification_missing"
        return False, detail

    if pre_commit:
        ok = (
            detail["intake_dir_exists"]
            and detail["upload_files_found"]
            and not missing
            and not hash_mismatch
        )
    else:
        ok = (
            detail["intake_dir_exists"]
            and detail["intake_json_exists"]
            and detail["upload_files_found"]
            and not hash_mismatch
            and detail.get("intake_json_matches_disk", False)
        )
    if not ok and "error" not in detail:
        if missing:
            detail["error"] = "files_missing_on_disk"
        elif hash_mismatch:
            detail["error"] = "file_hash_mismatch"
        elif not detail["intake_json_exists"]:
            detail["error"] = "intake_json_missing"
        else:
            detail["error"] = "durability_check_failed"
    return ok, detail


def require_upload_durability_verified(
    intake_id: str,
    *,
    saved_files: List[Dict[str, Any]],
    integrity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Raise in production if post-upload verification fails; write audit with integrity fields."""
    from .integrity import mark_lifecycle_verified

    assert_read_write_roots_match()
    lifecycle = list((integrity or {}).get("file_lifecycle") or [])
    for entry in saved_files:
        name = str(entry.get("name") or "")
        if not name:
            continue
        dest = intake_dir(intake_id) / "uploads" / name
        if dest.is_file():
            entry["sha256"] = sha256_file(dest)

    on_disk = hash_uploads_on_disk(intake_id)
    verified_count = mark_lifecycle_verified(lifecycle, saved_files, on_disk_hashes=on_disk)
    if integrity is not None:
        integrity = dict(integrity)
        integrity["file_lifecycle"] = lifecycle
        integrity["verified_file_count"] = verified_count
        integrity["persisted_file_count"] = sum(
            1
            for e in lifecycle
            if e.get("state") in ("persisted", "verified", "duplicate")
        )
        integrity["verified_files"] = [
            {
                "original_name": e.get("original_name"),
                "stored_name": e.get("stored_name"),
                "sha256": e.get("sha256"),
            }
            for e in lifecycle
            if e.get("state") == "verified"
        ]
        from .integrity import _count_lifecycle_states, derive_intake_status, lifecycle_to_custody_row

        state_counts = _count_lifecycle_states(lifecycle)
        integrity["rejected_file_count"] = state_counts["rejected_file_count"]
        integrity["duplicate_file_count"] = state_counts["duplicate_file_count"]
        integrity["failed_file_count"] = state_counts["failed_file_count"]
        integrity["file_lifecycle_table"] = [lifecycle_to_custody_row(e) for e in lifecycle]
    ok, detail = verify_intake_durability(intake_id, expected_files=saved_files, pre_commit=True)
    if integrity is not None:
        integrity["integrity_ok"] = (
            int(integrity.get("expected_file_count") or 0) == verified_count
            and not integrity.get("missing_files")
            and state_counts["failed_file_count"] == 0
            and verified_count == int(integrity.get("received_file_count") or 0)
            and verified_count == int(integrity.get("persisted_file_count") or 0)
        )
        integrity["integrity_mismatch"] = not integrity["integrity_ok"]
        integrity["custody_status"] = derive_intake_status(
            integrity,
            durability_ok=ok,
            batch_complete=bool(integrity.get("batch_complete", True)),
        )
    receipt = build_audit_receipt(
        intake_id,
        files_written=saved_files,
        created_utc=detail.get("verified_at_utc") or _utc_now(),
        integrity=integrity,
    )
    if ok and saved_files:
        write_audit_receipt(intake_id, receipt)
        detail["audit_receipt_path"] = str(audit_receipt_path(intake_id).resolve())
        detail["durable_receipt_created"] = True
        from .durable_root import durable_data_root, mount_status_for_operator
        from .hash_ledger import append_hash_ledger

        mount_status_for_operator()
        root = str(durable_data_root())
        for entry in saved_files:
            name = str(entry.get("name") or "")
            if not name:
                continue
            dest = intake_dir(intake_id) / "uploads" / name
            if dest.is_file():
                append_hash_ledger(
                    intake_id=intake_id,
                    stored_filename=name,
                    sha256=str(entry.get("sha256") or sha256_file(dest)),
                    size_bytes=int(entry.get("size") or dest.stat().st_size),
                    data_root=root,
                    write_path=str(dest.resolve()),
                )
        return {
            "durability_verified": True,
            "durable_receipt_created": True,
            "verified_file_count": verified_count,
            "audit": receipt,
            "detail": detail,
            "integrity": integrity,
        }

    detail["durable_receipt_created"] = False
    logger.critical(
        "intake_upload_durability_failed intake_id=%s detail=%s",
        intake_id,
        detail,
    )
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "intake",
            "intake_durability_failed",
            message=intake_id,
            metadata={"intake_id": intake_id, **{k: detail.get(k) for k in detail if k != "file_hashes"}},
        )
    except Exception:
        pass

    if is_production():
        raise HTTPException(
            status_code=500,
            detail=_PUBLIC_DURABILITY_DETAIL,
            headers={"X-KYC-Error-Code": "upload_durability_failed"},
        )
    return {
        "durability_verified": False,
        "durable_receipt_created": False,
        "verified_file_count": 0,
        "detail": detail,
    }


def get_intake_audit(intake_id: str) -> Dict[str, Any]:
    receipt = load_audit_receipt(intake_id)
    on_disk = hash_uploads_on_disk(intake_id)
    record: Dict[str, Any] = {}
    try:
        record = load_intake_record(intake_id, persist_recovery=False)
    except (FileNotFoundError, ValueError, OSError):
        record = {}
    ui = record.get("upload_integrity") or {}
    custody = record.get("upload_custody") or {}
    lifecycle_table = list(ui.get("file_lifecycle_table") or [])
    if not lifecycle_table and ui.get("file_lifecycle"):
        from .integrity import lifecycle_to_custody_row

        lifecycle_table = [lifecycle_to_custody_row(e) for e in ui.get("file_lifecycle") or []]
    from .transactions import load_transaction_log

    return {
        "ok": True,
        "intake_id": intake_id,
        "write_root": str(resolved_write_root()),
        "read_root": str(resolved_read_root()),
        "audit_receipt": receipt,
        "audit_receipt_exists": receipt is not None,
        "audit_receipt_path": str(audit_receipt_path(intake_id).resolve()),
        "files_on_disk": on_disk,
        "intake_json_path": str(intake_json_path(intake_id).resolve()),
        "classification_path": str(classification_path(intake_id).resolve()),
        "custody_status": record.get("custody_status") or ui.get("custody_status"),
        "upload_integrity": ui,
        "upload_custody": custody,
        "file_lifecycle_table": lifecycle_table,
        "transaction_lifecycle": load_transaction_log(intake_id),
        "count_breakdown": {
            "expected_file_count": ui.get("expected_file_count"),
            "received_file_count": ui.get("received_file_count"),
            "persisted_file_count": ui.get("persisted_file_count"),
            "verified_file_count": ui.get("verified_file_count"),
            "rejected_file_count": ui.get("rejected_file_count"),
            "duplicate_file_count": ui.get("duplicate_file_count"),
            "failed_file_count": ui.get("failed_file_count"),
        },
    }


def _queue_contains_intake(intake_id: str) -> bool:
    from .queue import get_operator_review_queue

    q = get_operator_review_queue(limit=100)
    ids = {row.get("intake_id") for row in q.get("queue") or []}
    return intake_id in ids


def _cote_reflects_intake(intake_id: str) -> bool:
    """Per-intake: COTE latest signal matches this intake's storage-backed custody."""
    try:
        from .intake import _latest_intake_custody_signal

        signal = _latest_intake_custody_signal()
        if signal.get("latest_intake_id") != intake_id:
            return False
        rec = load_intake_record(intake_id, persist_recovery=False)
        storage_status = str(rec.get("custody_status") or (rec.get("upload_integrity") or {}).get("custody_status") or "")
        return storage_status == str(signal.get("latest_custody_status") or "")
    except (FileNotFoundError, ValueError, OSError):
        return False


def retention_check(intake_id: str) -> Dict[str, Any]:
    """Operator retention proof — disk vs index vs queue vs COTE."""
    from .inventory import is_ghost_intake

    idir = intake_dir(intake_id)
    ij = intake_json_path(intake_id)
    receipt = load_audit_receipt(intake_id)
    on_disk = hash_uploads_on_disk(intake_id)

    clf_path = classification_path(intake_id)
    record: Dict[str, Any] = {}
    try:
        record = load_intake_record(intake_id, persist_recovery=False)
    except (FileNotFoundError, ValueError, OSError):
        record = {}
    ui = record.get("upload_integrity") or {}
    expected = int(ui.get("expected_file_count") or 0)
    received = int(ui.get("received_file_count") or 0)
    persisted = int(ui.get("persisted_file_count") or 0)
    verified = int(ui.get("verified_file_count") or 0)
    rejected = int(ui.get("rejected_file_count") or 0)
    duplicate = int(ui.get("duplicate_file_count") or 0)
    failed = int(ui.get("failed_file_count") or 0)
    meta_count = int(record.get("file_count") or len(record.get("files") or []))
    disk_count = len(on_disk)
    counts_match = (
        expected == received == persisted == verified == disk_count and failed == 0
    )
    ghost_intake = is_ghost_intake(intake_id, record=record)
    expected_on_disk = max(expected, verified, persisted, meta_count)
    file_hashes_match = audit_hashes_match(intake_id, on_disk=on_disk) and not ghost_intake
    if expected_on_disk > 0 and disk_count == 0:
        file_hashes_match = False
    upload_files_found = disk_count > 0
    ok = (
        idir.is_dir()
        and ij.is_file()
        and upload_files_found
        and receipt is not None
        and file_hashes_match
        and counts_match
        and not ghost_intake
        and not (expected_on_disk > 0 and disk_count == 0)
    )
    return {
        "ok": ok,
        "intake_id": intake_id,
        "write_root": str(resolved_write_root()),
        "read_root": str(resolved_read_root()),
        "intake_dir_exists": idir.is_dir(),
        "intake_json_exists": ij.is_file(),
        "upload_files_found": upload_files_found,
        "upload_file_count": disk_count,
        "file_hashes_match": file_hashes_match,
        "ghost_intake": ghost_intake,
        "classification_exists": clf_path.is_file(),
        "audit_receipt_exists": receipt is not None,
        "queue_visible": _queue_contains_intake(intake_id),
        "cote_visible": _cote_reflects_intake(intake_id),
        "files_on_disk": on_disk,
        "audit_receipt": receipt,
        "custody_status": record.get("custody_status") or ui.get("custody_status"),
        "count_breakdown": {
            "expected_file_count": expected,
            "received_file_count": received,
            "persisted_file_count": persisted,
            "verified_file_count": verified,
            "rejected_file_count": rejected,
            "duplicate_file_count": duplicate,
            "failed_file_count": failed,
            "on_disk_file_count": disk_count,
        },
        "counts_match": counts_match,
        "integrity_mismatch": bool(ui.get("integrity_mismatch")) or not counts_match or not file_hashes_match,
        "hash_mismatch_detected": not file_hashes_match,
    }


def scan_retention_at_startup(*, force: bool = False) -> Dict[str, Any]:
    """Count disk inventory; CRITICAL log when index and filesystem disagree."""
    global _STARTUP_SCAN
    try:
        from .durable_root import initialize_mount_probe

        initialize_mount_probe()
    except Exception as exc:
        logger.critical("[durable_root] mount probe init failed: %s", exc)
    if _STARTUP_SCAN is not None and not force:
        return dict(_STARTUP_SCAN)
    disk_ids = set(list_intake_ids(limit=500))
    index_ids = set(index_intake_ids(tail_lines=500))
    only_disk = sorted(disk_ids - index_ids)
    only_index = sorted(index_ids - disk_ids)

    intake_json_count = 0
    file_count = 0
    for iid in disk_ids:
        if intake_json_path(iid).is_file():
            intake_json_count += 1
        uploads = intake_dir(iid) / "uploads"
        if uploads.is_dir():
            from .file_durability import is_upload_payload_file

            file_count += sum(1 for p in uploads.iterdir() if p.is_file() and is_upload_payload_file(p.name))

    report = {
        "write_root": str(resolved_write_root()),
        "read_root": str(resolved_read_root()),
        "intakes_root": str(intakes_root().resolve()),
        "index_jsonl": str(index_jsonl().resolve()),
        "intake_directories": len(disk_ids),
        "intake_json_files": intake_json_count,
        "upload_files": file_count,
        "index_tail_unique_ids": len(index_ids),
        "only_on_disk_not_in_index": only_disk[:50],
        "only_in_index_not_on_disk": only_index[:50],
        "index_disk_agree": not only_disk and not only_index,
    }

    global _LAST_INVENTORY
    inventory = {
        "intake_directories": len(disk_ids),
        "intake_json_files": intake_json_count,
        "upload_files": file_count,
    }
    if _LAST_INVENTORY is not None:
        for key in ("intake_directories", "intake_json_files", "upload_files"):
            prev = int(_LAST_INVENTORY.get(key) or 0)
            cur = int(inventory.get(key) or 0)
            if cur < prev:
                emit_sev1_data_loss_suspected(
                    f"Durable inventory dropped for {key}: {prev} -> {cur}",
                    detail={"key": key, "previous": prev, "current": cur, "root": report["write_root"]},
                )
    _LAST_INVENTORY = inventory

    if only_disk or only_index:
        emit_sev1_data_loss_suspected(
            "Index and durable disk disagree at startup",
            detail={
                "only_on_disk": len(only_disk),
                "only_in_index": len(only_index),
                "write_root": report["write_root"],
            },
        )
        logger.critical(
            "[retention] index and disk disagree dirs=%s json=%s files=%s "
            "only_disk=%s only_index=%s root=%s",
            len(disk_ids),
            intake_json_count,
            file_count,
            len(only_disk),
            len(only_index),
            report["write_root"],
        )
    else:
        logger.info(
            "[retention] startup scan dirs=%s json=%s files=%s root=%s",
            len(disk_ids),
            intake_json_count,
            file_count,
            report["write_root"],
        )

    try:
        from .reconcile import recover_uncommitted_intakes

        recovery = recover_uncommitted_intakes(limit=500)
        report["startup_recovery"] = recovery
        logger.info(
            "[retention] startup recovery completed recovered=%s",
            recovery.get("recovered_count", 0),
        )
    except Exception as exc:
        report["startup_recovery"] = {"ok": False, "error": str(exc)}
        logger.critical("[retention] startup recovery failed: %s", exc)

    try:
        from services.runtime_boot import log_boot

        status = "ok" if report["index_disk_agree"] else "critical"
        log_boot(
            "intake_retention",
            status,
            f"dirs={len(disk_ids)} files={file_count} agree={report['index_disk_agree']}"[:200],
        )
    except Exception:
        pass

    try:
        from .hash_ledger import ledger_orphans
        from .inventory import detect_ghost_intakes

        orphans = ledger_orphans(limit=500)
        report["hash_ledger_orphans"] = orphans[:25]
        report["hash_ledger_orphan_count"] = len(orphans)
        if orphans:
            emit_sev1_data_loss_suspected(
                f"Hash ledger orphans: {len(orphans)} file(s) missing on disk",
                detail={"samples": orphans[:5]},
            )
        ghosts = detect_ghost_intakes(limit=200)
        report["ghost_intakes"] = ghosts
        report["ghost_intake_count"] = len(ghosts)
        if ghosts:
            emit_sev1_data_loss_suspected(
                f"Ghost intakes at startup: {len(ghosts)}",
                detail={"ghosts": ghosts[:10]},
            )
    except Exception as exc:
        report["hash_ledger_orphan_count"] = 0
        report["ghost_intake_count"] = 0
        logger.warning("startup ghost/ledger scan failed: %s", exc)

    try:
        from .proof_gate import build_live_boot_status, detect_cockpit_zero_after_recent_success, live_disk_scan

        report["live_scan"] = live_disk_scan()
        live_boot = build_live_boot_status()
        report["live_boot_status"] = live_boot.get("status")
        report["healthy"] = bool(live_boot.get("ok"))
        report["forensic_proof_ok"] = bool(live_boot.get("forensic_proof_ok"))
        if int(report.get("ghost_intake_count") or 0) > 0:
            report["healthy"] = False
        if not report["healthy"]:
            emit_sev1_data_loss_suspected(
                "Startup reconciliation: upload visibility not healthy",
                detail={
                    "index_disk_agree": report["index_disk_agree"],
                    "live_boot_status": report.get("live_boot_status"),
                    "upload_files": file_count,
                },
            )
        detect_cockpit_zero_after_recent_success()
    except Exception as exc:
        report["live_scan_error"] = str(exc)
        report["healthy"] = False

    _STARTUP_SCAN = report
    return report


def last_startup_retention_scan() -> Optional[Dict[str, Any]]:
    return dict(_STARTUP_SCAN) if _STARTUP_SCAN else None


def retention_diagnostics_overlay(*, queue_depth: Optional[int] = None) -> Dict[str, Any]:
    """Extra fields for operator intake diagnostics — live inventory, not boot cache."""
    from .integrity import latest_integrity_mismatch_from_records
    from .inventory import build_intake_inventory, verify_inventory_agreement
    from .storage import all_intake_ids

    inv = build_intake_inventory()
    startup = last_startup_retention_scan()
    agreement = verify_inventory_agreement(
        inventory=inv,
        queue_depth=queue_depth,
        retention_scan=inv,
    )
    recent_records: List[Dict[str, Any]] = []
    for iid in all_intake_ids(limit=15):
        try:
            recent_records.append(load_intake_record(iid, persist_recovery=False))
        except (FileNotFoundError, ValueError, OSError):
            continue
    mismatch = latest_integrity_mismatch_from_records(recent_records)
    live_scan_status = agreement.get("live_scan_status") or ("healthy" if agreement.get("ok") else "degraded")
    return {
        "write_root": str(resolved_write_root()),
        "read_root": str(resolved_read_root()),
        "roots_match": resolved_write_root() == resolved_read_root(),
        "inventory": inv,
        "retention_scan": dict(inv),
        "startup_retention_snapshot": startup,
        "inventory_agreement": agreement,
        "live_scan_status": live_scan_status,
        "latest_integrity_mismatch": mismatch,
    }

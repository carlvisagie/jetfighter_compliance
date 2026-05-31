"""
Upload success proof gate — customer HTTP success only when intake is immediately discoverable.

Hard rule: upload may fail loudly but NEVER appear successful then vanish.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_PUBLIC_GATE_FAILURE = (
    "Your files could not be verified on secure storage. "
    "Please try again or contact support@keepyourcontracts.com."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def live_disk_scan(*, intake_id: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    """
    Live filesystem inventory — never cached. Counts from canonical inventory module.
    """
    from .inventory import build_intake_inventory
    from .retention import hash_uploads_on_disk
    from .storage import index_intake_ids, intake_dir, intake_json_path, list_intake_ids

    inv = build_intake_inventory(limit=limit, intake_id=intake_id)
    if intake_id:
        iids = [intake_id.strip()]
    else:
        iids = list_intake_ids(limit=limit)

    index_ids = set(index_intake_ids(tail_lines=max(limit, 500)))
    intakes: List[Dict[str, Any]] = []
    total_bytes = 0

    for iid in iids:
        idir = intake_dir(iid)
        uploads = idir / "uploads"
        on_disk = hash_uploads_on_disk(iid)
        file_names = sorted(on_disk.keys())
        bytes_on_disk = 0
        if uploads.is_dir():
            for name in file_names:
                try:
                    bytes_on_disk += (uploads / name).stat().st_size
                except OSError:
                    pass
        total_bytes += bytes_on_disk
        intakes.append(
            {
                "intake_id": iid,
                "intake_dir": str(idir.resolve()),
                "intake_json_exists": intake_json_path(iid).is_file(),
                "upload_file_count": len(file_names),
                "upload_file_names": file_names,
                "upload_bytes": bytes_on_disk,
                "in_index": iid in index_ids,
                "file_hashes": on_disk,
            }
        )

    return {
        **inv,
        "upload_bytes": total_bytes,
        "intakes": intakes,
    }


def _queue_or_archive_visible(intake_id: str) -> bool:
    from .queue import get_operator_review_queue
    from .storage import load_intake_record

    active = get_operator_review_queue(limit=200, include_archived=False, persist_recovery=False)
    active_ids = {str(r.get("intake_id") or "") for r in active.get("queue") or []}
    if intake_id in active_ids:
        return True
    archived = get_operator_review_queue(limit=200, include_archived=True, persist_recovery=False)
    archived_ids = {str(r.get("intake_id") or "") for r in archived.get("queue") or []}
    if intake_id in archived_ids:
        return True
    try:
        rec = load_intake_record(intake_id, persist_recovery=False)
        if str(rec.get("review_status") or "") == "archived":
            return True
    except (FileNotFoundError, ValueError, OSError):
        pass
    return False


def _operator_file_endpoints_ok(intake_id: str, saved_files: List[Dict[str, Any]]) -> tuple[bool, List[str]]:
    """Verify download/view delivery paths return readable files (same as HTTP 200 endpoints)."""
    from .operator_files import resolve_intake_upload_path

    failures: List[str] = []
    for entry in saved_files:
        name = str(entry.get("name") or "")
        if not name:
            continue
        try:
            path = resolve_intake_upload_path(intake_id, name)
            if not path.is_file() or path.stat().st_size <= 0:
                failures.append(f"{name}:not_readable")
                continue
            with path.open("rb") as fh:
                if not fh.read(1):
                    failures.append(f"{name}:empty")
        except Exception:
            failures.append(name)
    return len(failures) == 0 and bool(saved_files), failures


def _file_access_verified(intake_id: str, saved_files: List[Dict[str, Any]]) -> tuple[bool, List[str]]:
    from .operator_files import resolve_intake_upload_path

    failures: List[str] = []
    for entry in saved_files:
        name = str(entry.get("name") or "")
        if not name:
            continue
        try:
            path = resolve_intake_upload_path(intake_id, name)
            if not path.is_file():
                failures.append(name)
        except Exception:
            failures.append(name)
    return len(failures) == 0 and bool(saved_files), failures


def _intake_integrity_proof_ok(intake_id: str) -> bool:
    """Read-only integrity check — does not append incidents."""
    from .retention import audit_hashes_match, load_audit_receipt, hash_uploads_on_disk
    from .storage import intake_json_path, latest_index_row
    from .transactions import intake_commit_complete

    on_disk = hash_uploads_on_disk(intake_id)
    if not on_disk:
        return False
    if not intake_json_path(intake_id).is_file():
        return False
    if not load_audit_receipt(intake_id):
        return False
    if not audit_hashes_match(intake_id, on_disk=on_disk):
        return False
    if not latest_index_row(intake_id):
        return False
    return intake_commit_complete(intake_id)


def evaluate_upload_proof_gate(
    intake_id: str,
    *,
    saved_files: List[Dict[str, Any]],
    verified_file_count: int,
) -> Dict[str, Any]:
    """
    Verify intake is discoverable via every required subsystem before customer success.
    """
    from services.durable_storage import active_data_root

    from .operator_files import list_intake_files_for_operator
    from .retention import retention_check
    from .storage import intake_dir, latest_index_row

    data_root = active_data_root().resolve()
    write_path = str((intake_dir(intake_id) / "uploads").resolve())

    live = live_disk_scan(intake_id=intake_id)
    intake_row = (live.get("intakes") or [{}])[0]
    live_count = int(intake_row.get("upload_file_count") or 0)
    live_scan_confirmed = live_count >= verified_file_count and verified_file_count > 0

    index_row = latest_index_row(intake_id)
    index_visible = index_row is not None

    queue_or_archive_visible = _queue_or_archive_visible(intake_id)

    retention = retention_check(intake_id)
    retention_visible = (
        bool(retention.get("ok"))
        and bool(retention.get("upload_files_found"))
        and bool(retention.get("file_hashes_match"))
        and bool(retention.get("audit_receipt_exists"))
        and not bool(retention.get("ghost_intake"))
        and int(retention.get("upload_file_count") or 0) >= verified_file_count
    )

    file_list_ok = False
    file_list_failures: List[str] = []
    try:
        listing = list_intake_files_for_operator(intake_id)
        docs = list(listing.get("documents") or [])
        accessible = [d for d in docs if d.get("accessible")]
        file_list_ok = len(accessible) >= verified_file_count
        if not file_list_ok:
            file_list_failures = [
                str(d.get("stored_filename") or "")
                for d in docs
                if not d.get("accessible")
            ]
    except Exception as exc:
        file_list_failures = [str(exc)]

    file_access_verified, access_failures = _file_access_verified(intake_id, saved_files)
    download_view_ok, endpoint_failures = _operator_file_endpoints_ok(intake_id, saved_files)

    integrity_ok = _intake_integrity_proof_ok(intake_id)

    quarantine_ok = False
    quarantine_detail: Dict[str, Any] = {}
    try:
        from .quarantine import load_quarantine_manifest, mirror_intake_uploads

        quarantine_detail = mirror_intake_uploads(intake_id)
        manifest = load_quarantine_manifest(intake_id)
        quarantine_ok = bool(manifest) and int(manifest.get("file_count") or 0) >= verified_file_count
    except Exception as exc:
        quarantine_detail = {"ok": False, "error": str(exc)}

    checks = {
        "live_scan_confirmed": live_scan_confirmed,
        "index_visible": index_visible,
        "queue_or_archive_visible": queue_or_archive_visible,
        "retention_visible": retention_visible,
        "file_list_resolves": file_list_ok,
        "file_access_verified": file_access_verified,
        "download_view_endpoints_ok": download_view_ok,
        "audit_receipt_exists": bool(retention.get("audit_receipt_exists")),
        "integrity_proof_passed": integrity_ok,
        "quarantine_mirror_ok": quarantine_ok,
    }
    proof_gate_passed = all(checks.values())

    return {
        "intake_id": intake_id,
        "proof_gate_passed": proof_gate_passed,
        "data_root": str(data_root),
        "write_path": write_path,
        "live_scan_confirmed": live_scan_confirmed,
        "queue_or_archive_visible": queue_or_archive_visible,
        "retention_visible": retention_visible,
        "file_access_verified": file_access_verified,
        "verified_file_count": verified_file_count,
        "live_upload_file_count": live_count,
        "checks": checks,
        "failures": {
            "live_scan": [] if live_scan_confirmed else ["disk_count_mismatch"],
            "index": [] if index_visible else ["index_row_missing"],
            "queue": [] if queue_or_archive_visible else ["not_in_queue_or_archive"],
            "retention": [] if retention_visible else ["retention_check_failed"],
            "file_list": file_list_failures,
            "file_access": access_failures,
            "download_view": endpoint_failures,
            "integrity": [] if integrity_ok else ["integrity_disagreement"],
            "quarantine": [] if quarantine_ok else [quarantine_detail.get("error") or "quarantine_mirror_failed"],
        },
        "retention_check": retention,
        "live_scan": live,
        "quarantine": quarantine_detail,
        "evaluated_at_utc": _utc_now(),
    }


def _emit_proof_gate_incident(intake_id: str, gate: Dict[str, Any]) -> None:
    from .forensic_reconcile import IntegrityDisagreement, append_integrity_incident

    failed = [k for k, v in (gate.get("checks") or {}).items() if not v]
    detail = f"Upload proof gate failed: {', '.join(failed)} failures={gate.get('failures')}"
    append_integrity_incident(
        IntegrityDisagreement(
            subsystem="proof_gate",
            intake_id=intake_id,
            evidence_id=None,
            issue_code="upload_proof_gate_failed",
            detail=detail[:2000],
            detected_at=_utc_now(),
            severity="critical",
        )
    )
    logger.critical("[SEV-1] upload_proof_gate_failed intake=%s failed=%s", intake_id, failed)
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "intake",
            "upload_proof_gate_failed",
            message=intake_id,
            metadata={"intake_id": intake_id, "failed_checks": failed, **gate.get("checks", {})},
            severity="critical",
        )
    except Exception:
        pass
    try:
        from .telemetry import emit_intake_event

        emit_intake_event(
            "upload_proof_gate_failed",
            message=f"SEV-1 proof gate failed for {intake_id}",
            metadata={"intake_id": intake_id, "failed_checks": failed},
        )
    except Exception:
        pass


def require_upload_proof_gate(
    intake_id: str,
    *,
    saved_files: List[Dict[str, Any]],
    verified_file_count: int,
) -> Dict[str, Any]:
    """
    Raise HTTP 500 + SEV-1 incident when proof gate fails.
    Never allow customer-visible success without passing gate.
    """
    gate = evaluate_upload_proof_gate(
        intake_id,
        saved_files=saved_files,
        verified_file_count=verified_file_count,
    )
    if gate.get("proof_gate_passed"):
        return gate

    _emit_proof_gate_incident(intake_id, gate)
    raise HTTPException(
        status_code=500,
        detail=_PUBLIC_GATE_FAILURE,
        headers={"X-KYC-Error-Code": "upload_proof_gate_failed"},
    )


def build_live_boot_status() -> Dict[str, Any]:
    """
    Live boot status — disk scan + forensic proof + upload pipeline severity.
    Never uses cached startup snapshot alone.
    """
    from services.durable_storage import get_storage_status, intake_upload_allowed
    from services.runtime_boot import boot_log_snapshot, is_safe_mode, schedulers_enabled

    from .inventory import build_intake_inventory, detect_ghost_intakes, verify_inventory_agreement
    from .queue import get_operator_review_queue

    inv = build_intake_inventory()
    live = live_disk_scan()
    q = get_operator_review_queue(limit=100, persist_recovery=False)
    queue_depth = int(q.get("queue_depth") or 0)
    agreement = verify_inventory_agreement(
        inventory=inv,
        queue_depth=queue_depth,
        live_boot={"intake_directories": inv["intake_directories"], "upload_files": inv["upload_files"], "live_scan": live},
    )

    forensic: Dict[str, Any] = {}
    try:
        from .forensic_reconcile import build_integrity_proof, load_integrity_incidents

        forensic = build_integrity_proof(limit=500, use_cache=False)
        incident_count = len(load_integrity_incidents(tail=200))
    except Exception as exc:
        forensic = {"ok": False, "error": str(exc)}
        incident_count = 0

    upload_metrics: Dict[str, Any] = {}
    try:
        from .intake import intake_flow_metrics

        upload_metrics = intake_flow_metrics()
    except Exception:
        upload_metrics = {}

    storage = get_storage_status()
    dirs = int(inv.get("intake_directories") or 0)
    files = int(inv.get("upload_files") or 0)
    index_agree = bool(inv.get("index_disk_agree"))
    forensic_ok = bool(forensic.get("ok", False))
    upload_severity = str(upload_metrics.get("upload_node_severity") or "green")
    incidents = incident_count + int(forensic.get("integrity_incident_count") or 0)
    inventory_ok = bool(agreement.get("ok"))

    ghosts = detect_ghost_intakes(limit=200)
    ghost_count = len(ghosts)

    healthy = (
        inventory_ok
        and index_agree
        and forensic_ok
        and upload_severity != "red"
        and queue_depth == int(inv.get("pending_review_count") or 0)
        and ghost_count == 0
        and (int(inv.get("upload_files") or 0) > 0 or int(inv.get("pending_review_count") or 0) == 0)
    )
    if not intake_upload_allowed() and storage.get("upload_block_reason"):
        healthy = False

    boot = boot_log_snapshot()
    status = "healthy" if healthy else "critical"
    if upload_severity == "red" or not index_agree or not inventory_ok:
        status = "critical"
    elif not forensic_ok:
        status = "critical"
    elif upload_severity == "amber" and not inventory_ok:
        status = "degraded"

    live_scan_status = agreement.get("live_scan_status") or ("healthy" if inventory_ok else "degraded")
    if ghost_count > 0:
        live_scan_status = "critical"
        status = "critical"
        healthy = False
    elif healthy and inventory_ok:
        live_scan_status = "healthy"
        status = "healthy"

    return {
        "ok": healthy,
        "status": status,
        "live_scan_status": live_scan_status,
        "scan_type": "live",
        "scan_at_utc": inv.get("scan_at_utc"),
        "safe_mode_effective": is_safe_mode(),
        "schedulers_enabled": schedulers_enabled(),
        "data_root": inv.get("data_root"),
        "intake_directories": dirs,
        "upload_files": files,
        "pending_review_count": int(inv.get("pending_review_count") or 0),
        "queue_depth": queue_depth,
        "index_disk_agree": index_agree,
        "inventory_agreement": agreement,
        "forensic_proof_ok": forensic_ok,
        "forensic_proof": forensic,
        "integrity_incident_count": incidents,
        "ghost_intake_count": ghost_count,
        "ghost_intakes": ghosts[:25],
        "upload_node_severity": upload_severity,
        "upload_pipeline": upload_metrics,
        "storage": storage,
        "live_scan": live,
        "inventory": inv,
        "boot_log": boot,
        "startup_retention_snapshot": boot.get("entries"),
        "cockpit_may_show_green": healthy and upload_severity == "green",
    }


def detect_cockpit_zero_after_recent_success(*, window_minutes: int = 120) -> Optional[Dict[str, Any]]:
    """
    SEV-1 when durable disk has upload files but operator queue depth is zero
    while intakes remain pending review — visibility collapse after success.
    """
    from .queue import get_operator_review_queue
    from .storage import list_intake_ids, load_intake_record, is_pending_review

    live = live_disk_scan(limit=100)
    files = int(live.get("upload_files") or 0)
    dirs = int(live.get("intake_directories") or 0)
    if files <= 0 and dirs <= 0:
        return None

    q = get_operator_review_queue(limit=100)
    queue_depth = int(q.get("queue_depth") or 0)
    pending_on_disk = 0
    for iid in list_intake_ids(limit=100):
        try:
            rec = load_intake_record(iid, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        uploads = int(rec.get("file_count") or len(rec.get("files") or []))
        if uploads > 0 and is_pending_review(rec.get("review_status")):
            pending_on_disk += 1

    if files > 0 and pending_on_disk > 0 and queue_depth == 0:
        detail = {
            "upload_files_on_disk": files,
            "intake_directories": dirs,
            "pending_on_disk": pending_on_disk,
            "queue_depth": queue_depth,
            "issue": "cockpit_zero_while_pending_uploads_on_disk",
        }
        from .forensic_reconcile import IntegrityDisagreement, append_integrity_incident

        append_integrity_incident(
            IntegrityDisagreement(
                subsystem="cockpit",
                intake_id=None,
                evidence_id=None,
                issue_code="cockpit_zero_upload_visibility",
                detail=str(detail),
                detected_at=_utc_now(),
                severity="critical",
            )
        )
        return detail
    return None

"""Customer paperwork pipeline — single source of truth, no silent empty states."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.durable_storage import (
    founding_beta_upload_allowed,
    get_storage_status,
    upload_block_reason,
)

logger = logging.getLogger(__name__)

PIPELINE_ID = "customer_paperwork"
PIPELINE_LABEL = "Customer paperwork intake"


def surface_pipeline_failure(
    code: str,
    message: str,
    *,
    severity: str = "error",
    intake_id: str = "",
    **metadata: Any,
) -> None:
    """Every failure: logged, operator-telemetry surfaced, never swallowed."""
    meta: Dict[str, Any] = {
        "pipeline_id": PIPELINE_ID,
        "code": code,
        "severity": severity,
        **metadata,
    }
    if intake_id:
        meta["intake_id"] = intake_id

    log_fn = logger.critical if severity in ("critical", "sev1") else logger.error
    log_fn("[pipeline] %s %s meta=%s", code, message, meta)

    try:
        from services.runtime_boot import log_boot

        log_boot(f"pipeline_{code}", severity, message[:200])
    except Exception:
        pass

    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "founding_beta",
            code,
            message=message[:300],
            metadata=meta,
        )
    except Exception:
        pass

    try:
        from .telemetry import emit_beta_event

        emit_beta_event(
            "pipeline_failure",
            message=message[:300],
            metadata=meta,
        )
    except Exception:
        pass


def emit_sev1_data_loss_suspected(
    reason: str,
    *,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Unexplained disappearance or index/disk divergence — SEV-1."""
    surface_pipeline_failure(
        "sev1_data_loss_suspected",
        reason,
        severity="sev1",
        **(detail or {}),
    )


def compute_queue_truth(
    *,
    diag: Dict[str, Any],
    rows: List[Dict[str, Any]],
    pending: List[Dict[str, Any]],
    storage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    When queue is empty the operator must know exactly why.
    Filesystem counts in diag are authoritative; index is advisory only.
    """
    storage = storage or get_storage_status()
    dirs = int(diag.get("intake_directories_found") or 0)
    uploads = int(diag.get("upload_files_on_disk") or 0)
    pending_count = len(pending)
    row_count = len(rows)
    scan = diag.get("retention_scan") or {}

    if not founding_beta_upload_allowed():
        reason = upload_block_reason() or "durable_storage_unavailable"
        return {
            "pipeline_id": PIPELINE_ID,
            "pipeline_label": PIPELINE_LABEL,
            "queue_empty": True,
            "queue_empty_reason": reason,
            "queue_empty_message": _reason_message(reason, storage=storage),
            "uploads_blocked": True,
            "filesystem_intake_dirs": dirs,
            "filesystem_upload_files": uploads,
        }

    if scan.get("index_disk_agree") is False:
        od = len(scan.get("only_on_disk_not_in_index") or [])
        oi = len(scan.get("only_in_index_not_on_disk") or [])
        if od or oi:
            emit_sev1_data_loss_suspected(
                "Index and durable disk disagree",
                detail={
                    "only_on_disk": od,
                    "only_in_index": oi,
                    "write_root": scan.get("write_root"),
                },
            )
            return {
                "pipeline_id": PIPELINE_ID,
                "pipeline_label": PIPELINE_LABEL,
                "queue_empty": pending_count <= 0,
                "queue_empty_reason": "index_disk_mismatch",
                "queue_empty_message": (
                    f"Durable disk and intake index disagree ({od} on disk only, "
                    f"{oi} in index only). Filesystem is canonical — reconcile before trusting queue."
                ),
                "filesystem_intake_dirs": dirs,
                "filesystem_upload_files": uploads,
                "index_disk_agree": False,
            }

    if dirs <= 0 and uploads <= 0:
        return {
            "pipeline_id": PIPELINE_ID,
            "pipeline_label": PIPELINE_LABEL,
            "queue_empty": True,
            "queue_empty_reason": "no_customer_paperwork_on_disk",
            "queue_empty_message": "No customer paperwork on durable storage yet.",
            "filesystem_intake_dirs": 0,
            "filesystem_upload_files": 0,
        }

    if dirs > 0 and row_count == 0:
        surface_pipeline_failure(
            "queue_metadata_unreadable",
            f"{dirs} intake folder(s) on disk but queue could not load metadata",
            severity="critical",
            intake_dirs=dirs,
        )
        return {
            "pipeline_id": PIPELINE_ID,
            "pipeline_label": PIPELINE_LABEL,
            "queue_empty": True,
            "queue_empty_reason": "metadata_unreadable",
            "queue_empty_message": (
                f"Found {dirs} intake folder(s) on disk but queue could not load metadata — "
                "check intake.json permissions or corruption."
            ),
            "filesystem_intake_dirs": dirs,
            "filesystem_upload_files": uploads,
        }

    if dirs > 0 and pending_count == 0 and uploads > 0:
        return {
            "pipeline_id": PIPELINE_ID,
            "pipeline_label": PIPELINE_LABEL,
            "queue_empty": True,
            "queue_empty_reason": "no_pending_reviews",
            "queue_empty_message": (
                f"Found {dirs} intake(s) and {uploads} file(s) on durable disk but none "
                "awaiting operator review (archived or approved)."
            ),
            "filesystem_intake_dirs": dirs,
            "filesystem_upload_files": uploads,
        }

    if pending_count > 0:
        return {
            "pipeline_id": PIPELINE_ID,
            "pipeline_label": PIPELINE_LABEL,
            "queue_empty": False,
            "queue_empty_reason": None,
            "queue_empty_message": None,
            "filesystem_intake_dirs": dirs,
            "filesystem_upload_files": uploads,
            "pending_review_count": pending_count,
        }

    return {
        "pipeline_id": PIPELINE_ID,
        "pipeline_label": PIPELINE_LABEL,
        "queue_empty": True,
        "queue_empty_reason": "queue_filtered_empty",
        "queue_empty_message": "Queue has no visible rows after filters — check review_status values.",
        "filesystem_intake_dirs": dirs,
        "filesystem_upload_files": uploads,
    }


def _reason_message(reason: str, *, storage: Dict[str, Any]) -> str:
    messages = {
        "KYC_DATA_not_configured": (
            "Durable storage not configured (KYC_DATA missing). Customer uploads are hard-disabled."
        ),
        "KYC_DATA_invalid": "KYC_DATA path is invalid. Customer uploads are hard-disabled.",
        "KYC_DATA_points_to_ephemeral_repo_data": (
            "KYC_DATA points at ephemeral repo data/. Customer uploads are hard-disabled in production."
        ),
        "KYC_DATA_not_writable": "KYC_DATA path is not writable. Customer uploads are hard-disabled.",
        "founding_beta_intake_disabled": "Customer paperwork intake is disabled.",
        "durable_storage_unavailable": "Durable storage unavailable. Customer uploads are hard-disabled.",
    }
    if reason in messages:
        return messages[reason]
    op = storage.get("operator_message")
    if op:
        return str(op)
    return f"Uploads blocked: {reason}"

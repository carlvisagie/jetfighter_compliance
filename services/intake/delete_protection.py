"""Delete protection — intake upload files cannot be removed without explicit policy."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

ALLOWED_RETENTION_POLICIES = frozenset(
    {
        "operator_approved_retention_expired",
        "legal_hold_release",
        "gdpr_erasure_verified",
    }
)


class UploadDeleteForbidden(Exception):
    """Raised when an intake upload file delete is not authorized."""


def assert_upload_file_delete_allowed(
    intake_id: str,
    filename: str,
    *,
    operator_authorized: bool,
    retention_policy: Optional[str] = None,
    audit_event_written: bool = False,
) -> None:
    """
    Gate for any future cleanup path. Unreviewed uploads must never be deleted.
    Requires operator auth + named retention policy + audit event.
    """
    from .storage import load_intake_record, is_pending_review

    if not operator_authorized:
        raise UploadDeleteForbidden("operator authorization required")
    policy = (retention_policy or "").strip()
    if policy not in ALLOWED_RETENTION_POLICIES:
        raise UploadDeleteForbidden(f"retention policy not allowed: {policy!r}")
    if not audit_event_written:
        raise UploadDeleteForbidden("audit event required before intake file deletion")

    try:
        rec = load_intake_record(intake_id, persist_recovery=False)
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise UploadDeleteForbidden("intake record unavailable") from exc

    review_status = str(rec.get("review_status") or rec.get("status") or "")
    if is_pending_review(review_status) and policy != "gdpr_erasure_verified":
        raise UploadDeleteForbidden(
            f"unreviewed intake {intake_id} cannot be deleted under policy {policy}"
        )

    ui = rec.get("upload_integrity") or {}
    if ui.get("integrity_mismatch") and policy != "gdpr_erasure_verified":
        raise UploadDeleteForbidden("integrity-mismatch intake requires forensic review before deletion")


def delete_upload_file_protected(
    intake_id: str,
    filename: str,
    path: Path,
    *,
    operator_authorized: bool,
    retention_policy: str,
    audit_event_written: bool,
) -> None:
    """Only supported deletion entry point for intake uploads/."""
    assert_upload_file_delete_allowed(
        intake_id,
        filename,
        operator_authorized=operator_authorized,
        retention_policy=retention_policy,
        audit_event_written=audit_event_written,
    )
    if not path.is_file():
        return
    path.unlink()
    logger.warning(
        "Protected delete intake=%s file=%s policy=%s",
        intake_id,
        filename,
        retention_policy,
    )


def http_guard_upload_delete(intake_id: str, filename: str, **kwargs) -> None:
    try:
        assert_upload_file_delete_allowed(intake_id, filename, **kwargs)
    except UploadDeleteForbidden as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
            headers={"X-KYC-Error-Code": "intake_delete_forbidden"},
        ) from exc

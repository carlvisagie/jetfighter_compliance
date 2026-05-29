"""Production durable data policy — customer intake must not use ephemeral disk."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException

from .config import DATA, ROOT
from .production import is_production

logger = logging.getLogger(__name__)

_PUBLIC_UPLOAD_DETAIL = (
    "Paperwork upload is not available right now. "
    "Please contact support@keepyourcontracts.com and we will help you submit securely."
)


def repo_default_data_dir() -> Path:
    return (ROOT / "data").resolve()


def kyc_data_env_value() -> Optional[str]:
    return (os.getenv("KYC_DATA") or "").strip() or None


def resolved_kyc_data_path() -> Optional[Path]:
    raw = kyc_data_env_value()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def is_data_root_ephemeral_in_production() -> bool:
    """True when production is using the repo-local data dir (lost on Render redeploy)."""
    if not is_production():
        return False
    try:
        return active_data_root() == repo_default_data_dir()
    except OSError:
        return True


def is_durable_storage_configured() -> bool:
    """
    Durable storage requires explicit KYC_DATA to a writable path.
    In production the path must not be the default repo data/ directory.
    """
    path = resolved_kyc_data_path()
    if path is None:
        return False
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".kyc_storage_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        return False
    if is_production() and path == repo_default_data_dir():
        return False
    return True


def intake_pipeline_enabled() -> bool:
    from services.intake.mode import is_intake_mode

    return is_intake_mode()


def founding_beta_intake_enabled() -> bool:
    """Deprecated alias — use intake_pipeline_enabled."""
    return intake_pipeline_enabled()


def _writable_data_root(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".kyc_storage_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def canonical_storage_ready() -> bool:
    """All environments: customer paperwork requires a writable non-ephemeral data root."""
    if is_durable_storage_configured():
        return True
    root = active_data_root()
    if root == repo_default_data_dir():
        return False
    return _writable_data_root(root)


def intake_upload_allowed() -> bool:
    if not intake_pipeline_enabled():
        return False
    return canonical_storage_ready()


def founding_beta_upload_allowed() -> bool:
    """Deprecated alias — use intake_upload_allowed."""
    return intake_upload_allowed()


def upload_block_reason() -> Optional[str]:
    if not intake_pipeline_enabled():
        return "intake_pipeline_disabled"
    if canonical_storage_ready():
        return None
    if not kyc_data_env_value() and active_data_root() == repo_default_data_dir():
        return "durable_storage_required_set_KYC_DATA"
    if not kyc_data_env_value():
        return "KYC_DATA_not_configured"
    path = resolved_kyc_data_path()
    if path is None:
        return "KYC_DATA_invalid"
    if path == repo_default_data_dir():
        return "KYC_DATA_points_to_ephemeral_repo_data"
    if not is_durable_storage_configured():
        return "KYC_DATA_not_writable"
    return None


def log_storage_boot_status() -> None:
    reason = upload_block_reason()
    allowed = intake_upload_allowed()
    msg = (
        f"data_root={active_data_root()} "
        f"durable_storage_configured={is_durable_storage_configured()} "
        f"intake_uploads_enabled={allowed}"
    )
    if reason:
        msg += f" upload_block_reason={reason}"
    logger.info("[storage] %s", msg)
    try:
        from services.runtime_boot import log_boot

        log_boot(
            "storage",
            "ok" if allowed or not is_production() else "blocked",
            msg[:240],
        )
    except Exception:
        pass
    if is_production() and not allowed:
        logger.critical("[storage] intake uploads disabled in production: %s", reason)


def _log_upload_blocked(reason: str) -> None:
    logger.critical("intake_upload_blocked reason=%s data_root=%s", reason, DATA)
    try:
        from services.runtime_boot import log_boot

        log_boot("intake_upload", "blocked", reason[:200])
    except Exception:
        pass
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "intake",
            "intake_storage_unavailable",
            message=reason,
            metadata={"data_root": str(DATA.resolve()), "reason": reason},
        )
    except Exception:
        pass


def require_intake_upload_allowed() -> None:
    reason = upload_block_reason()
    if reason is None:
        return
    _log_upload_blocked(reason)
    raise HTTPException(
        status_code=503,
        detail=_PUBLIC_UPLOAD_DETAIL,
        headers={"X-KYC-Error-Code": "durable_storage_required"},
    )


def require_founding_beta_upload_allowed() -> None:
    """Deprecated alias — use require_intake_upload_allowed."""
    require_intake_upload_allowed()


def reject_demo_order_in_production(order_id: str) -> None:
    oid = (order_id or "").strip().upper()
    if not is_production():
        return
    if oid.startswith("CP-DEMO") or oid.startswith("DEMO-") or oid.startswith("TEST-"):
        raise HTTPException(
            status_code=403,
            detail="Demo and test project creation is disabled in production.",
        )


def active_data_root() -> Path:
    """Live data root (honors KYC_DATA env even when config.DATA was imported earlier)."""
    from services.config import _resolve_data_root

    return _resolve_data_root()


def get_storage_status() -> Dict[str, Any]:
    reason = upload_block_reason()
    kyc = resolved_kyc_data_path()
    root = active_data_root()
    allowed = intake_upload_allowed()
    return {
        "ok": True,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "data_root": str(root),
        "kyc_data_env": kyc_data_env_value(),
        "kyc_data_path": str(kyc) if kyc else None,
        "durable_storage_configured": is_durable_storage_configured(),
        "data_root_ephemeral_in_production": is_data_root_ephemeral_in_production(),
        "intake_pipeline_enabled": intake_pipeline_enabled(),
        "intake_uploads_enabled": allowed,
        "founding_beta_intake_enabled": intake_pipeline_enabled(),
        "founding_beta_uploads_enabled": allowed,
        "upload_block_reason": reason,
        "operator_message": (
            None
            if allowed
            else "Durable paperwork storage not configured — uploads disabled."
        ),
    }

"""Production runtime guards and startup checks (minimal — no new frameworks)."""
import logging
import os
from typing import Any, Dict, List

from fastapi import HTTPException, Request

from .config import DATA, PROJECTS, SETTINGS

logger = logging.getLogger(__name__)

_DEV_INTAKE_SECRET = "dev-dev-dev-dev-dev"


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "").lower() == "production"


def get_public_base_for_checks() -> str:
    from .public_url import get_public_base_url

    return get_public_base_url()


def startup_warnings() -> List[str]:
    warnings: List[str] = []
    if SETTINGS.intake_token_secret == _DEV_INTAKE_SECRET:
        warnings.append("INTAKE_TOKEN_SECRET is default dev value — set a strong secret in production")
    if is_production():
        base = get_public_base_for_checks()
        if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
            warnings.append(f"PUBLIC_BASE_URL not set — intake links use {base}")
        if not os.getenv("OPS_API_KEY"):
            warnings.append("OPS_API_KEY unset — test kickoff routes blocked in production")
        if not os.getenv("OPS_PASSWORD", "").strip():
            warnings.append("OPS_PASSWORD unset — internal UI/API require login or X-Ops-Key")
        if SETTINGS.intake_token_secret == _DEV_INTAKE_SECRET:
            warnings.append("CRITICAL: rotate INTAKE_TOKEN_SECRET before accepting real clients")
        from .durable_storage import intake_upload_allowed, upload_block_reason

        if not intake_upload_allowed():
            warnings.append(
                "CRITICAL: intake uploads disabled — "
                + (upload_block_reason() or "configure KYC_DATA on persistent disk")
            )
    return warnings


def smtp_env_status() -> Dict[str, Any]:
    """Which SMTP env vars are set (never exposes password value)."""
    host = SETTINGS.smtp_host
    user = SETTINGS.smtp_user
    pwd_set = bool(SETTINGS.smtp_pass)
    from_email = SETTINGS.smtp_from_email
    return {
        "smtp_enabled_flag": SETTINGS.smtp_enabled,
        "SMTP_ENABLED": SETTINGS.smtp_enabled,
        "SMTP_HOST": bool(host),
        "SMTP_SERVER": bool(os.getenv("SMTP_SERVER")),
        "SMTP_PORT": SETTINGS.smtp_port,
        "SMTP_USER": bool(user),
        "SMTP_USERNAME": bool(os.getenv("SMTP_USERNAME")),
        "SMTP_PASS": pwd_set,
        "SMTP_PASSWORD": bool(os.getenv("SMTP_PASSWORD")),
        "SMTP_FROM_EMAIL": bool(from_email),
        "SMTP_FROM_NAME": bool(SETTINGS.smtp_from_name),
        "configured": bool(
            SETTINGS.smtp_enabled and host and user and SETTINGS.smtp_pass
        ),
        "missing": _smtp_missing_fields(),
    }


def _smtp_missing_fields() -> list:
    missing = []
    if not SETTINGS.smtp_enabled:
        missing.append("SMTP_ENABLED=true")
    if not SETTINGS.smtp_host:
        missing.append("SMTP_HOST or SMTP_SERVER")
    if not SETTINGS.smtp_user:
        missing.append("SMTP_USER or SMTP_USERNAME")
    if not SETTINGS.smtp_pass:
        missing.append("SMTP_PASS or SMTP_PASSWORD")
    return missing


def readiness_checks() -> Dict[str, Any]:
    from .durable_storage import get_storage_status

    data_ok = DATA.exists() and os.access(str(DATA), os.W_OK)
    projects_ok = PROJECTS.exists()
    base = get_public_base_for_checks()
    storage = get_storage_status()
    return {
        "data_writable": data_ok,
        "projects_dir": projects_ok,
        "public_base_url": base,
        "inquiry_onboarding_active": True,
        "intake_secret_configured": SETTINGS.intake_token_secret != _DEV_INTAKE_SECRET,
        "smtp_configured": smtp_env_status()["configured"],
        "smtp_status": smtp_env_status(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "durable_storage_configured": storage["durable_storage_configured"],
        "intake_uploads_enabled": storage["intake_uploads_enabled"],
        "founding_beta_uploads_enabled": storage.get("founding_beta_uploads_enabled"),
    }


def require_ops_access(request: Request) -> None:
    """Ops routes: session cookie or X-Ops-Key — same contract as ops_auth_middleware."""
    from .ops_auth import (
        auth_contract,
        is_authenticated,
        ops_api_key_configured,
        ops_password_configured,
    )

    if is_authenticated(request):
        return
    if not ops_password_configured() and not ops_api_key_configured():
        raise HTTPException(
            status_code=503,
            detail="OPS_PASSWORD or OPS_API_KEY not configured on server",
        )
    contract = auth_contract()
    raise HTTPException(
        status_code=403,
        detail=(
            "Unauthorized — authenticate via "
            f"{contract['login_endpoint']} (cookie {contract['session_cookie']}) "
            f"or header {contract['api_key_header']}"
        ),
    )


def _timing_safe_equal(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode(), b.encode())


def safe_upload_filename(name: str) -> str:
    from pathlib import Path

    base = Path(name or "").name
    if not base or base in (".", "..") or ".." in base:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


def validate_project_id(project_id: str) -> None:
    if not project_id or not project_id.startswith("P-"):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    pdir = PROJECTS / project_id
    if not pdir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")

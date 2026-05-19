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
        if not SETTINGS.stripe_webhook_secret:
            warnings.append("STRIPE_WEBHOOK_SECRET unset — Stripe payments will not trigger kickoff()")
        base = get_public_base_for_checks()
        if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
            warnings.append(f"PUBLIC_BASE_URL not set — intake links use {base}")
        if not os.getenv("OPS_API_KEY"):
            warnings.append("OPS_API_KEY unset — test kickoff routes blocked in production")
        if SETTINGS.intake_token_secret == _DEV_INTAKE_SECRET:
            warnings.append("CRITICAL: rotate INTAKE_TOKEN_SECRET before accepting real clients")
    if os.getenv("SHOPIFY_WEBHOOK_SECRET"):
        warnings.append("SHOPIFY_WEBHOOK_SECRET still set — remove (Shopify decommissioned)")
    if os.getenv("SHOPIFY_SECRET"):
        warnings.append("SHOPIFY_SECRET still set — remove (unused)")
    return warnings


def readiness_checks() -> Dict[str, Any]:
    data_ok = DATA.exists() and os.access(str(DATA), os.W_OK)
    projects_ok = PROJECTS.exists()
    base = get_public_base_for_checks()
    return {
        "data_writable": data_ok,
        "projects_dir": projects_ok,
        "public_base_url": base,
        "stripe_webhook_configured": bool(SETTINGS.stripe_webhook_secret),
        "intake_secret_configured": SETTINGS.intake_token_secret != _DEV_INTAKE_SECRET,
        "smtp_configured": bool(
            SETTINGS.smtp_enabled and SETTINGS.smtp_host and SETTINGS.smtp_user and SETTINGS.smtp_pass
        ),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


def require_ops_access(request: Request) -> None:
    """Block ops/test kickoff routes in production unless OPS_API_KEY header matches."""
    if not is_production():
        return
    expected = os.getenv("OPS_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=403, detail="Test routes disabled in production")
    provided = request.headers.get("X-Ops-Key") or request.headers.get("x-ops-key")
    if not provided or not _timing_safe_equal(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Ops-Key")


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

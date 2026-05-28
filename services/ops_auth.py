"""
Operator session authentication for internal UI and API routes.
Uses OPS_PASSWORD + OPS_SECRET (or INTAKE_TOKEN_SECRET fallback for signing).
"""
from __future__ import annotations

import hmac
import os
import re
import time
from typing import Optional, Set
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

SESSION_COOKIE = "kyc_ops_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600

# Customer-facing UI (always open)
PUBLIC_UI_EXACT: Set[str] = {
    "/ui/shop.html",
    "/ui/inquiry.html",
    "/ui/intake.html",
    "/ui/upload.html",
    "/ui/login.html",
    "/ui/index.html",
    "/ui/vendor_quote.html",
    "/ui/continue.html",
    "/ui/founding-beta.html",
}

PUBLIC_UI_PREFIXES = (
    "/ui/assets/",
)

# Operator UI (session required)
PROTECTED_UI_EXACT: Set[str] = {
    "/ui/control.html",
    "/ui/memory.html",
    "/ui/command.html",
    "/ui/status.html",
    "/ui/inbox.html",
    "/ui/webhook_test.html",
    "/ui/onboarding_validation.html",
    "/ui/lead_discovery.html",
    "/ui/knowledge.html",
    "/ui/scan.html",
    "/ui/event.html",
    "/ui/new_client.html",
    "/ui/healthz.html",
}

PROTECTED_UI_PREFIXES = (
    "/ui/readiness/",
)

# Public API (customer + health)
PUBLIC_API_PREFIXES = (
    "/healthz",
    "/health/ready",
    "/api/inquiry/",
    "/api/intake/",
    "/api/customer/",
    "/api/founding-beta/",
    "/webhooks/",
)

PUBLIC_API_EXACT: Set[str] = {
    "/api/ops/login",
    "/api/ops/logout",
    "/api/ops/session",
    "/api/ops/boot-status",
}

# Operator / organism / intelligence APIs
PROTECTED_API_PREFIXES = (
    "/api/memory/",
    "/api/ops/",
    "/api/operator/",
    "/api/knowledge/",
    "/api/projects",
    "/api/project/",
    "/api/events/",
    "/api/vendors",
    "/api/rfq/",
    "/api/ping-host.json",
    "/api/coc/event/form",
    "/api/schemas/validate",
    "/api/test-webhook",
    "/events/payment/test",
)

BACKUP_UI_PATTERN = re.compile(
    r"\.bak($|[?#])|\.backup[^/]*\.html($|[?#])|\.pre_[^/]+\.bak($|[?#])",
    re.IGNORECASE,
)


def _signer() -> URLSafeTimedSerializer:
    secret = (
        os.getenv("OPS_SECRET")
        or os.getenv("INTAKE_TOKEN_SECRET")
        or "dev-ops-secret-change-me"
    )
    return URLSafeTimedSerializer(secret, salt="kyc-ops-session")


def ops_password_configured() -> bool:
    return bool(os.getenv("OPS_PASSWORD", "").strip())


def verify_ops_password(password: str) -> bool:
    expected = os.getenv("OPS_PASSWORD", "").strip()
    if not expected:
        return False
    return hmac.compare_digest(password.encode("utf-8"), expected.encode("utf-8"))


def create_session_token() -> str:
    return _signer().dumps({"role": "ops", "ts": int(time.time())})


def verify_session_token(token: str) -> bool:
    if not token:
        return False
    try:
        data = _signer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        return isinstance(data, dict) and data.get("role") == "ops"
    except BadSignature:
        return False


def _valid_api_key(request: Request) -> bool:
    import os as _os

    expected = _os.getenv("OPS_API_KEY", "")
    if not expected:
        return False
    provided = request.headers.get("X-Ops-Key") or request.headers.get("x-ops-key") or ""
    return hmac.compare_digest(provided.encode(), expected.encode())


def is_authenticated(request: Request) -> bool:
    if not ops_password_configured() and not _os_api_key_configured():
        return False
    token = request.cookies.get(SESSION_COOKIE, "")
    if verify_session_token(token):
        return True
    return _valid_api_key(request)


def _os_api_key_configured() -> bool:
    return bool(os.getenv("OPS_API_KEY", "").strip())


def is_blocked_backup_path(path: str) -> bool:
    return bool(BACKUP_UI_PATTERN.search(path))


def is_public_ui_path(path: str) -> bool:
    if path in PUBLIC_UI_EXACT:
        return True
    return any(path.startswith(p) for p in PUBLIC_UI_PREFIXES)


def is_protected_ui_path(path: str) -> bool:
    if path in PROTECTED_UI_EXACT:
        return True
    return any(path.startswith(p) for p in PROTECTED_UI_PREFIXES)


def is_public_api_path(path: str) -> bool:
    if path in PUBLIC_API_EXACT:
        return True
    if path in ("/healthz", "/health/ready"):
        return True
    return any(path.startswith(p) for p in PUBLIC_API_PREFIXES)


def is_protected_api_path(path: str) -> bool:
    if is_public_api_path(path):
        return False
    if path == "/api/evidence/register" or path.startswith("/api/evidence/register"):
        return False
    return any(path.startswith(p) for p in PROTECTED_API_PREFIXES) or path in (
        "/events/payment/test",
    )


def set_session_cookie(response: Response, token: str) -> None:
    from services.production import is_production

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_production(),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def gate_request(request: Request) -> Optional[Response]:
    """Return a Response to short-circuit, or None to continue."""
    path = request.url.path

    if path.startswith("/ui/") and is_blocked_backup_path(path):
        return JSONResponse({"ok": False, "detail": "Not found"}, status_code=404)

    if not ops_password_configured() and not _os_api_key_configured():
        if is_protected_ui_path(path) or is_protected_api_path(path):
            if path.startswith("/ui/") and path.endswith(".html"):
                return RedirectResponse(url="/ui/login.html?error=config", status_code=302)
            return JSONResponse(
                {"ok": False, "detail": "OPS_PASSWORD or OPS_API_KEY not configured"},
                status_code=503,
            )
        return None

    if is_authenticated(request):
        return None

    if is_protected_ui_path(path):
        nxt = quote(path, safe="")
        return RedirectResponse(url=f"/ui/login.html?next={nxt}", status_code=302)

    if is_protected_api_path(path):
        return JSONResponse({"ok": False, "detail": "Unauthorized"}, status_code=403)

    return None

"""Email transport shim — backwards-compatible interface over the email service.

All emails now route through services.communications.email_service which owns
the adapter chain (Resend → SMTP → manual fallback), forensic records, and
telemetry. This module exists solely to preserve the existing import surface
for legacy callers (server.py, engine.py, reports.py, rfq.py, alerts_center.py).

New code should import directly from services.communications.email_service.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from .config import SETTINGS

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Configuration helpers — still used by tests and UI status endpoints
# ---------------------------------------------------------------------------

def resend_is_configured() -> bool:
    return bool(SETTINGS.resend_api_key)


def smtp_is_configured() -> bool:
    return bool(
        SETTINGS.smtp_enabled
        and SETTINGS.smtp_host
        and SETTINGS.smtp_user
        and SETTINGS.smtp_pass
    )


def email_is_configured() -> bool:
    return resend_is_configured() or smtp_is_configured()


# ---------------------------------------------------------------------------
# Public API — all delegate to email_service
# ---------------------------------------------------------------------------

def send_email_with_result(to_email: str, subject: str, html_body: str) -> Dict[str, Any]:
    """Send email and return structured result. Routes through email_service."""
    from services.communications.email_service import send_raw
    return send_raw(to_email, subject, html_body, intent="operational")


def send_email(to_email: str, subject: str, html_body: str) -> None:
    """Send HTML email; raises RuntimeError on unrecoverable failure."""
    result = send_email_with_result(to_email, subject, html_body)
    if not result.get("sent") and not result.get("skipped") and not result.get("manual_fallback_generated"):
        raise RuntimeError(
            result.get("detail") or result.get("reason") or "email send failed"
        )


def send_operator_test_email(to_email: str) -> Dict[str, Any]:
    """Operator-only transport test — exercises whichever provider is live."""
    if not _EMAIL_RE.match((to_email or "").strip()):
        return {"ok": False, "error": "invalid_email"}
    to_email = to_email.strip()
    provider = (
        "Resend" if resend_is_configured()
        else "SMTP" if smtp_is_configured()
        else "none"
    )
    html = (
        f"<h2>KeepYourContracts email test</h2>"
        f"<p>Transport: <strong>{provider}</strong></p>"
        "<p>If you received this, email delivery is working correctly.</p>"
    )
    return send_email_with_result(to_email, "KYC email test — KeepYourContracts", html)

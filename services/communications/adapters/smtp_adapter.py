"""SMTP transport adapter.

Pure SMTP delivery — zero business logic, zero domain imports.
All configuration is passed as arguments; this module owns nothing.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_configured(host: str, user: str, password: str, enabled: bool) -> bool:
    return bool(enabled and host and user and password)


def send(
    to: str,
    subject: str,
    html: str,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
) -> Dict[str, Any]:
    """Send via SMTP STARTTLS. Returns {sent, provider, ...} — never raises."""
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.set_content("HTML email. Please view in an HTML-capable client.")
        msg.add_alternative(html, subtype="html")
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        logger.info("smtp: delivered to %s", to)
        return {"sent": True, "provider": "smtp"}
    except Exception as exc:
        err = type(exc).__name__
        logger.warning("smtp: failed for %s: %s", to, err)
        return {
            "sent": False,
            "provider": "smtp",
            "error": err,
            "detail": str(exc)[:200],
        }

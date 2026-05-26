import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

from .config import SETTINGS

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def smtp_is_configured() -> bool:
    return bool(
        SETTINGS.smtp_enabled
        and SETTINGS.smtp_host
        and SETTINGS.smtp_user
        and SETTINGS.smtp_pass
    )


def _emit(event_type: str, *, success: bool = True, severity: str = "info", message: str = "", metadata: Dict = None):
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "email",
            event_type,
            severity=severity,
            success=success,
            message=message,
            metadata=metadata or {},
        )
    except Exception:
        pass


def send_email(to_email: str, subject: str, html_body: str):
    """Send HTML email when SMTP is enabled; otherwise no-op (used in tests)."""
    result = send_email_with_result(to_email, subject, html_body)
    if result.get("error"):
        raise RuntimeError(result["error"])


def send_email_with_result(to_email: str, subject: str, html_body: str) -> Dict[str, Any]:
    """Send email and return structured result without logging secrets."""
    _emit("send_attempted", metadata={"to": to_email, "subject": subject[:80]})

    if not smtp_is_configured():
        _emit(
            "smtp_unconfigured",
            success=False,
            severity="warning",
            message="SMTP not configured — email skipped",
        )
        return {
            "ok": False,
            "skipped": True,
            "reason": "smtp_unconfigured",
            "to": to_email,
        }

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{SETTINGS.smtp_from_name} <{SETTINGS.smtp_from_email or SETTINGS.smtp_user}>"
        msg["To"] = to_email
        msg.set_content("HTML email. Please view in an HTML-capable client.")
        msg.add_alternative(html_body, subtype="html")
        with smtplib.SMTP(SETTINGS.smtp_host, SETTINGS.smtp_port, timeout=30) as s:
            s.starttls()
            s.login(SETTINGS.smtp_user, SETTINGS.smtp_pass)
            s.send_message(msg)
        _emit("send_success", metadata={"to": to_email})
        return {"ok": True, "sent": True, "to": to_email}
    except Exception as e:
        err = type(e).__name__
        _emit(
            "send_failed",
            success=False,
            severity="error",
            message=str(e)[:200],
            metadata={"to": to_email, "error_type": err},
        )
        logger.warning("Email send failed to %s: %s", to_email, err)
        try:
            from services.alerts import alert_organism_failure

            alert_organism_failure("smtp_failure", message=str(e)[:200], metadata={"to": to_email, "error_type": err})
        except Exception:
            pass
        return {"ok": False, "sent": False, "to": to_email, "error": err, "detail": str(e)[:200]}


def send_operator_test_email(to_email: str) -> Dict[str, Any]:
    """Operator-only SMTP connectivity test."""
    if not _EMAIL_RE.match((to_email or "").strip()):
        return {"ok": False, "error": "invalid_email"}
    to_email = to_email.strip()
    html = (
        "<h2>KeepYourContracts SMTP test</h2>"
        "<p>This is an operator test message from the KYC compliance backend.</p>"
        "<p>If you received this, SMTP transport is working.</p>"
    )
    return send_email_with_result(to_email, "KYC SMTP test — KeepYourContracts", html)

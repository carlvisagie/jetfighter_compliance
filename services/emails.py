"""Email transport layer.

Priority order:
  1. Resend API  (RESEND_API_KEY set)   — REST, reliable, no SMTP flakiness
  2. SMTP        (SMTP_ENABLED + creds)  — fallback for legacy / self-hosted

Gmail App Passwords get silently revoked. Resend is the production path.
"""
import json
import logging
import re
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict

from .config import SETTINGS

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Configuration checks
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
# Internal telemetry
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Transport: Resend REST API
# ---------------------------------------------------------------------------

def _send_via_resend(to_email: str, subject: str, html_body: str, *, from_email: str = "") -> Dict[str, Any]:
    """Send via Resend API — no SMTP, no App Passwords, no silent revocations."""
    from_addr = (
        from_email
        or SETTINGS.resend_from_email
        or SETTINGS.smtp_from_email
        or f"{SETTINGS.smtp_from_name} <noreply@keepyourcontracts.com>"
    )
    payload = json.dumps({
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {SETTINGS.resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        email_id = body.get("id")
        logger.info("Resend: sent to %s (id=%s)", to_email, email_id)
        return {"ok": True, "sent": True, "provider": "resend", "to": to_email, "resend_id": email_id}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        logger.warning("Resend HTTP %s for %s: %s", exc.code, to_email, raw[:300])
        return {
            "ok": False, "sent": False, "provider": "resend",
            "to": to_email, "http_status": exc.code,
            "error": "resend_http_error", "detail": raw[:300],
        }
    except Exception as exc:
        logger.warning("Resend request failed for %s: %s", to_email, exc)
        return {
            "ok": False, "sent": False, "provider": "resend",
            "to": to_email, "error": type(exc).__name__, "detail": str(exc)[:200],
        }


# ---------------------------------------------------------------------------
# Transport: SMTP fallback
# ---------------------------------------------------------------------------

def _send_via_smtp(to_email: str, subject: str, html_body: str) -> Dict[str, Any]:
    """Send via SMTP — kept as fallback only."""
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
        logger.info("SMTP: sent to %s", to_email)
        return {"ok": True, "sent": True, "provider": "smtp", "to": to_email}
    except Exception as exc:
        err = type(exc).__name__
        logger.warning("SMTP send failed to %s: %s", to_email, err)
        return {
            "ok": False, "sent": False, "provider": "smtp",
            "to": to_email, "error": err, "detail": str(exc)[:200],
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_email_with_result(to_email: str, subject: str, html_body: str) -> Dict[str, Any]:
    """Send email and return structured result. Tries Resend first, SMTP second."""
    _emit("send_attempted", metadata={"to": to_email, "subject": subject[:80]})

    # --- Resend (primary) ---
    if resend_is_configured():
        result = _send_via_resend(to_email, subject, html_body)
        if result.get("sent"):
            _emit("send_success", metadata={"to": to_email, "provider": "resend"})
            return result
        # Resend failed — log but don't alert unless SMTP also fails
        logger.warning("Resend failed for %s — trying SMTP fallback if configured", to_email)

    # --- SMTP (fallback) ---
    if smtp_is_configured():
        result = _send_via_smtp(to_email, subject, html_body)
        if result.get("sent"):
            _emit("send_success", metadata={"to": to_email, "provider": "smtp"})
            return result

    # --- Both failed / nothing configured ---
    if not email_is_configured():
        _emit("smtp_unconfigured", success=False, severity="warning",
              message="No email provider configured — email skipped")
        return {"ok": False, "skipped": True, "reason": "no_email_provider_configured", "to": to_email}

    # At least one provider was tried but failed
    _emit("send_failed", success=False, severity="error",
          message="All email providers failed",
          metadata={"to": to_email})
    try:
        from services.alerts import alert_organism_failure
        alert_organism_failure(
            "email_all_providers_failed",
            message=f"Both Resend and SMTP failed for {to_email}",
            metadata={"to": to_email},
        )
    except Exception:
        pass
    return {"ok": False, "sent": False, "reason": "all_providers_failed", "to": to_email}


def send_email(to_email: str, subject: str, html_body: str):
    """Send HTML email; raises on failure (used where exceptions are expected)."""
    result = send_email_with_result(to_email, subject, html_body)
    if not result.get("sent") and not result.get("skipped"):
        raise RuntimeError(result.get("detail") or result.get("error") or "email send failed")


def send_operator_test_email(to_email: str) -> Dict[str, Any]:
    """Operator-only connectivity test — hits whichever provider is configured."""
    if not _EMAIL_RE.match((to_email or "").strip()):
        return {"ok": False, "error": "invalid_email"}
    to_email = to_email.strip()
    provider = "Resend" if resend_is_configured() else "SMTP" if smtp_is_configured() else "none"
    html = (
        f"<h2>KeepYourContracts email test</h2>"
        f"<p>Transport: <strong>{provider}</strong></p>"
        "<p>If you received this, email delivery is working correctly.</p>"
    )
    return send_email_with_result(to_email, "KYC email test — KeepYourContracts", html)

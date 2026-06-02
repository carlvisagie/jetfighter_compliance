"""Email service — single outbound email boundary for KYC.

All emails leave the system through this module. Business logic lives here.
Providers are adapters: they own transport only, no domain knowledge.

Architecture:
    send_outreach_invite()     → acquisition outreach to a discovered lead
    send_payment_link()        → payment link after intake classification
    send_upload_confirmation() → receipt acknowledgment after paperwork upload
    send_operator_alert()      → operational alert to the operator inbox
    send_raw()                 → legacy/operational emails (digest, RFQ, etc.)

Internal dispatch (_dispatch):
    1. Try Resend adapter   (primary)
    2. Try SMTP adapter     (fallback)
    3. Generate manual copy (last resort — organism never blocks)
    4. Record delivery      (forensic JSONL, every attempt)
    5. Emit telemetry
    6. Return EmailResult dict

EmailResult fields:
    ok                      True unless address invalid / product not found
    sent                    True only when a provider confirmed delivery
    manual_fallback_generated  True when copyable fallback was built
    fallback_used           True when non-primary provider delivered
    provider_attempted      list of provider names tried
    provider_succeeded      name or None
    message_id              MSG-xxxx
    message_hash            SHA-256 dedup key
    intent                  one of the intent strings above
    to                      recipient address
    lead_id / intake_id / project_id   attribution (empty string if N/A)
    timestamp_utc           ISO-8601
    manual_copy_text        operator-copyable plain text (if fallback)
    manual_copy_html        original HTML (if fallback)
    operator_instruction    instructions for operator (if fallback)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .adapters import manual_adapter, resend_adapter, smtp_adapter
from .delivery_record import (
    load_delivery_log,
    message_hash,
    new_message_id,
    record_delivery,
)

logger = logging.getLogger(__name__)

# Re-export for callers that only need the log reader
__all__ = [
    "send_outreach_invite",
    "send_payment_link",
    "send_upload_confirmation",
    "send_operator_alert",
    "send_raw",
    "load_delivery_log",
]


# ---------------------------------------------------------------------------
# Config read-through — no business logic, adapter config only
# ---------------------------------------------------------------------------

def _resend_cfg() -> Dict[str, str]:
    from services.config import SETTINGS
    return {
        "api_key": SETTINGS.resend_api_key,
        "from_addr": (
            SETTINGS.resend_from_email
            or SETTINGS.smtp_from_email
            or f"{SETTINGS.smtp_from_name} <noreply@keepyourcontracts.com>"
        ),
    }


def _smtp_cfg() -> Dict[str, Any]:
    from services.config import SETTINGS
    return {
        "enabled": SETTINGS.smtp_enabled,
        "host": SETTINGS.smtp_host,
        "port": SETTINGS.smtp_port,
        "user": SETTINGS.smtp_user,
        "password": SETTINGS.smtp_pass,
        "from_addr": (
            f"{SETTINGS.smtp_from_name} "
            f"<{SETTINGS.smtp_from_email or SETTINGS.smtp_user}>"
        ),
    }


# ---------------------------------------------------------------------------
# Core dispatch — adapters only below this line
# ---------------------------------------------------------------------------

def _dispatch(
    to: str,
    subject: str,
    html: str,
    *,
    intent: str,
    plain: str = "",
    lead_id: str = "",
    intake_id: str = "",
    project_id: str = "",
) -> Dict[str, Any]:
    """Route through Resend → SMTP → Manual and record every outcome."""
    msg_id = new_message_id()
    msg_hash = message_hash(to, subject, html)
    providers_attempted: List[str] = []
    provider_succeeded: Optional[str] = None
    fallback_used: bool = False
    manual_generated: bool = False
    provider_response: Dict[str, Any] = {}
    sent: bool = False
    manual_result: Dict[str, Any] = {}

    _tel("send_attempted", {"to": to, "intent": intent, "subject": subject[:80]})

    # 1 — Resend (primary)
    rc = _resend_cfg()
    if resend_adapter.is_configured(rc["api_key"]):
        providers_attempted.append("resend")
        r = resend_adapter.send(
            to, subject, html,
            from_addr=rc["from_addr"],
            api_key=rc["api_key"],
        )
        provider_response["resend"] = r
        if r.get("sent"):
            sent = True
            provider_succeeded = "resend"

    # 2 — SMTP (fallback)
    if not sent:
        sc = _smtp_cfg()
        if smtp_adapter.is_configured(sc["host"], sc["user"], sc["password"], sc["enabled"]):
            providers_attempted.append("smtp")
            r = smtp_adapter.send(
                to, subject, html,
                host=sc["host"], port=sc["port"],
                user=sc["user"], password=sc["password"],
                from_addr=sc["from_addr"],
            )
            provider_response["smtp"] = r
            if r.get("sent"):
                sent = True
                provider_succeeded = "smtp"
                fallback_used = len(providers_attempted) > 1

    # 3 — Manual fallback (only when providers were tried but failed)
    # If no providers are configured at all → skipped (configuration state, not failure)
    if not sent and providers_attempted:
        manual_generated = True
        manual_result = manual_adapter.generate(to, subject, html, plain)
        provider_response["manual"] = {
            "manual_fallback_generated": True,
            "operator_instruction": manual_result.get("operator_instruction", ""),
        }

    # 4 — Forensic delivery record
    rec = record_delivery(
        msg_id=msg_id,
        msg_hash=msg_hash,
        intent=intent,
        to=to,
        subject=subject,
        sent=sent,
        provider_attempted=providers_attempted,
        provider_succeeded=provider_succeeded,
        fallback_used=fallback_used,
        manual_fallback_generated=manual_generated,
        lead_id=lead_id,
        intake_id=intake_id,
        project_id=project_id,
        provider_response=provider_response,
    )

    # 5 — Telemetry + organism alert on total delivery failure
    if sent:
        _tel("send_success", {"to": to, "intent": intent, "provider": provider_succeeded})
    elif not providers_attempted:
        _tel(
            "smtp_unconfigured",  # kept for backward-compat with existing telemetry monitors
            {"to": to, "intent": intent},
            success=False,
            severity="warning",
            message="No email provider configured",
        )
    else:
        last_err = _last_error(providers_attempted, provider_response)
        _tel(
            "send_failed",
            {"to": to, "intent": intent, "providers": providers_attempted, "error_type": last_err},
            success=False,
            severity="error",
            message=last_err,
        )
        try:
            from services.alerts import alert_organism_failure
            alert_organism_failure(
                "email_all_providers_failed",
                message=f"All email providers failed for {to} (intent={intent}): {last_err}",
                metadata={"to": to, "intent": intent, "providers": providers_attempted},
            )
        except Exception:
            pass

    # 6 — Build result
    result: Dict[str, Any] = {
        "ok": True,          # organism always continues
        "sent": sent,
        "manual_fallback_generated": manual_generated,
        "fallback_used": fallback_used,
        "provider_attempted": providers_attempted,
        "provider_succeeded": provider_succeeded,
        "message_id": msg_id,
        "message_hash": msg_hash,
        "intent": intent,
        "to": to,
        "lead_id": lead_id,
        "intake_id": intake_id,
        "project_id": project_id,
        "timestamp_utc": rec.get("timestamp_utc", ""),
        "provider_response": provider_response,
    }

    if manual_generated:
        result["manual_copy_text"] = manual_result.get("copy_text", "")
        result["manual_copy_html"] = manual_result.get("copy_html", "")
        result["manual_copy_subject"] = manual_result.get("copy_subject", "")
        result["manual_copy_to"] = manual_result.get("copy_to", "")
        result["operator_instruction"] = manual_result.get("operator_instruction", "")
        result["skipped"] = False
        result["reason"] = "manual_fallback"
    elif not sent and not providers_attempted:
        result["skipped"] = True
        result["reason"] = "no_email_provider_configured"
    else:
        result["skipped"] = False

    return result


def _tel(
    event: str,
    metadata: Dict,
    *,
    success: bool = True,
    severity: str = "info",
    message: str = "",
) -> None:
    try:
        from services.memory.telemetry import emit_telemetry
        emit_telemetry(
            "email", event,
            severity=severity, success=success, message=message, metadata=metadata,
        )
    except Exception:
        pass


def _last_error(providers_attempted: List[str], provider_response: Dict) -> str:
    for name in reversed(providers_attempted):
        pr = provider_response.get(name, {})
        err = pr.get("detail") or pr.get("error") or ""
        if err:
            return err
    return "unknown_error"


# ---------------------------------------------------------------------------
# Public: intent-specific send methods
# ---------------------------------------------------------------------------

def send_outreach_invite(
    *,
    to_email: str,
    company_name: str = "",
    contact_name: str = "",
    invite_url: str = "",
    upload_url: str = "",
    lead_id: str = "",
) -> Dict[str, Any]:
    """Send acquisition outreach to a discovered lead.

    KYC owns: intent, template, recipient validation, attribution tracking.
    """
    if not to_email or "@" not in to_email:
        return _invalid("no_email_address", "outreach_invite")

    from services.email_utils import build_invitation_email_text
    draft = build_invitation_email_text(
        company_name=company_name,
        contact_name=contact_name,
        invite_url=invite_url,
        upload_url=upload_url,
    )
    result = _dispatch(
        to_email,
        draft["subject"],
        draft["html"],
        intent="outreach_invite",
        plain=draft.get("body", ""),
        lead_id=lead_id,
    )
    result["draft"] = draft
    return result


def send_payment_link(
    *,
    to_email: str,
    customer_name: str = "",
    company: str = "",
    product_id: str,
    intake_id: str = "",
) -> Dict[str, Any]:
    """Send payment link after intake classification.

    Payment link (PayPal URL) is always included in the manual fallback
    so the operator can forward it if both providers are unavailable.
    """
    if not to_email or "@" not in to_email:
        return _invalid("no_email_address", "payment_link")

    from services.intake.payment_email import (
        PAYMENT_EMAIL_SUBJECT,
        build_manual_payment_email_text,
        build_payment_link_email_html,
    )
    from services.intake.payment_products import get_payment_product

    product = get_payment_product(product_id)
    if not product:
        return _invalid("invalid_product", "payment_link", extra={"product_id": product_id})

    html = build_payment_link_email_html(
        customer_name=customer_name,
        company=company,
        product=product,
    )
    plain = build_manual_payment_email_text(product=product).get("body", "")

    result = _dispatch(
        to_email.strip(),
        PAYMENT_EMAIL_SUBJECT,
        html,
        intent="payment_link",
        plain=plain,
        intake_id=intake_id,
    )
    result["product_id"] = product_id
    result["product_title"] = product.get("title")
    result["paypal_url"] = product.get("paypal_url")
    return result


def send_upload_confirmation(
    *,
    to_email: str,
    intake_id: str = "",
    company: str = "",
) -> Dict[str, Any]:
    """Confirm document receipt to the customer immediately after upload."""
    if not to_email or "@" not in to_email:
        return _invalid("no_email_address", "upload_confirmation")

    name_line = company.strip() or "there"
    subject = "KeepYourContracts — We Received Your Documents"
    html = (
        "<div style='font-family:Arial,sans-serif;max-width:600px;'>"
        f"<p>Hi {name_line},</p>"
        "<p>We have received your paperwork and our team is reviewing it. "
        "You will hear from us shortly with next steps.</p>"
        "<p>If you have additional documents to share, just reply to this email.</p>"
        "<p>Best,<br>KeepYourContracts</p>"
        "</div>"
    )
    return _dispatch(to_email, subject, html, intent="upload_confirmation", intake_id=intake_id)


def send_operator_alert(
    *,
    to_email: str,
    subject: str,
    html_body: str,
) -> Dict[str, Any]:
    """Send an operational alert to the operator.

    Manual fallback is always generated so no alert is ever silently dropped.
    """
    if not to_email or "@" not in to_email:
        return _invalid("no_operator_email", "operator_alert")
    return _dispatch(to_email, subject, html_body, intent="operator_alert")


def send_raw(
    to_email: str,
    subject: str,
    html_body: str,
    *,
    intent: str = "operational",
) -> Dict[str, Any]:
    """Low-level send for legacy operational emails (digest, RFQ, welcome, etc.).

    Routes through the same adapter chain and forensic record as all other sends.
    """
    if not to_email or "@" not in to_email:
        return _invalid("no_email_address", intent)
    return _dispatch(to_email, subject, html_body, intent=intent)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _invalid(reason: str, intent: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": False,
        "sent": False,
        "skipped": True,
        "reason": reason,
        "manual_fallback_generated": False,
        "intent": intent,
    }
    if extra:
        result.update(extra)
    return result

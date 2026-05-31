"""Shared email template utilities — used by acquisition outreach and intake notification."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

INVITATION_SUBJECT = "KeepYourContracts — Free Compliance Paperwork Review"


def build_invitation_email_text(
    *,
    company_name: str = "",
    contact_name: str = "",
    invite_url: str = "",
    upload_url: str = "",
) -> Dict[str, str]:
    """Build outreach invitation email content."""
    name_line = contact_name.strip() or "there"
    company_line = f" at {company_name.strip()}" if company_name.strip() else ""
    cta_url = upload_url or invite_url

    subject = INVITATION_SUBJECT
    body = (
        f"Hi {name_line},\n\n"
        f"I came across your work{company_line} and wanted to reach out.\n\n"
        "We offer a free compliance paperwork review — you upload whatever you already have "
        "(policies, spreadsheets, audit questionnaires, anything), and we tell you exactly where "
        "you stand and what the fastest path to compliance looks like.\n\n"
        "No need to have perfect paperwork. Messy or partial is absolutely fine — that's the point.\n\n"
        f"Start here (takes about 2 minutes):\n{cta_url}\n\n"
        "If you have questions, just reply.\n\n"
        "Best,\nKeepYourContracts"
    )
    html = (
        "<div style='font-family:Arial,sans-serif;max-width:600px;'>"
        f"<p>Hi {name_line},</p>"
        f"<p>I came across your work{company_line} and wanted to reach out.</p>"
        "<p>We offer a <strong>free compliance paperwork review</strong> — you upload whatever you already have "
        "(policies, spreadsheets, audit questionnaires, anything), and we tell you exactly where "
        "you stand and what the fastest path to compliance looks like.</p>"
        "<p>No need to have perfect paperwork. Messy or partial is absolutely fine — that's the point.</p>"
        f"<p><a href='{cta_url}' style='background:#1a56db;color:#fff;padding:10px 20px;border-radius:5px;text-decoration:none;'>Start free review (2 min)</a></p>"
        "<p>If you have questions, just reply.</p>"
        "<p>Best,<br>KeepYourContracts</p>"
        "</div>"
    )
    return {"subject": subject, "body": body, "html": html, "cta_url": cta_url}


def send_invitation_email(
    *,
    to_email: str,
    company_name: str = "",
    contact_name: str = "",
    invite_url: str = "",
    upload_url: str = "",
) -> Dict[str, Any]:
    """Send the outreach invitation email via SMTP. Returns structured send result."""
    if not to_email or "@" not in to_email:
        return {"ok": False, "sent": False, "skipped": True, "reason": "no_email_address"}

    draft = build_invitation_email_text(
        company_name=company_name,
        contact_name=contact_name,
        invite_url=invite_url,
        upload_url=upload_url,
    )
    from services.emails import send_email_with_result

    result = send_email_with_result(to_email, draft["subject"], draft["html"])
    result["draft"] = draft
    if result.get("sent"):
        logger.info("Invitation email sent to %s (lead outreach)", to_email)
    else:
        logger.warning(
            "Invitation email NOT sent to %s — reason: %s",
            to_email,
            result.get("reason") or result.get("error") or "smtp_unconfigured",
        )
    return result

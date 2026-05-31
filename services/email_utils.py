"""Shared email template utilities — used by acquisition outreach and intake notification."""
from __future__ import annotations

from typing import Any, Dict


INVITATION_SUBJECT = "KeepYourContracts — Free Compliance Paperwork Review"


def build_invitation_email_text(
    *,
    company_name: str = "",
    contact_name: str = "",
    invite_url: str = "",
    upload_url: str = "",
) -> Dict[str, str]:
    """Draft outreach / invitation email for operator to send to an approved lead."""
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
        f"Start here (takes about 2 minutes): {cta_url}\n\n"
        "If you have questions, just reply.\n\n"
        "Best,\nKeepYourContracts"
    )
    return {"subject": subject, "body": body, "cta_url": cta_url}

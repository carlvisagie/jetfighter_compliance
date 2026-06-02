"""Manual copy fallback adapter.

When all delivery providers are unavailable, this adapter generates an
operator-copyable message so the organism never silently drops an email.
Zero business logic — pure text transformation.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NL = re.compile(r"\n{3,}")


def generate(
    to: str,
    subject: str,
    html: str,
    plain: str = "",
) -> Dict[str, Any]:
    """Generate operator-copyable fallback. Returns {sent=False, manual_fallback_generated=True, ...}."""
    if not plain:
        plain = _TAG_RE.sub("", html)
        plain = _MULTI_NL.sub("\n\n", plain).strip()

    logger.warning(
        "manual fallback generated for %s — subject: %s — "
        "no email provider is available; operator must send manually",
        to,
        subject,
    )
    return {
        "sent": False,
        "provider": "manual",
        "manual_fallback_generated": True,
        "copy_subject": subject,
        "copy_to": to,
        "copy_text": plain,
        "copy_html": html,
        "operator_instruction": (
            f"All email providers are unavailable. "
            f"Please send manually to: {to}\n"
            f"Subject: {subject}"
        ),
    }

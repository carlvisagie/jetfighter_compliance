"""Backward-compat shim — canonical: services.intake.messaging."""
from services.intake.messaging import (
    BETA_HEADLINE,
    BETA_INTRO,
    BETA_REASSURANCE,
    BETA_STYLE,
    BETA_UPLOAD_LIST,
    intake_messaging_blocks as beta_messaging_blocks,
    intake_outreach_snippet as beta_outreach_snippet,
)

__all__ = [
    "BETA_HEADLINE",
    "BETA_INTRO",
    "BETA_REASSURANCE",
    "BETA_STYLE",
    "BETA_UPLOAD_LIST",
    "beta_messaging_blocks",
    "beta_outreach_snippet",
]

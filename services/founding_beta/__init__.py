"""Backward-compat shim — canonical implementation in services.intake."""
from services.intake.mode import is_intake_mode as is_founding_beta_mode
from services.intake.messaging import (
    BETA_HEADLINE,
    BETA_REASSURANCE,
    intake_messaging_blocks as beta_messaging_blocks,
    intake_outreach_snippet as beta_outreach_snippet,
)
from services.intake.stats import get_intake_status as get_founding_beta_status
from services.intake.telemetry import emit_intake_event as emit_beta_event

__all__ = [
    "is_founding_beta_mode",
    "beta_messaging_blocks",
    "beta_outreach_snippet",
    "BETA_HEADLINE",
    "BETA_REASSURANCE",
    "get_founding_beta_status",
    "emit_beta_event",
]

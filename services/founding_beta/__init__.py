"""Founding Beta Organism Validation Mode — real paperwork over vanity metrics."""
from .mode import is_founding_beta_mode
from .messaging import beta_messaging_blocks, beta_outreach_snippet
from .stats import get_founding_beta_status
from .telemetry import emit_beta_event

__all__ = [
    "is_founding_beta_mode",
    "beta_messaging_blocks",
    "beta_outreach_snippet",
    "get_founding_beta_status",
    "emit_beta_event",
]

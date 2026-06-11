"""Customer intake pipeline — upload-first paperwork, no login wall."""
from .mode import is_intake_mode
from .messaging import intake_messaging_blocks, intake_outreach_snippet
from .stats import get_intake_status
from .telemetry import emit_intake_event, emit_lifecycle_event, LIFECYCLE_EVENTS

__all__ = [
    "is_intake_mode",
    "intake_messaging_blocks",
    "intake_outreach_snippet",
    "get_intake_status",
    "emit_intake_event",
    "emit_lifecycle_event",
    "LIFECYCLE_EVENTS",
]

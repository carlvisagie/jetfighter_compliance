"""Intake pipeline mode flag — validation over revenue."""
from __future__ import annotations

import os


def is_intake_mode() -> bool:
    """When true, organism optimizes for real uploads and quiet operational burden."""
    return os.getenv("KYC_FOUNDING_PILOT_MODE", "true").lower() in ("1", "true", "yes", "on")

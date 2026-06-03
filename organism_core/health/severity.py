"""Severity + HealthState enums — single canonical vocabulary."""
from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Severity reported by a single Check."""

    INFO = "info"
    AMBER = "amber"
    RED = "red"

    @classmethod
    def coerce(cls, value) -> "Severity":
        if isinstance(value, cls):
            return value
        s = str(value or "").lower()
        if s in ("red", "critical", "error", "fail"):
            return cls.RED
        if s in ("amber", "warn", "warning", "degraded"):
            return cls.AMBER
        return cls.INFO


class HealthState(str, Enum):
    """Overall organism health derived from all checks."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"

    def label(self) -> str:
        return self.value

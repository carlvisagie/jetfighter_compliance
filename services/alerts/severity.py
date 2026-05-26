"""Alert severity levels for operational nervous system."""
from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    INFO = 10
    IMPORTANT = 20
    HIGH = 30
    CRITICAL = 40


SEVERITY_LABELS = {
    Severity.INFO: "INFO",
    Severity.IMPORTANT: "IMPORTANT",
    Severity.HIGH: "HIGH",
    Severity.CRITICAL: "CRITICAL",
}

SEVERITY_EMOJI = {
    Severity.INFO: "ℹ️",
    Severity.IMPORTANT: "📌",
    Severity.HIGH: "🔔",
    Severity.CRITICAL: "🚨",
}


def parse_severity(value: str | int | Severity) -> Severity:
    if isinstance(value, Severity):
        return value
    if isinstance(value, int):
        for s in Severity:
            if s.value == value:
                return s
    key = str(value or "INFO").upper().strip()
    return getattr(Severity, key, Severity.INFO)

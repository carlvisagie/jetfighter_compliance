"""Compliance intelligence telemetry."""
from __future__ import annotations

from typing import Any, Dict, Optional

SUBSYSTEM = "compliance_intel"


def emit(
    event_type: str,
    *,
    success: bool = True,
    severity: str = "info",
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            SUBSYSTEM,
            event_type,
            severity=severity,
            success=success,
            message=message,
            metadata=metadata or {},
        )
    except Exception:
        pass

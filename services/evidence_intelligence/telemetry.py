"""Evidence intelligence telemetry → central memory."""
from __future__ import annotations

from typing import Any, Dict, Optional


SUBSYSTEM = "evidence_intelligence"


def emit(
    event_type: str,
    *,
    project_id: str = "",
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
            project_id=project_id,
            message=message,
            metadata=metadata or {},
        )
    except Exception:
        pass

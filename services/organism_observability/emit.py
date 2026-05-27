"""Canonical organism telemetry emit — central memory + optional timeline."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .registry import learning_goal_for

logger = logging.getLogger(__name__)

_write_failures = 0


def write_failure_count() -> int:
    return _write_failures


def organism_emit(
    subsystem: str,
    event_type: str,
    *,
    learning_goal: str = "",
    severity: str = "info",
    entity_id: str = "",
    project_id: str = "",
    lead_id: str = "",
    artifact_id: str = "",
    duration_ms: Optional[int] = None,
    success: bool = True,
    error_code: str = "",
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    link_timeline: bool = False,
    timeline_event_type: str = "",
    base: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Emit telemetry with learning_goal; never raises."""
    global _write_failures
    goal = learning_goal or learning_goal_for(subsystem, event_type)
    meta = dict(metadata or {})
    meta["learning_goal"] = goal

    rec = None
    try:
        from services.memory.telemetry import emit_telemetry

        rec = emit_telemetry(
            subsystem,
            event_type,
            severity=severity,
            entity_id=entity_id,
            project_id=project_id,
            lead_id=lead_id,
            artifact_id=artifact_id,
            duration_ms=duration_ms,
            success=success,
            error_code=error_code,
            message=message,
            metadata=meta,
            base=base,
        )
    except Exception as e:
        logger.warning("organism_emit failed %s/%s: %s", subsystem, event_type, e)
        rec = None

    if rec is None:
        _write_failures += 1
        try:
            from services.memory.telemetry import emit_telemetry

            emit_telemetry(
                "organism_health",
                "telemetry_write_failed",
                severity="error",
                success=False,
                message=f"{subsystem}/{event_type}",
                metadata={"learning_goal": "Detect silent telemetry loss", "subsystem": subsystem},
                base=base,
            )
        except Exception:
            pass
        return None

    if link_timeline and entity_id:
        try:
            from services.memory.timeline import append_timeline

            append_timeline(
                entity_id,
                timeline_event_type or event_type,
                subsystem,
                project_id or lead_id or artifact_id or "",
                {"learning_goal": goal, **meta},
                base=base,
            )
        except Exception as e:
            logger.debug("Timeline link skipped: %s", e)

    return rec

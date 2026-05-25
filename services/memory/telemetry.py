"""Organism telemetry — support subsystems emit signals; central memory is canonical truth."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .entity_graph import memory_dir, utc_now

logger = logging.getLogger(__name__)

TELEMETRY_FILE = "telemetry.jsonl"


def _path(base: Optional[Path] = None) -> Path:
    d = memory_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    return d / TELEMETRY_FILE


def new_telemetry_id() -> str:
    return f"TEL-{uuid.uuid4().hex[:12]}"


def emit_telemetry(
    subsystem: str,
    event_type: str,
    *,
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
    base: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Append telemetry event. Never raises — transport/output layers stay non-canonical."""
    try:
        rec = {
            "telemetry_id": new_telemetry_id(),
            "subsystem": subsystem,
            "event_type": event_type,
            "severity": severity,
            "entity_id": entity_id or None,
            "project_id": project_id or None,
            "lead_id": lead_id or None,
            "artifact_id": artifact_id or None,
            "duration_ms": duration_ms,
            "success": success,
            "error_code": error_code or None,
            "message": message[:500] if message else "",
            "observed_at_utc": utc_now(),
            "metadata": metadata or {},
        }
        path = _path(base)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            from .adaptive_signals import ingest_telemetry_event

            ingest_telemetry_event(rec, base=base)
        except Exception as e:
            logger.debug("Adaptive signal ingest skipped: %s", e)
        return rec
    except Exception as e:
        logger.warning("Telemetry emit failed (%s/%s): %s", subsystem, event_type, e)
        return None


def load_telemetry(
    *,
    limit: int = 100,
    subsystem: str = "",
    event_type: str = "",
    success_only: Optional[bool] = None,
    base: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = _path(base)
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if subsystem and row.get("subsystem") != subsystem:
            continue
        if event_type and row.get("event_type") != event_type:
            continue
        if success_only is not None and row.get("success") != success_only:
            continue
        rows.append(row)
    return rows[-limit:]

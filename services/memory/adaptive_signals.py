"""Adaptive signals derived from telemetry — fed into learning and system patterns."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .entity_graph import memory_dir, utc_now
from .learning import record_learning_signal

logger = logging.getLogger(__name__)

ADAPTIVE_FILE = "adaptive_signals.jsonl"


def _path(base: Optional[Path] = None) -> Path:
    return memory_dir(base) / ADAPTIVE_FILE


def record_adaptive_signal(
    signal_key: str,
    *,
    source_subsystem: str = "",
    pattern: str = "",
    success: bool = True,
    weight: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "signal_key": signal_key,
        "source_subsystem": source_subsystem,
        "pattern": pattern,
        "success": success,
        "weight": weight,
        "when_utc": utc_now(),
        "metadata": metadata or {},
    }
    path = _path(base)
    memory_dir(base)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_adaptive_signals(limit: int = 100, base: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _path(base)
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]


def ingest_telemetry_event(rec: Dict[str, Any], base: Optional[Path] = None) -> None:
    """Derive adaptive signals and refresh system patterns from one telemetry row."""
    subsystem = rec.get("subsystem", "")
    event_type = rec.get("event_type", "")
    success = bool(rec.get("success", True))
    key = f"{subsystem}:{event_type}"

    if not success:
        record_adaptive_signal(
            key,
            source_subsystem=subsystem,
            pattern="failure",
            success=False,
            metadata={"telemetry_id": rec.get("telemetry_id"), "error_code": rec.get("error_code")},
            base=base,
        )
        severity = rec.get("severity", "info")
        if severity in ("error", "critical"):
            record_learning_signal(
                f"telemetry:{key}",
                "subsystem_failure",
                success=False,
                base=base,
            )

    if subsystem == "acquisition" and event_type == "lead_scored":
        meta = rec.get("metadata") or {}
        if meta.get("high_priority"):
            record_learning_signal("acquisition:high_priority", "lead_to_inquiry", success=True, base=base)

    if subsystem == "email" and event_type == "send_success":
        record_learning_signal("email:deliverability", "inquiry_to_intake", success=True, base=base)

    if subsystem == "reports" and event_type == "binder_generated":
        if rec.get("metadata", {}).get("used_entity_context"):
            record_learning_signal("reports:entity_context", "inquiry_to_intake", success=True, base=base)

    try:
        from .organism_observability import refresh_system_patterns_from_telemetry

        refresh_system_patterns_from_telemetry(base=base)
    except Exception as e:
        logger.debug("System pattern refresh skipped: %s", e)

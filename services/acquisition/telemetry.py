"""Acquisition organism telemetry — central memory transport, local interaction log."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .intelligence_paths import INTERACTIONS_JSONL, ensure_intel_dirs
from .models import utc_now

logger = logging.getLogger(__name__)

ORGANISM_SUBSYSTEM = "acquisition_organism"


def _append_jsonl(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> None:
    root = ensure_intel_dirs(base)
    path = root / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def emit(
    event_type: str,
    *,
    lead_id: str = "",
    target_id: str = "",
    project_id: str = "",
    campaign_id: str = "",
    severity: str = "info",
    success: bool = True,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
    log_interaction: bool = True,
) -> Optional[Dict[str, Any]]:
    """Emit to central telemetry; optionally mirror to interactions.jsonl."""
    meta = dict(metadata or {})
    if campaign_id:
        meta.setdefault("campaign_id", campaign_id)
    if target_id:
        meta.setdefault("target_id", target_id)
    rec = None
    try:
        from services.memory.telemetry import emit_telemetry

        rec = emit_telemetry(
            ORGANISM_SUBSYSTEM,
            event_type,
            lead_id=lead_id,
            project_id=project_id,
            severity=severity,
            success=success,
            message=message[:500] if message else "",
            metadata=meta,
            base=base,
        )
    except Exception as e:
        logger.debug("Acquisition organism telemetry skipped: %s", e)
    if log_interaction:
        _append_jsonl(
            INTERACTIONS_JSONL,
            {
                "interaction_id": f"ACQ-{uuid.uuid4().hex[:10]}",
                "event_type": event_type,
                "lead_id": lead_id,
                "target_id": target_id,
                "project_id": project_id,
                "campaign_id": campaign_id,
                "when_utc": utc_now(),
                "success": success,
                "metadata": meta,
            },
            base,
        )
    return rec


def load_interactions(
    *,
    limit: int = 200,
    event_type: str = "",
    base: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    path = root / INTERACTIONS_JSONL
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_type and row.get("event_type") != event_type:
            continue
        rows.append(row)
    return rows[-limit:]

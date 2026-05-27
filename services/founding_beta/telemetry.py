"""Founding beta telemetry — upload validation and organism learning."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .mode import is_founding_beta_mode

BETA_EVENT_TYPES = frozenset(
    {
        "beta_upload_started",
        "beta_upload_completed",
        "upload_file_types",
        "evidence_mapping_confidence",
        "operator_review_needed",
        "onboarding_confusion",
        "overlay_helpfulness",
        "acquisition_to_upload_conversion",
    }
)


def emit_beta_event(
    event_type: str,
    *,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not is_founding_beta_mode():
        return
    meta = dict(metadata or {})
    meta["founding_beta"] = True
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry("founding_beta", event_type, message=message[:300], metadata=meta)
    except Exception:
        pass
    try:
        from services.knowledge_cockpit.telemetry import emit_knowledge_event

        if event_type == "overlay_helpfulness":
            emit_knowledge_event("overlay_helpfulness", metadata=meta)
    except Exception:
        pass

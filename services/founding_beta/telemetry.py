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
        "intake_received",
        "intake_classified",
        "operator_approved",
        "operator_archived",
        "operator_high_value",
        "operator_request_more_info",
        "missing_documents_detected",
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
        from services.organism_observability.emit import organism_emit

        organism_emit("founding_beta", event_type, message=message[:300], metadata=meta)
        if event_type in ("beta_upload_completed", "workspace_created"):
            organism_emit(
                "acquisition_organism",
                "upload_conversion_completed",
                message=message[:300],
                metadata={**meta, "real_paperwork_submitted": True},
            )
    except Exception:
        pass
    try:
        from services.knowledge_cockpit.telemetry import emit_knowledge_event

        if event_type == "overlay_helpfulness":
            emit_knowledge_event("overlay_helpfulness_signal", metadata=meta)
    except Exception:
        pass

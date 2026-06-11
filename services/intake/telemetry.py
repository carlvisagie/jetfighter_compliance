"""Intake pipeline telemetry — upload validation and organism learning.

PATCH 13A-4F: Timeline Normalization
Canonical lifecycle event names for organism timeline:
- upload_started, upload_completed
- verified_complete
- external_verification_started, external_verification_completed
- project_kickoff_started, project_kickoff_completed
- evidence_intelligence_started, evidence_intelligence_completed
- cognition_started, cognition_completed
- validation_started, validation_completed
- compliance_health_completed
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .mode import is_intake_mode

INTAKE_EVENT_TYPES = frozenset(
    {
        "pilot_upload_started",
        "pilot_upload_completed",
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

# PATCH 13A-4F: Canonical lifecycle event names
LIFECYCLE_EVENTS = frozenset(
    {
        "upload_started",
        "upload_completed",
        "verified_complete",
        "external_verification_started",
        "external_verification_completed",
        "project_kickoff_started",
        "project_kickoff_completed",
        "evidence_intelligence_started",
        "evidence_intelligence_completed",
        "cognition_started",
        "cognition_completed",
        "validation_started",
        "validation_completed",
        "compliance_health_completed",
    }
)


def emit_intake_event(
    event_type: str,
    *,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Emit intake pipeline telemetry. Returns False if organism emit failed."""
    if not is_intake_mode():
        return True
    meta = dict(metadata or {})
    meta["intake"] = True
    ok = True
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit("intake", event_type, message=message[:300], metadata=meta)
        if event_type in ("pilot_upload_completed", "workspace_created"):
            organism_emit(
                "acquisition_organism",
                "upload_conversion_completed",
                message=message[:300],
                metadata={**meta, "real_paperwork_submitted": True},
            )
    except Exception:
        ok = False
    try:
        from services.knowledge_cockpit.telemetry import emit_knowledge_event

        if event_type == "overlay_helpfulness":
            emit_knowledge_event("overlay_helpfulness_signal", metadata=meta)
    except Exception:
        pass
    return ok


def emit_lifecycle_event(
    canonical_name: str,
    *,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    alias: str = "",
) -> bool:
    """
    Emit a canonical lifecycle event for organism timeline.
    
    PATCH 13A-4F: All lifecycle events use canonical names from LIFECYCLE_EVENTS.
    If an alias is provided, it is also emitted for backward compatibility.
    
    Args:
        canonical_name: The canonical event name (e.g., "upload_started")
        message: Human-readable message
        metadata: Event metadata
        alias: Legacy alias to also emit (e.g., "pilot_upload_started")
    
    Returns:
        True if emission succeeded
    """
    if not is_intake_mode():
        return True
    
    meta = dict(metadata or {})
    meta["intake"] = True
    meta["lifecycle_event"] = True
    ok = True
    
    try:
        from services.organism_observability.emit import organism_emit
        
        # Emit canonical name
        organism_emit("intake", canonical_name, message=message[:300], metadata=meta)
        
        # Emit alias for backward compatibility if provided and different
        if alias and alias != canonical_name:
            organism_emit("intake", alias, message=message[:300], metadata=meta)
        
        # Special handling for upload_completed
        if canonical_name == "upload_completed":
            organism_emit(
                "acquisition_organism",
                "upload_conversion_completed",
                message=message[:300],
                metadata={**meta, "real_paperwork_submitted": True},
            )
    except Exception:
        ok = False
    
    return ok

"""Central memory hooks for knowledge cockpit usage."""
from __future__ import annotations

from typing import Any, Dict, Optional

OPERATOR_ENTITY_EMAIL = "operator@keepyourcontracts.internal"
OPERATOR_ENTITY_NAME = "KYC Solo Operator"


def link_operator_learning(
    event_type: str,
    *,
    concept_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from services.memory.central_memory import resolve_or_create_entity
        from services.memory.timeline import append_timeline
        from services.memory.learning import record_learning_signal

        eid = resolve_or_create_entity(
            email=OPERATOR_ENTITY_EMAIL,
            company=OPERATOR_ENTITY_NAME,
            display_name=OPERATOR_ENTITY_NAME,
        )
        ref = concept_id or event_type
        append_timeline(
            eid,
            "operator_learning_event",
            "knowledge_concept",
            ref,
            {"event_type": event_type, "knowledge_context_used": True, **(metadata or {})},
        )
        if concept_id:
            record_learning_signal(
                f"knowledge:{concept_id}",
                event_type,
                success=True,
                paperwork_hint=concept_id,
            )
    except Exception:
        pass

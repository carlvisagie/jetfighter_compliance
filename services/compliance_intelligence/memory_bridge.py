"""Write compliance intelligence into central memory (canonical brain)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

COMPLIANCE_ENTITY_EMAIL = "compliance-watch@keepyourcontracts.internal"
COMPLIANCE_ENTITY_NAME = "KYC Compliance Intelligence Watch"


def _entity_id(base: Optional[Any] = None) -> str:
    from services.memory.central_memory import resolve_or_create_entity

    return resolve_or_create_entity(
        email=COMPLIANCE_ENTITY_EMAIL,
        company=COMPLIANCE_ENTITY_NAME,
        display_name=COMPLIANCE_ENTITY_NAME,
        base=base,
    )


def write_source_checked(source_id: str, *, status: str = "ok", base: Optional[Any] = None) -> None:
    try:
        from services.memory.timeline import append_timeline
        from services.memory.organism_integration import _timeline_has

        eid = _entity_id(base)
        ref = f"check:{source_id}"
        if _timeline_has(eid, "compliance_source_checked", ref_id=ref, base=base):
            return
        append_timeline(
            eid,
            "compliance_source_checked",
            "compliance_source",
            source_id,
            {"status": status},
            base,
        )
    except Exception:
        pass


def write_change_detected(change_id: str, source_id: str, payload: Dict[str, Any], base: Optional[Any] = None) -> None:
    try:
        from services.memory.timeline import append_timeline
        from services.memory.organism_integration import _timeline_has

        eid = _entity_id(base)
        if _timeline_has(eid, "compliance_change_detected", ref_id=change_id, base=base):
            return
        append_timeline(
            eid,
            "compliance_change_detected",
            "compliance_change",
            change_id,
            {"source_id": source_id, **payload},
            base,
        )
    except Exception:
        pass


def write_impact_classified(impact_id: str, payload: Dict[str, Any], base: Optional[Any] = None) -> None:
    try:
        from services.memory.timeline import append_timeline
        from services.memory.organism_integration import _timeline_has

        eid = _entity_id(base)
        if _timeline_has(eid, "compliance_impact_classified", ref_id=impact_id, base=base):
            return
        append_timeline(
            eid,
            "compliance_impact_classified",
            "compliance_impact",
            impact_id,
            payload,
            base,
        )
    except Exception:
        pass


def write_review_required(review_id: str, payload: Dict[str, Any], base: Optional[Any] = None) -> None:
    try:
        from services.memory.timeline import append_timeline

        eid = _entity_id(base)
        append_timeline(
            eid,
            "compliance_review_required",
            "compliance_review",
            review_id,
            payload,
            base,
        )
    except Exception:
        pass


def write_knowledge_update_recommended(topic_id: str, change_id: str, base: Optional[Any] = None) -> None:
    try:
        from services.memory.timeline import append_timeline
        from services.memory.learning import record_learning_signal

        eid = _entity_id(base)
        ref = f"{topic_id}:{change_id}"
        append_timeline(
            eid,
            "knowledge_update_recommended",
            "knowledge_topic",
            topic_id,
            {"change_id": change_id, "auto_apply": False},
            base,
        )
        record_learning_signal(
            f"compliance:{topic_id}",
            "compliance_intel",
            success=True,
            paperwork_hint=change_id[:40],
            base=base,
        )
    except Exception:
        pass

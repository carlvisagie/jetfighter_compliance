"""Evidence intelligence telemetry → central memory."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

SUBSYSTEM = "evidence_intelligence"

_DOC_TYPE_HINTS = {
    "policy": "likely_policy_detected",
    "ssp": "likely_ssp_detected",
    "questionnaire": "likely_questionnaire_detected",
    "screenshot": "likely_screenshot_detected",
}


def emit(
    event_type: str,
    *,
    project_id: str = "",
    success: bool = True,
    severity: str = "info",
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    meta = dict(metadata or {})
    try:
        from services.organism_observability.emit import organism_emit

        entity_id = ""
        if project_id:
            try:
                from services.memory.central_memory import find_entity_id

                entity_id = find_entity_id(project_id=project_id) or ""
            except Exception:
                pass
        organism_emit(
            SUBSYSTEM,
            event_type,
            severity=severity,
            success=success,
            project_id=project_id,
            entity_id=entity_id,
            message=message,
            metadata=meta,
            link_timeline=bool(entity_id),
        )
        if event_type == "document_classified":
            _emit_classification_hints(meta, project_id=project_id, entity_id=entity_id)
    except Exception:
        pass


def _emit_classification_hints(
    meta: Dict[str, Any],
    *,
    project_id: str,
    entity_id: str,
) -> None:
    from services.organism_observability.emit import organism_emit

    doc_type = str(meta.get("document_type") or "").lower()
    conf = meta.get("confidence")
    organism_emit(
        SUBSYSTEM,
        "evidence_mapping_confidence",
        project_id=project_id,
        entity_id=entity_id,
        metadata={"document_type": doc_type, "confidence": conf},
        link_timeline=bool(entity_id),
    )
    for key, hint_event in _DOC_TYPE_HINTS.items():
        if key in doc_type:
            organism_emit(
                SUBSYSTEM,
                hint_event,
                project_id=project_id,
                entity_id=entity_id,
                metadata={"document_type": doc_type, "confidence": conf},
            )
    if conf is not None:
        try:
            if float(conf) < 0.55:
                organism_emit(
                    SUBSYSTEM,
                    "evidence_mapping_failure",
                    severity="warning",
                    success=False,
                    project_id=project_id,
                    entity_id=entity_id,
                    metadata={"reason": "low_confidence", **meta},
                )
        except (TypeError, ValueError):
            pass


def emit_upload_batch(
    *,
    project_id: str,
    file_types: List[str],
    total_size: int,
    file_count: int,
    quality_estimate: str = "",
) -> None:
    emit(
        "evidence_upload_batch",
        project_id=project_id,
        metadata={
            "file_types_uploaded": file_types,
            "upload_file_count": file_count,
            "upload_total_size": total_size,
            "upload_quality_estimate": quality_estimate,
        },
    )

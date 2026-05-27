"""Evidence uploads → knowledge concepts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .encyclopedia import get_concept

_DOC_TO_CONCEPT = {
    "policy": "policy",
    "procedure": "procedure",
    "ssp": "ssp",
    "poam": "poam",
    "mfa_evidence": "mfa",
    "training_record": "evidence",
    "incident_response": "incident-response",
    "access_control_evidence": "access-control",
    "vendor_document": "vendor-questionnaire",
    "vulnerability_report": "assessment",
    "backup_evidence": "configuration-management",
    "unknown": "evidence",
}


def build_evidence_context(
    *,
    filename: str = "",
    document_type: str = "",
    text_preview: str = "",
) -> Dict[str, Any]:
    cid = _DOC_TO_CONCEPT.get((document_type or "").lower(), "evidence")
    concept = get_concept(cid) or get_concept("evidence")
    matched = [concept] if concept else []
    blob = f"{filename}\n{text_preview}".lower()
    extra: List[Dict[str, Any]] = []
    for doc_type, concept_id in _DOC_TO_CONCEPT.items():
        if doc_type in blob and concept_id != cid:
            c = get_concept(concept_id)
            if c:
                extra.append(c)
    return {
        "ok": True,
        "document_type": document_type or "unknown",
        "filename": filename,
        "primary_concept": {"id": concept.get("id"), "term": concept.get("term")} if concept else None,
        "related_concepts": [
            {"id": c.get("id"), "term": c.get("term")} for c in ([concept] if concept else []) + extra[:5]
        ],
        "operational_meaning": (concept or {}).get("operational_meaning", ""),
        "evidence_examples": (concept or {}).get("evidence_examples", []),
        "what_to_check_next": _next_checks(document_type),
    }


def _next_checks(document_type: str) -> List[str]:
    dt = (document_type or "").lower()
    if dt == "policy":
        return ["Approval date and owner", "Matches actual tools in use", "Exception register"]
    if dt == "ssp":
        return ["CUI boundary diagram", "Shared responsibility with MSP/cloud", "Version matches production"]
    if dt == "mfa_evidence":
        return ["Covers admins", "Covers remote access", "Dated screenshot"]
    return ["Map file to control matrix", "Attach to customer questionnaire row", "Note gaps in POA&M"]

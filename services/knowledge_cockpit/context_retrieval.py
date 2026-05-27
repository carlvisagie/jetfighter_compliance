"""Knowledge cockpit orchestration — concepts + runbooks + context adapters."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .acquisition_context import build_acquisition_context
from .compliance_context import build_compliance_context
from .concept_graph import suggest_next_learning
from .encyclopedia import get_concept, load_authoritative_sources, search_concepts
from .evidence_context import build_evidence_context
from .operational_explainer import explain_concept, explain_text
from .telemetry import emit_knowledge_event


def search_all(query: str = "", *, limit: int = 12) -> Dict[str, Any]:
    concepts = search_concepts(query, limit=limit)
    runbooks: List[Dict[str, Any]] = []
    try:
        from services.knowledge_index import search_knowledge

        runbooks = search_knowledge(query=query, limit=min(6, limit)).get("topics") or []
    except Exception:
        pass
    emit_knowledge_event("knowledge_lookup", query=query, metadata={"concept_count": len(concepts)})
    return {"ok": True, "query": query, "concepts": concepts, "runbooks": runbooks}


def explain(
    *,
    text: str = "",
    concept_id: str = "",
    record_telemetry: bool = True,
) -> Dict[str, Any]:
    if concept_id:
        out = explain_concept(concept_id)
        if record_telemetry and out.get("ok"):
            emit_knowledge_event("concept_explained", concept_id=concept_id)
        return out
    out = explain_text(text)
    if record_telemetry and out.get("ok") and out.get("primary"):
        pid = (out.get("primary") or {}).get("concept_id", "")
        emit_knowledge_event("concept_explained", concept_id=pid, query=text)
    return out


def get_dashboard() -> Dict[str, Any]:
    return {
        "ok": True,
        "source": "repo_runtime",
        "data_path": "data/knowledge_cockpit",
        "concept_count": len(search_concepts("", limit=100)),
        "authoritative_sources": load_authoritative_sources(),
        "suggested_next_learning": suggest_next_learning(),
        "deprecated_import_note": (
            "Legacy desktop encyclopedia folders are import-only; production reads data/knowledge_cockpit in this repo."
        ),
    }


def context_bundle(
    *,
    acquisition: Optional[Dict[str, Any]] = None,
    compliance: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {"ok": True}
    if acquisition:
        bundle["acquisition"] = build_acquisition_context(**acquisition)
        emit_knowledge_event("acquisition_context_opened", metadata=acquisition)
    if compliance:
        bundle["compliance"] = build_compliance_context(**compliance)
    if evidence:
        bundle["evidence"] = build_evidence_context(**evidence)
        emit_knowledge_event("evidence_context_opened", metadata=evidence)
    return bundle

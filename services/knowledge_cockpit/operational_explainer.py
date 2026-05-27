"""Format concept bundles for operator cockpit (operational voice)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .concept_graph import related_concepts, suggest_next_learning
from .encyclopedia import get_concept, match_concepts_in_text, search_concepts


def explain_concept(concept_id: str) -> Dict[str, Any]:
    c = get_concept(concept_id)
    if not c:
        return {"ok": False, "detail": "concept not found"}
    related = related_concepts(concept_id)
    return {
        "ok": True,
        "concept_id": c["id"],
        "term": c.get("term"),
        "burden_category": c.get("category"),
        "operational_meaning": c.get("operational_meaning"),
        "why_it_matters": c.get("why_it_matters"),
        "evidence_examples": c.get("evidence_examples", []),
        "common_mistakes": c.get("common_mistakes", []),
        "related_concepts": [
            {"id": r.get("id"), "term": r.get("term"), "relation": r.get("relation", "related")}
            for r in related
        ],
        "suggested_next_learning": suggest_next_learning(concept_id),
        "acquisition_signals": c.get("acquisition_signals", []),
    }


def explain_text(text: str, *, limit: int = 6) -> Dict[str, Any]:
    q = (text or "").strip()
    if not q:
        return {"ok": False, "detail": "text required"}
    matched = match_concepts_in_text(q, limit=limit)
    if not matched:
        matched = search_concepts(q, limit=limit)
    primary = matched[0] if matched else None
    bundle: Dict[str, Any] = {
        "ok": True,
        "query": q,
        "matched_concepts": [
            {
                "id": m.get("id"),
                "term": m.get("term"),
                "operational_meaning": (m.get("operational_meaning") or "")[:500],
            }
            for m in matched
        ],
    }
    if primary:
        detail = explain_concept(primary["id"])
        bundle["primary"] = detail
        bundle["burden_category"] = primary.get("category")
        bundle["operational_context"] = primary.get("operational_meaning")
        bundle["why_it_matters"] = primary.get("why_it_matters")
        bundle["likely_paperwork_indicators"] = primary.get("evidence_examples", [])
        bundle["related_concepts"] = detail.get("related_concepts", [])
        bundle["suggested_next_learning"] = detail.get("suggested_next_learning", [])
    return bundle

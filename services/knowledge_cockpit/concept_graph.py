"""Concept relationship graph — in-repo edges only."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List

from .encyclopedia import get_concept, list_concepts
from .paths import relationships_file


@lru_cache(maxsize=1)
def _edges() -> List[Dict[str, str]]:
    path = relationships_file()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("edges") or [])


def related_concepts(concept_id: str, *, limit: int = 10) -> List[Dict[str, Any]]:
    cid = (concept_id or "").strip().lower()
    concept = get_concept(cid)
    if not concept:
        return []
    seen = {cid}
    out: List[Dict[str, Any]] = []

    def _add(target_id: str, relation: str = "related") -> None:
        tid = target_id.lower()
        if tid in seen:
            return
        row = get_concept(tid)
        if not row:
            return
        seen.add(tid)
        out.append({**row, "relation": relation})

    for rid in concept.get("related_ids") or []:
        _add(rid, "related")
        if len(out) >= limit:
            return out

    for edge in _edges():
        if edge.get("from") == cid:
            _add(edge.get("to", ""), edge.get("relation", "linked"))
        elif edge.get("to") == cid:
            _add(edge.get("from", ""), f"inverse_{edge.get('relation', 'linked')}")
        if len(out) >= limit:
            break

    return out[:limit]


def relationship_graph(concept_id: str = "", *, limit: int = 12) -> Dict[str, Any]:
    """Nodes and edges for overlay relationship visualization."""
    nodes: List[Dict[str, Any]] = []
    edges_out: List[Dict[str, str]] = []
    if concept_id:
        center = get_concept(concept_id)
        if center:
            nodes.append({"id": center["id"], "term": center.get("term"), "role": "center"})
        for rel in related_concepts(concept_id, limit=limit):
            nodes.append({"id": rel["id"], "term": rel.get("term"), "role": "related"})
            edges_out.append(
                {"from": concept_id, "to": rel["id"], "relation": rel.get("relation", "related")}
            )
    else:
        for c in list_concepts()[: min(limit, 8)]:
            nodes.append({"id": c["id"], "term": c.get("term"), "role": "seed"})
    return {"ok": True, "nodes": nodes, "edges": edges_out}


def suggest_next_learning(concept_id: str = "", *, limit: int = 3) -> List[Dict[str, Any]]:
    if concept_id:
        rel = related_concepts(concept_id, limit=limit)
        if rel:
            return rel
    # Default onboarding path for solo operator
    path = ["vendor-questionnaire", "ssp", "nist-800-171", "poam", "sprs-score"]
    out = []
    for pid in path:
        c = get_concept(pid)
        if c:
            out.append(c)
        if len(out) >= limit:
            break
    return out

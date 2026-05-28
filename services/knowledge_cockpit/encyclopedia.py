"""Load and search canonical compliance concepts (in-repo data only)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import concepts_file, control_matrix_file, control_xref_file, sources_file


@lru_cache(maxsize=1)
def _load_concepts_payload() -> Dict[str, Any]:
    path = concepts_file()
    if not path.is_file():
        return {"concepts": []}
    return json.loads(path.read_text(encoding="utf-8"))


def list_concepts() -> List[Dict[str, Any]]:
    return list(_load_concepts_payload().get("concepts") or [])


def get_concept(concept_id: str) -> Optional[Dict[str, Any]]:
    cid = (concept_id or "").strip().lower()
    for c in list_concepts():
        if c.get("id") == cid:
            return dict(c)
    return None


def _blob(concept: Dict[str, Any]) -> str:
    parts = [
        concept.get("term", ""),
        " ".join(concept.get("aliases") or []),
        concept.get("category", ""),
        concept.get("operational_meaning", ""),
        concept.get("why_it_matters", ""),
        " ".join(concept.get("evidence_examples") or []),
        " ".join(concept.get("common_mistakes") or []),
    ]
    return " ".join(parts).lower()


def search_concepts(query: str = "", *, limit: int = 12) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    scored: List[tuple[int, Dict[str, Any]]] = []
    for c in list_concepts():
        if not q:
            scored.append((1, c))
            continue
        b = _blob(c)
        score = 0
        if q == c.get("id", ""):
            score += 20
        if q in b:
            score += 5 + b.count(q)
        for word in re.split(r"\W+", q):
            if len(word) > 2 and word in b:
                score += 2
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], x[1].get("term", "")))
    return [dict(c, relevance=s) for s, c in scored[: max(1, min(limit, 50))]]


def match_concepts_in_text(text: str, *, limit: int = 8) -> List[Dict[str, Any]]:
    blob = (text or "").lower()
    hits: List[tuple[int, Dict[str, Any]]] = []
    for c in list_concepts():
        terms = [c.get("term", "")] + list(c.get("aliases") or []) + [c.get("id", "").replace("-", " ")]
        score = 0
        for t in terms:
            t = (t or "").strip().lower()
            if len(t) < 3:
                continue
            if t in blob:
                score += 3 + len(t) // 4
        if score:
            hits.append((score, c))
    hits.sort(key=lambda x: -x[0])
    return [dict(c, match_score=s) for s, c in hits[:limit]]


@lru_cache(maxsize=1)
def load_authoritative_sources() -> List[Dict[str, Any]]:
    path = sources_file()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("sources") or [])


@lru_cache(maxsize=1)
def load_control_matrix() -> List[Dict[str, Any]]:
    path = control_matrix_file()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("rows") or [])


@lru_cache(maxsize=1)
def load_control_xref() -> Dict[str, Any]:
    path = control_xref_file()
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}

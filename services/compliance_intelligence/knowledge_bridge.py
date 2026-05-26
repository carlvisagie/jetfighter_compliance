"""Bridge compliance findings to KYC knowledge index (recommendations only)."""
from __future__ import annotations

from typing import Any, Dict, List

from .schemas import ChangeRecord, ClassificationResult

# Curated topic ids from services/knowledge_index.py — recommendations only, no auto-edit.
TOPIC_HINTS = {
    "CMMC": "launch-path",
    "NIST 800-171": "central-memory",
    "NIST 800-53": "central-memory",
    "DFARS": "launch-path",
    "FAR": "launch-path",
    "CUI": "central-memory",
    "ITAR": "controlled-onboarding-acquisition",
    "CISA alert": "forensic-acquisition-intelligence",
    "EU DPP/ESPR": "launch-path",
}


def recommend_knowledge_updates(
    change: ChangeRecord,
    clf: ClassificationResult,
) -> List[Dict[str, Any]]:
    """Return operator-review knowledge suggestions — never writes repo files."""
    recs: List[Dict[str, Any]] = []
    seen = set()
    for fw in clf.frameworks:
        topic_id = TOPIC_HINTS.get(fw, "launch-path")
        if topic_id in seen:
            continue
        seen.add(topic_id)
        try:
            from services.knowledge_index import get_topic

            topic = get_topic(topic_id) or {}
        except Exception:
            topic = {}
        recs.append(
            {
                "topic_id": topic_id,
                "topic_title": topic.get("title", topic_id),
                "source_path": topic.get("source_path", ""),
                "recommendation": (
                    f"Consider updating encyclopedia section for {fw} after reviewing "
                    f"change {change.change_id}. Not legal advice — operator approval required."
                ),
                "change_id": change.change_id,
                "auto_apply": False,
            }
        )
    if not recs:
        recs.append(
            {
                "topic_id": "launch-path",
                "topic_title": "Launch path",
                "recommendation": "Review whether launch path or ops checklist needs a compliance note.",
                "change_id": change.change_id,
                "auto_apply": False,
            }
        )
    return recs[:6]


def search_related_knowledge(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        from services.knowledge_index import search_knowledge

        return search_knowledge(query=query, limit=limit).get("results") or []
    except Exception:
        return []

"""
Contextual knowledge index for operator guidance (memory layer).
Re-exports curated catalog and adds phase/trigger-aware lookup.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services import knowledge_index as _root_index

# Re-export canonical catalog API
KNOWLEDGE_TOPICS = _root_index.KNOWLEDGE_TOPICS
GLOSSARY = _root_index.GLOSSARY
get_topic = _root_index.get_topic
search_knowledge = _root_index.search_knowledge
topics_for_phase = _root_index.topics_for_phase
knowledge_catalog = _root_index.knowledge_catalog

# Trigger → search query + why template for contextual learning
CONTEXT_TRIGGERS: Dict[str, Dict[str, Any]] = {
    "smtp_failure": {
        "query": "SMTP email transport",
        "phase": "inquiry",
        "why": "Email transport affects whether customers receive intake links.",
        "topic_ids": ["owner-activation-checklist", "launch-path"],
    },
    "lead_stalled": {
        "query": "acquisition onboarding outreach",
        "phase": "acquisition",
        "why": "Stalled leads need controlled outreach and inquiry routing.",
        "topic_ids": ["controlled-onboarding-acquisition", "lead-discovery-engine"],
    },
    "workflow_orphan": {
        "query": "central memory self-heal",
        "phase": "self_heal",
        "why": "Orphan projects break entity continuity and observability.",
        "topic_ids": ["central-memory", "organism-integration-audit"],
    },
    "intake_stalled": {
        "query": "intake workflow",
        "phase": "intake",
        "why": "Customers cannot progress until intake is completed.",
        "topic_ids": ["launch-path", "owner-activation-checklist"],
    },
    "evidence_gap": {
        "query": "evidence upload binder",
        "phase": "evidence",
        "why": "Evidence gaps block binder delivery and customer readiness.",
        "topic_ids": ["launch-path"],
    },
    "telemetry_silence": {
        "query": "organism observability telemetry",
        "phase": "self_heal",
        "why": "Without telemetry the organism cannot detect degradation early.",
        "topic_ids": ["central-memory", "organism-integration-audit"],
    },
    "acquisition_starvation": {
        "query": "lead discovery scoring",
        "phase": "acquisition_discovery",
        "why": "No new leads limits pipeline and learning signal quality.",
        "topic_ids": ["lead-discovery-engine", "forensic-acquisition-intelligence"],
    },
    "new_operator": {
        "query": "architecture runtime flow",
        "phase": "event_logging",
        "why": "Understanding the runtime flow reduces mistakes during onboarding.",
        "topic_ids": ["direct-runtime-flow", "readme-ops-hub"],
    },
}


def contextual_lookup(
    *,
    triggers: Optional[List[str]] = None,
    phase: str = "",
    query: str = "",
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Return articles with relevance, snippet, and why relevant now."""
    seen: set = set()
    out: List[Dict[str, Any]] = []

    def _add_from_search(q: str, ph: str, why: str, boost: int = 0) -> None:
        res = search_knowledge(query=q, phase=ph, limit=limit)
        for t in res.get("topics") or []:
            tid = t["id"]
            if tid in seen:
                continue
            seen.add(tid)
            out.append(
                {
                    "id": tid,
                    "title": t["title"],
                    "relevance": t.get("score", 0) + boost,
                    "snippet": t.get("summary", ""),
                    "why_relevant_now": why,
                    "source_path": t.get("source_path", ""),
                }
            )

    for trig in triggers or []:
        cfg = CONTEXT_TRIGGERS.get(trig)
        if not cfg:
            continue
        for tid in cfg.get("topic_ids") or []:
            meta = next((x for x in KNOWLEDGE_TOPICS if x["id"] == tid), None)
            if meta and meta["id"] not in seen:
                seen.add(meta["id"])
                out.append(
                    {
                        "id": meta["id"],
                        "title": meta["title"],
                        "relevance": 10,
                        "snippet": meta["summary"],
                        "why_relevant_now": cfg["why"],
                        "source_path": meta["path"],
                    }
                )
        _add_from_search(cfg.get("query", ""), cfg.get("phase", ""), cfg["why"], boost=3)

    if phase or query:
        _add_from_search(
            query or phase,
            phase,
            "Matched your current workflow phase or search.",
            boost=1,
        )

    out.sort(key=lambda x: -x["relevance"])
    return out[:limit]

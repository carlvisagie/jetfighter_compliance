"""
Curated operator knowledge index — real repo docs only (no invented articles).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

# topic id → file under repo root; phases filter contextual learning
KNOWLEDGE_TOPICS: List[Dict[str, Any]] = [
    {
        "id": "launch-path",
        "title": "Launch path (inquiry → intake → events)",
        "summary": "Canonical customer onboarding sequence and production entry URLs.",
        "path": "docs/LAUNCH_PATH.md",
        "phases": ["inquiry", "intake", "event_logging"],
        "tags": ["onboarding", "production", "workflow"],
    },
    {
        "id": "direct-runtime-flow",
        "title": "Direct runtime flow",
        "summary": "How inquiry, intake, projects, and ledger events connect on Render.",
        "path": "docs/KYC_DIRECT_RUNTIME_FLOW.md",
        "phases": ["inquiry", "intake", "event_logging"],
        "tags": ["architecture", "workflow"],
    },
    {
        "id": "owner-activation-checklist",
        "title": "Owner activation checklist",
        "summary": "Render env, domain, smoke test, and ops-only tools.",
        "path": "docs/KYC_OWNER_ACTIVATION_CHECKLIST.md",
        "phases": ["inquiry", "intake"],
        "tags": ["production", "checklist"],
    },
    {
        "id": "controlled-onboarding-acquisition",
        "title": "Controlled onboarding acquisition",
        "summary": "MVP outreach targets, messaging, and tracking for 5–15 real tests.",
        "path": "docs/CONTROLLED_ONBOARDING_ACQUISITION.md",
        "phases": ["acquisition", "inquiry"],
        "tags": ["outreach", "mvp"],
    },
    {
        "id": "lead-discovery-engine",
        "title": "Lead discovery engine",
        "summary": "CSV import, scoring, review queue — manual outreach only.",
        "path": "docs/LEAD_DISCOVERY_ENGINE.md",
        "phases": ["acquisition_discovery", "acquisition"],
        "tags": ["leads", "scoring"],
    },
    {
        "id": "forensic-acquisition-intelligence",
        "title": "Forensic acquisition intelligence",
        "summary": "Acquisition forensics, outcomes, and intelligence bridge to central memory.",
        "path": "docs/FORENSIC_ACQUISITION_INTELLIGENCE.md",
        "phases": ["acquisition", "acquisition_discovery"],
        "tags": ["forensics", "memory"],
    },
    {
        "id": "central-memory",
        "title": "Central memory (one brain)",
        "summary": "Entities, timelines, learning, self-heal — canonical organism truth.",
        "path": "docs/CENTRAL_MEMORY.md",
        "phases": ["self_heal", "event_logging"],
        "tags": ["memory", "organism"],
    },
    {
        "id": "organism-integration-audit",
        "title": "Organism integration audit",
        "summary": "Which engines are plugged into central memory vs legacy islands.",
        "path": "docs/KYC_ORGANISM_INTEGRATION_AUDIT.md",
        "phases": ["self_heal"],
        "tags": ["integration", "audit"],
    },
    {
        "id": "production-engineering-doctrine",
        "title": "Production engineering doctrine",
        "summary": "How to operate and change production safely.",
        "path": "docs/PRODUCTION_ENGINEERING_DOCTRINE.md",
        "phases": ["event_logging"],
        "tags": ["production", "ops"],
    },
    {
        "id": "acquisition-readme",
        "title": "Acquisition data layout",
        "summary": "Files under data/acquisition/ and how tracking works.",
        "path": "data/acquisition/README.md",
        "phases": ["acquisition", "acquisition_discovery"],
        "tags": ["data", "tracking"],
    },
    {
        "id": "acquisition-observation-log",
        "title": "Acquisition observation log",
        "summary": "Owner notes from live acquisition experiments.",
        "path": "data/acquisition/observation_log.md",
        "phases": ["acquisition"],
        "tags": ["notes", "mvp"],
    },
    {
        "id": "readme-ops-hub",
        "title": "Operations hub overview",
        "summary": "Active launch path and ops UI map.",
        "path": "docs/README.md",
        "phases": ["inquiry", "intake", "event_logging", "binder"],
        "tags": ["overview"],
    },
]

GLOSSARY: List[Dict[str, str]] = [
    {
        "term": "Phase (ORDER / INTAKE / SCOPE / BINDER / HANDOVER)",
        "definition": "Workflow stage for a project. Steps open as the phase advances.",
    },
    {
        "term": "Required open step",
        "definition": "A checklist step that is required, not done, and already opened for the current phase.",
    },
    {
        "term": "RAG (red / amber / green)",
        "definition": "Green = no required work open; amber = open items on time; red = overdue required steps.",
    },
    {
        "term": "Chain of custody (CoC)",
        "definition": "Ledger events that record who did what, when, on which project.",
    },
    {
        "term": "Intake token",
        "definition": "Signed link sent after inquiry so the customer can complete intake securely.",
    },
    {
        "term": "Evidence binder",
        "definition": "Packaged policies and artifacts exported for customer or auditor review.",
    },
    {
        "term": "Central memory",
        "definition": "Canonical entity/timeline store under data/memory/ — one brain, many vessels.",
    },
    {
        "term": "Orphan project",
        "definition": "Project in registry without a linked entity in central memory; self-heal flags these.",
    },
    {
        "term": "Lead discovery",
        "definition": "Import and score candidates from CSV; owner approves before any outreach.",
    },
    {
        "term": "Controlled onboarding",
        "definition": "Small cohort (5–15) of real end-to-end tests before scaling outreach.",
    },
]


def _topic_by_id(topic_id: str) -> Optional[Dict[str, Any]]:
    for t in KNOWLEDGE_TOPICS:
        if t["id"] == topic_id:
            return t
    return None


def _read_markdown(rel_path: str) -> str:
    p = REPO_ROOT / rel_path
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def get_topic(topic_id: str) -> Optional[Dict[str, Any]]:
    meta = _topic_by_id(topic_id)
    if not meta:
        return None
    content = _read_markdown(meta["path"])
    return {
        "id": meta["id"],
        "title": meta["title"],
        "summary": meta["summary"],
        "phases": meta["phases"],
        "tags": meta["tags"],
        "source_path": meta["path"],
        "content_markdown": content,
        "content_chars": len(content),
        "missing": not bool(content),
    }


def search_knowledge(query: str = "", phase: str = "", limit: int = 20) -> Dict[str, Any]:
    q = (query or "").strip().lower()
    phase_filter = (phase or "").strip().lower()
    results: List[Dict[str, Any]] = []

    for meta in KNOWLEDGE_TOPICS:
        if phase_filter and phase_filter not in meta["phases"]:
            continue
        blob = " ".join(
            [meta["title"], meta["summary"], meta["path"], " ".join(meta["tags"]), " ".join(meta["phases"])]
        ).lower()
        snippet = meta["summary"]
        score = 0
        if not q:
            score = 1
        elif q in blob:
            score = 2 + blob.count(q)
        else:
            for word in re.split(r"\W+", q):
                if len(word) > 2 and word in blob:
                    score += 1
        if score > 0:
            results.append(
                {
                    "id": meta["id"],
                    "title": meta["title"],
                    "summary": meta["summary"],
                    "phases": meta["phases"],
                    "tags": meta["tags"],
                    "source_path": meta["path"],
                    "score": score,
                    "snippet": snippet,
                }
            )

    results.sort(key=lambda x: (-x["score"], x["title"]))
    lim = max(1, min(limit, 50))
    return {
        "query": query,
        "phase": phase_filter or None,
        "count": len(results[:lim]),
        "topics": results[:lim],
        "glossary_hits": _search_glossary(q) if q else [],
    }


def _search_glossary(q: str) -> List[Dict[str, str]]:
    out = []
    for g in GLOSSARY:
        blob = (g["term"] + " " + g["definition"]).lower()
        if q in blob:
            out.append(g)
    return out[:10]


def topics_for_phase(phase: str) -> List[Dict[str, Any]]:
    pf = (phase or "").strip().lower()
    if not pf:
        return [dict(t) for t in KNOWLEDGE_TOPICS]
    return [dict(t) for t in KNOWLEDGE_TOPICS if pf in t["phases"]]


def knowledge_catalog() -> Dict[str, Any]:
    return {
        "topic_count": len(KNOWLEDGE_TOPICS),
        "glossary_count": len(GLOSSARY),
        "topics": [
            {
                "id": t["id"],
                "title": t["title"],
                "summary": t["summary"],
                "phases": t["phases"],
                "source_path": t["path"],
            }
            for t in KNOWLEDGE_TOPICS
        ],
        "glossary": GLOSSARY,
        "fragmentation_note": (
            "No single encyclopedia file exists. Knowledge is spread across docs/*.md and "
            "data/acquisition/*.md; this index is the consolidation layer for the operator cockpit."
        ),
    }

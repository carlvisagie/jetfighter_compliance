"""Detect linkage gaps and suggest corrections (never auto-delete)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import DATA, PROJECTS
from .entity_graph import build_indexes, load_entities, memory_dir, normalize_company, utc_now

CORRECTIONS_FILE = "corrections.jsonl"


def _append_correction(suggestion: Dict[str, Any], base: Optional[Path] = None) -> None:
    path = memory_dir(base) / CORRECTIONS_FILE
    suggestion["when_utc"] = utc_now()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(suggestion, ensure_ascii=False) + "\n")


def load_corrections(base: Optional[Path] = None, limit: int = 50) -> List[Dict[str, Any]]:
    path = memory_dir(base) / CORRECTIONS_FILE
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]


def run_self_healing_scan(base: Optional[Path] = None, write_suggestions: bool = True) -> Dict[str, Any]:
    entities = load_entities(base)
    idx = build_indexes(entities)
    linked_projects = {k.split(":", 1)[1] for k in idx["by_ref"] if k.startswith("project:")}
    linked_leads = {k.split(":", 1)[1] for k in idx["by_ref"] if k.startswith("lead:")}

    orphan_projects: List[str] = []
    if PROJECTS.exists():
        for pdir in PROJECTS.glob("P-*"):
            if pdir.name not in linked_projects:
                orphan_projects.append(pdir.name)

    orphan_inquiries: List[str] = []
    inq_dir = DATA / "inquiries"
    if inq_dir.exists():
        for f in inq_dir.glob("inquiry-*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                email = d.get("email", "")
                dom = email.split("@", 1)[-1].lower() if "@" in email else ""
                if dom and dom not in idx["by_domain"]:
                    orphan_inquiries.append(f.name)
            except Exception:
                orphan_inquiries.append(f.name)

    duplicate_companies: List[Dict[str, str]] = []
    company_map: Dict[str, List[str]] = {}
    for ent in entities:
        cn = ent.get("company_norm") or ""
        eid = ent.get("entity_id", "")
        if cn and eid:
            company_map.setdefault(cn, []).append(eid)
    for cn, ids in company_map.items():
        unique = list(dict.fromkeys(ids))
        if len(unique) > 1:
            duplicate_companies.append({"company_norm": cn, "entity_ids": unique})

    missing_timeline: List[str] = []
    for ent in entities[-100:]:
        eid = ent.get("entity_id", "")
        refs = ent.get("refs") or []
        if refs and eid:
            from .timeline import load_timeline

            if not load_timeline(eid, base):
                missing_timeline.append(eid)

    report = {
        "orphan_projects": orphan_projects,
        "orphan_inquiries": orphan_inquiries[:50],
        "duplicate_companies": duplicate_companies,
        "missing_timeline_entities": missing_timeline,
        "entity_count": len(entities),
        "suggestions_written": 0,
    }

    if write_suggestions:
        for pid in orphan_projects[:20]:
            _append_correction(
                {
                    "type": "orphan_project",
                    "severity": "medium",
                    "ref_id": pid,
                    "suggestion": f"Link project {pid} to an entity via kickoff or manual entity resolve.",
                },
                base,
            )
            report["suggestions_written"] += 1
        for cn_entry in duplicate_companies[:10]:
            _append_correction(
                {
                    "type": "duplicate_company",
                    "severity": "low",
                    "detail": cn_entry,
                    "suggestion": "Review duplicate entities; merge refs manually if same organization.",
                },
                base,
            )
            report["suggestions_written"] += 1
        for eid in missing_timeline[:10]:
            _append_correction(
                {
                    "type": "missing_timeline",
                    "severity": "low",
                    "entity_id": eid,
                    "suggestion": "Replay timeline from forensic events or re-run onboarding link.",
                },
                base,
            )
            report["suggestions_written"] += 1

    return report

"""Map classified changes to KYC impacts and review queue."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import ChangeRecord, ClassificationResult, ImpactRecord, ReviewQueueItem

SERVICE_MAP = {
    "CMMC": ["CMMC-L1", "CMMC-L2"],
    "NIST 800-171": ["CMMC-L1", "CMMC-L2"],
    "NIST 800-53": ["CMMC-L2"],
    "DFARS": ["CMMC-L1", "CMMC-L2"],
    "FAR": ["CMMC-L1"],
    "CUI": ["CMMC-L1", "CMMC-L2"],
    "ITAR": ["ITAR-READY"],
    "CISA alert": ["CMMC-L1", "CMMC-L2"],
    "EU DPP/ESPR": ["DPP-READY"],
}

TOPIC_MAP = {
    "CMMC": ["launch-path", "owner-activation-checklist"],
    "NIST 800-171": ["central-memory", "launch-path"],
    "DFARS": ["launch-path", "production-engineering-doctrine"],
    "CISA alert": ["forensic-acquisition-intelligence", "central-memory"],
    "EU DPP/ESPR": ["launch-path", "readme-ops-hub"],
    "ITAR": ["controlled-onboarding-acquisition"],
}


def _root() -> Path:
    from ..config import DATA

    d = DATA / "compliance_intelligence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_impact(record: ImpactRecord) -> None:
    with (_root() / "impacts.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")


def append_review(item: ReviewQueueItem) -> None:
    with (_root() / "review_queue.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(item.model_dump(), ensure_ascii=False) + "\n")


def load_impacts(limit: int = 100) -> List[Dict[str, Any]]:
    path = _root() / "impacts.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def load_review_queue(limit: int = 100, status: str = "") -> List[Dict[str, Any]]:
    path = _root() / "review_queue.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return rows[-limit:]


def map_impact(
    change: ChangeRecord,
    clf: ClassificationResult,
    *,
    source_name: str = "",
) -> tuple[ImpactRecord, ReviewQueueItem]:
    services: List[str] = []
    topics: List[str] = []
    for fw in clf.frameworks:
        for s in SERVICE_MAP.get(fw, []):
            if s not in services:
                services.append(s)
        for t in TOPIC_MAP.get(fw, []):
            if t not in topics:
                topics.append(t)

    evidence_notes = []
    if "evidence_requirements" in clf.impact_areas:
        evidence_notes.append("Review evidence catalog examples and upload guidance for affected controls.")
    if "customer_guidance" in clf.impact_areas:
        evidence_notes.append("Do not auto-update customer-facing copy — queue for operator review.")

    from .knowledge_bridge import recommend_knowledge_updates

    knowledge_recs = recommend_knowledge_updates(change, clf)

    impact_id = f"IMP-{uuid.uuid4().hex[:12]}"
    impact = ImpactRecord(
        impact_id=impact_id,
        change_id=change.change_id,
        source_id=change.source_id,
        severity=clf.severity,
        affected_services=services,
        affected_topics=topics,
        affected_project_patterns=["P-*"] if services else [],
        evidence_guidance_notes=evidence_notes,
        operator_actions=[
            f"Review change at source {source_name or change.source_id}",
            "Confirm whether KYC service scope or evidence guidance needs updates",
            "Approve knowledge index recommendations before publishing",
        ],
        knowledge_recommendations=knowledge_recs,
        requires_review=True,
        customer_auto_publish=False,
        created_at_utc=_utc(),
    )
    append_impact(impact)

    review_id = f"REV-{uuid.uuid4().hex[:12]}"
    review = ReviewQueueItem(
        review_id=review_id,
        change_id=change.change_id,
        impact_id=impact_id,
        source_id=change.source_id,
        status="pending",
        summary=clf.summary + " — " + change.diff_summary[:200],
        severity=clf.severity,
        suggested_actions=impact.operator_actions,
        knowledge_updates=knowledge_recs,
        created_at_utc=_utc(),
    )
    append_review(review)
    return impact, review

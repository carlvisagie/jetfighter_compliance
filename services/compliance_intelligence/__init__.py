"""Continuous Compliance Intelligence Engine v1."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import (
    change_detector,
    classifier,
    fetcher,
    impact_mapper,
    memory_bridge,
    snapshots,
    sources,
    telemetry,
)
from .schemas import RunSummary


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest_dir() -> Path:
    from ..config import DATA

    d = DATA / "compliance_intelligence" / "digests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_compliance_intel_cycle(
    *,
    polling_filter: str = "",
    source_ids: Optional[List[str]] = None,
    http_client=None,
) -> RunSummary:
    """Alias for scheduler/operator manual runs."""
    return run_compliance_cycle(
        polling_filter=polling_filter,
        source_ids=source_ids,
        http_client=http_client,
    )


def run_compliance_cycle(
    *,
    polling_filter: str = "",
    source_ids: Optional[List[str]] = None,
    http_client=None,
) -> RunSummary:
    """Fetch, snapshot, detect changes, classify, map impacts, bridge memory."""
    run_id = f"RUN-{uuid.uuid4().hex[:10]}"
    summary = RunSummary(run_id=run_id, started_utc=_utc())
    registry = sources.load_sources()
    if source_ids:
        registry = [s for s in registry if s.source_id in source_ids]
    elif polling_filter:
        registry = [s for s in registry if s.polling_frequency == polling_filter and s.enabled]
    else:
        registry = [s for s in registry if s.enabled]

    for src in registry:
        summary.sources_checked += 1
        prior_hash = src.content_hash or ""
        prior_title = ""
        prev_meta = snapshots.latest_snapshot_meta(src.source_id)
        if prev_meta:
            prior_hash = prior_hash or prev_meta.get("sha256", "")
            prior_title = prev_meta.get("title", "")

        result = fetcher.fetch_source(src, client=http_client)
        status = "ok" if result.ok else "failed"
        memory_bridge.write_source_checked(src.source_id, status=status)

        fields = {
            "last_seen_utc": result.fetched_at_utc or _utc(),
            "last_status_code": result.status_code,
            "last_error": result.error or "",
        }
        if result.etag:
            fields["etag"] = result.etag
        if result.last_modified:
            fields["last_modified"] = result.last_modified

        if not result.ok:
            summary.sources_failed += 1
            summary.errors.append(f"{src.source_id}: {result.error}")
            if result.status_code == 0:
                telemetry.emit("source_unreachable", success=False, metadata={"source_id": src.source_id})
            sources.update_source_fields(src.source_id, **fields)
            continue

        if result.not_modified:
            sources.update_source_fields(src.source_id, **fields)
            continue

        fields["content_hash"] = result.sha256
        change = change_detector.detect_change(
            src.source_id,
            result,
            prior_hash=prior_hash,
            prior_title=prior_title,
        )
        if change:
            fields["last_changed_utc"] = change.detected_at_utc
            summary.changes_detected += 1
            telemetry.emit(
                "change_detected",
                metadata={"source_id": src.source_id, "change_id": change.change_id},
            )
            memory_bridge.write_change_detected(
                change.change_id,
                src.source_id,
                change.model_dump(),
            )
            clf = classifier.classify_change(change, source_tags=src.topic_tags)
            telemetry.emit(
                "impact_classified",
                metadata={"change_id": change.change_id, "severity": clf.severity},
            )
            impact, review = impact_mapper.map_impact(change, clf, source_name=src.name)
            summary.impacts_created += 1
            summary.reviews_queued += 1
            telemetry.emit("review_queued", metadata={"review_id": review.review_id})
            memory_bridge.write_impact_classified(impact.impact_id, impact.model_dump())
            memory_bridge.write_review_required(review.review_id, review.model_dump())
            for rec in impact.knowledge_recommendations:
                memory_bridge.write_knowledge_update_recommended(
                    rec.get("topic_id", ""),
                    change.change_id,
                )
        sources.update_source_fields(src.source_id, **fields)

    summary.stale_sources = sources.detect_stale_sources()
    for sid in summary.stale_sources:
        telemetry.emit("source_stale", severity="warning", metadata={"source_id": sid})

    summary.completed_utc = _utc()
    summary.ok = summary.sources_failed < summary.sources_checked
    return summary


def generate_weekly_digest() -> Dict[str, Any]:
    """Build operator digest artifact — does not email customers."""
    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    changes = change_detector.load_changes(50)
    impacts = impact_mapper.load_impacts(50)
    pending = impact_mapper.load_review_queue(50, status="pending")
    stale = sources.detect_stale_sources()

    sections = []
    for ch in changes[-10:]:
        sections.append(
            {
                "change_id": ch.get("change_id"),
                "source_id": ch.get("source_id"),
                "type": ch.get("change_type"),
                "summary": ch.get("diff_summary"),
                "why_it_matters": "May affect service scope, evidence guidance, or operator knowledge.",
            }
        )

    digest = {
        "ok": True,
        "week": week,
        "generated_utc": _utc(),
        "disclaimer": "Operational intelligence only — not legal advice or certification guidance.",
        "changes_count": len(changes),
        "pending_reviews": len(pending),
        "stale_sources": stale,
        "highlights": sections,
        "pending_review_items": pending[:15],
        "recommended_actions": [
            "Review pending compliance intelligence items in Control Center.",
            "Approve knowledge updates before changing customer-facing guidance.",
            "Do not auto-notify customers from v1 digest.",
        ],
    }
    path = _digest_dir() / f"digest-{week}.json"
    path.write_text(json.dumps(digest, indent=2), encoding="utf-8")
    return digest


def get_operator_dashboard() -> Dict[str, Any]:
    registry = sources.load_sources()
    changes = change_detector.load_changes(30)
    impacts = impact_mapper.load_impacts(30)
    pending = impact_mapper.load_review_queue(30, status="pending")
    critical = [i for i in impacts if i.get("severity") in ("high", "critical")]
    stale = sources.detect_stale_sources()
    unreachable = [s.source_id for s in registry if s.last_error and s.last_status_code >= 400]

    latest_digest = None
    dig_dir = _digest_dir()
    if dig_dir.is_dir():
        files = sorted(dig_dir.glob("digest-*.json"), reverse=True)
        if files:
            try:
                latest_digest = json.loads(files[0].read_text(encoding="utf-8"))
            except Exception:
                pass

    return {
        "ok": True,
        "title": "Compliance Intelligence Watch",
        "disclaimer": "Not legal advice. Operator review required before customer-facing changes.",
        "sources": [s.model_dump() for s in registry],
        "sources_count": len(registry),
        "latest_changes": changes[-15:],
        "critical_impacts": critical[-10:],
        "pending_reviews": pending,
        "pending_review_count": len(pending),
        "stale_sources": stale,
        "unreachable_sources": unreachable,
        "latest_digest": latest_digest,
        "suggested_knowledge_updates": _collect_knowledge_suggestions(pending),
    }


def _collect_knowledge_suggestions(pending: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in pending:
        for rec in item.get("knowledge_updates") or []:
            key = rec.get("topic_id", "")
            if key and key not in seen:
                seen.add(key)
                out.append(rec)
    return out[:12]


def review_change(
    change_id: str,
    *,
    action: str = "approved",
    note: str = "",
) -> Dict[str, Any]:
    """Operator review — never auto-publishes customer guidance."""
    valid = {"approved", "dismissed", "deferred"}
    status = action if action in valid else "approved"
    rows = impact_mapper.load_review_queue(500)
    updated = False
    out_path = Path(impact_mapper._root()) / "review_queue.jsonl"
    new_lines = []
    target = None
    for row in rows:
        if row.get("change_id") == change_id and row.get("status") == "pending":
            row["status"] = status
            row["reviewed_at_utc"] = _utc()
            row["reviewer_note"] = (note or "")[:500]
            target = row
            updated = True
        new_lines.append(json.dumps(row, ensure_ascii=False))
    if updated:
        out_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
        telemetry.emit(
            "review_completed",
            metadata={"change_id": change_id, "status": status},
        )
    return {"ok": updated, "change_id": change_id, "status": status, "review": target}

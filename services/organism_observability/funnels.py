"""Upload and acquisition funnel metrics from central telemetry."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def _load_rows(*, limit: int = 3000, base: Optional[Path] = None) -> List[Dict[str, Any]]:
    from services.memory.telemetry import load_telemetry

    return load_telemetry(limit=limit, base=base)


def _count_events(rows: List[Dict[str, Any]], *event_keys: str) -> int:
    keys = set(event_keys)
    n = 0
    for r in rows:
        et = r.get("event_type", "")
        if et in keys:
            n += 1
    return n


def compute_upload_funnel(*, base: Optional[Path] = None, limit: int = 3000) -> Dict[str, Any]:
    rows = _load_rows(limit=limit, base=base)
    page_views = _count_events(
        rows,
        "upload_page_view",
        "customer_session_started",
    )
    helper_opened = _count_events(rows, "helper_opened")
    started = _count_events(
        rows,
        "pre_contact_upload_started",
        "pilot_upload_started",
        "upload_started",
    )
    completed = _count_events(
        rows,
        "pre_contact_upload_completed",
        "pilot_upload_completed",
        "upload_completed",
    )
    abandoned = _count_events(
        rows,
        "upload_first_abandoned",
        "upload_abandoned",
        "step_abandoned",
        "continuation_abandoned",
    )
    workspace = _count_events(rows, "workspace_created", "min_info_completed")
    continuation = _count_events(rows, "continuation_completed", "continuation_link_used")

    timings: List[int] = []
    for r in rows:
        dm = (r.get("metadata") or {}).get("seconds_to_upload")
        if dm is not None:
            try:
                timings.append(int(dm))
            except (TypeError, ValueError):
                pass

    rate = round(completed / started, 3) if started else None
    health = "healthy"
    if started and rate is not None and rate < 0.2:
        health = "critical"
    elif started and rate is not None and rate < 0.5:
        health = "degraded"

    hotspots: List[str] = []
    if page_views and not started:
        hotspots.append("Page views without upload start — hesitation at drop zone")
    if started and abandoned > started * 0.5:
        hotspots.append("High abandonment after upload start")
    if helper_opened > max(1, started):
        hotspots.append("Helper opened more than uploads — reassurance loop")

    return {
        "health": health,
        "page_views": page_views,
        "helper_opened": helper_opened,
        "upload_started": started,
        "upload_completed": completed,
        "onboarding_completed": workspace,
        "abandoned": abandoned,
        "continuation_used": continuation,
        "completion_rate": rate,
        "median_seconds_to_upload": sorted(timings)[len(timings) // 2] if timings else None,
        "abandonment_hotspots": hotspots,
    }


def compute_acquisition_funnel(*, base: Optional[Path] = None, limit: int = 3000) -> Dict[str, Any]:
    rows = _load_rows(limit=limit, base=base)
    cycles_started = _count_events(rows, "acquisition_cycle_started", "reddit_discovery_started")
    cycles_done = _count_events(rows, "acquisition_cycle_completed", "reddit_discovery_completed")
    prey_scored = _count_events(rows, "prey_scored")
    approved = _count_events(rows, "operator_approved", "reddit_reply_approved")
    denied = _count_events(rows, "operator_denied", "reddit_post_ignored")
    uploads_after_engagement = _count_events(
        rows,
        "pilot_upload_completed",
        "pre_contact_upload_completed",
        "workspace_created",
    )

    clusters: Counter = Counter()
    post_ids_approved: Set[str] = set()
    for r in rows:
        meta = r.get("metadata") or {}
        if r.get("event_type") in ("operator_approved", "reddit_reply_approved"):
            pid = meta.get("post_id")
            if pid:
                post_ids_approved.add(str(pid))
        cluster = meta.get("discovery_source_cluster") or meta.get("cluster")
        if cluster and r.get("event_type") in ("prey_scored", "reddit_discovery_completed"):
            clusters[cluster] += 1

    zero_cycle = False
    for r in rows:
        if r.get("event_type") in ("acquisition_cycle_completed", "reddit_discovery_completed"):
            meta = r.get("metadata") or {}
            if meta.get("queued") == 0 or meta.get("organism_auto_skipped", 0) == meta.get("discovered"):
                zero_cycle = True

    health = "healthy"
    if cycles_done and zero_cycle:
        health = "critical"
    elif cycles_started and approved == 0 and prey_scored > 5:
        health = "degraded"

    return {
        "health": health,
        "cycles_started": cycles_started,
        "cycles_completed": cycles_done,
        "prey_scored": prey_scored,
        "operator_approved": approved,
        "operator_denied": denied,
        "paperwork_outcomes": uploads_after_engagement,
        "approval_to_upload_proxy": uploads_after_engagement,
        "top_discovery_clusters": clusters.most_common(6),
        "zero_result_cycle_detected": zero_cycle,
        "queue_starvation_events": _count_events(rows, "queue_starvation"),
    }


def compute_overlay_metrics(*, base: Optional[Path] = None, limit: int = 3000) -> Dict[str, Any]:
    rows = [r for r in _load_rows(limit=limit, base=base) if r.get("subsystem") == "knowledge_cockpit"]
    opened = _count_events(rows, "overlay_opened")
    collapsed = _count_events(rows, "overlay_collapsed")
    explained = _count_events(rows, "explanation_generated", "concept_explained", "overlay_opened")
    concepts: Counter = Counter()
    views: Counter = Counter()
    for r in rows:
        meta = r.get("metadata") or {}
        v = meta.get("view") or meta.get("panel")
        if v:
            views[v] += 1
        cid = meta.get("concept_id")
        if cid:
            concepts[cid] += 1

    usefulness = None
    helpful = sum(1 for r in rows if (r.get("metadata") or {}).get("helpful") is True)
    if opened:
        usefulness = round(helpful / opened, 2) if helpful else 0.0

    return {
        "overlay_opened": opened,
        "overlay_collapsed": collapsed,
        "explanations": explained,
        "top_views": views.most_common(8),
        "top_concepts": concepts.most_common(8),
        "helpfulness_rate": usefulness,
    }


def compute_evidence_metrics(*, base: Optional[Path] = None, limit: int = 3000) -> Dict[str, Any]:
    rows = [
        r
        for r in _load_rows(limit=limit, base=base)
        if r.get("subsystem") in ("evidence_intelligence", "founding_pilot")
    ]
    classified = _count_events(rows, "document_classified", "evidence_extraction_completed")
    failures = _count_events(rows, "evidence_extraction_failed", "evidence_mapping_failure")
    gaps = _count_events(rows, "gap_detected")
    confidences: List[float] = []
    types: Counter = Counter()
    for r in rows:
        meta = r.get("metadata") or {}
        if r.get("event_type") in ("document_classified", "evidence_mapping_confidence"):
            dt = meta.get("document_type")
            if dt:
                types[dt] += 1
            c = meta.get("confidence")
            if c is not None:
                try:
                    confidences.append(float(c))
                except (TypeError, ValueError):
                    pass

    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else None
    health = "healthy"
    if failures and classified and failures / max(1, classified) > 0.3:
        health = "critical"
    elif avg_conf is not None and avg_conf < 0.5:
        health = "degraded"

    return {
        "health": health,
        "documents_classified": classified,
        "mapping_failures": failures,
        "gaps_detected": gaps,
        "avg_mapping_confidence": avg_conf,
        "document_types": types.most_common(8),
    }

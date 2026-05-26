"""Autonomous acquisition intelligence orchestrator."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import learning, messaging, qualification, routing, signals, telemetry
from .discovery import run_csv_import, run_finder_discovery
from .intelligence_paths import CAMPAIGNS_JSONL, SIGNALS_JSONL, TARGETS_JSONL, ensure_intel_dirs
from .models import Lead, utc_now
from .scoring import score_lead_full
from .storage import load_all_leads

from ..memory.telemetry import load_telemetry


def _append_intel(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> None:
    root = ensure_intel_dirs(base)
    path = root / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_intel(filename: str, base: Optional[Path] = None, limit: int = 300) -> List[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    path = root / filename
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


def ingest_public_signal(
    *,
    text: str,
    source: str,
    source_url: str = "",
    company_name: str = "",
    segment: str = "compliance-heavy",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Lawful public signal → target record (discussion, post, website snippet)."""
    sig = signals.detect_signals(text)
    target_id = f"TGT-{uuid.uuid4().hex[:10]}"
    lead_id = f"LD-SIG-{uuid.uuid4().hex[:8]}"
    lead = Lead(
        lead_id=lead_id,
        company_name=company_name or "Unknown organization",
        segment=segment,
        source=source,
        source_url=source_url,
        notes=text[:2000],
        pain_signals=sig.get("pain_tags", []),
    )
    lead = score_lead_full(lead)
    qual = qualification.qualify_lead(lead, sig)
    msg = messaging.generate_message(lead, variant="A")
    routes = routing.build_upload_route(lead_id=lead_id, segment=segment)
    lead = routing.route_lead(lead)

    target = {
        "target_id": target_id,
        "lead_id": lead_id,
        "company_name": lead.company_name,
        "source": source,
        "source_url": source_url,
        "signal_level": sig["signal_level"],
        "signal_bundle": sig,
        "qualification": qual,
        "fit_score": lead.fit_score,
        "priority_score": lead.acquisition_priority_score,
        "routed_url": routes["primary_url"],
        "message_preview": msg,
        "status": "discovered",
        "when_utc": utc_now(),
    }
    _append_intel(TARGETS_JSONL, target, base)
    _append_intel(SIGNALS_JSONL, {"target_id": target_id, **sig, "source": source, "when_utc": utc_now()}, base)

    telemetry.emit("acquisition_target_detected", target_id=target_id, lead_id=lead_id, metadata=target, base=base)
    telemetry.emit("acquisition_signal_detected", target_id=target_id, metadata=sig, base=base)
    telemetry.emit("acquisition_message_sent", target_id=target_id, success=False, message="draft_only", metadata=msg, base=base)

    return {"ok": True, "target": target, "lead": lead.to_dict()}


def run_acquisition_cycle(
    *,
    import_csv: Optional[Path] = None,
    run_finder: bool = False,
    campaign_id: str = "upload-first",
    message_variant: str = "A",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Discovery → signals → qualification → score → message → route."""
    telemetry.emit("acquisition_target_detected", metadata={"phase": "cycle_start"}, base=base)
    stats: Dict[str, Any] = {"targets_created": 0, "leads_processed": 0, "high_priority": 0}

    if import_csv and Path(import_csv).is_file():
        run_csv_import(import_csv)
    if run_finder:
        run_finder_discovery()

    leads, _by_key = load_all_leads()
    stats["leads_processed"] = len(leads)
    for lead in leads:
        blob = " ".join([lead.notes, " ".join(lead.pain_signals), " ".join(lead.compliance_signals)])
        sig = signals.detect_signals(blob) if blob.strip() else signals.detect_signals(lead.company_name)
        qual = qualification.qualify_lead(lead, sig)
        lead = score_lead_full(lead)
        lead = routing.route_lead(lead, campaign_id=campaign_id, variant=message_variant)
        msg = messaging.generate_message(lead, variant=message_variant)

        target_id = f"TGT-{lead.lead_id}"
        target = {
            "target_id": target_id,
            "lead_id": lead.lead_id,
            "company_name": lead.company_name,
            "signal_level": sig["signal_level"],
            "qualification": qual,
            "fit_score": lead.fit_score,
            "priority_score": lead.acquisition_priority_score,
            "routed_url": lead.inquiry_routed_link,
            "message_preview": msg,
            "status": lead.status,
            "when_utc": utc_now(),
        }
        _append_intel(TARGETS_JSONL, target, base)
        stats["targets_created"] += 1
        if lead.acquisition_priority_score >= 75:
            stats["high_priority"] += 1

    _append_intel(
        CAMPAIGNS_JSONL,
        {
            "campaign_id": campaign_id,
            "variant": message_variant,
            "when_utc": utc_now(),
            "targets": stats["targets_created"],
            "doctrine": "upload_first",
        },
        base,
    )
    learning.run_learning_cycle(base)
    telemetry.emit("acquisition_learning", metadata=stats, base=base)
    return {"ok": True, **stats}


def track_funnel_event(
    stage: str,
    *,
    success: bool = True,
    lead_id: str = "",
    project_id: str = "",
    org_key: str = "",
    campaign_id: str = "",
    variant: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    """Upload funnel telemetry for learning (real events only)."""
    telemetry.emit(
        f"acquisition_{'conversion' if success else 'failure'}",
        lead_id=lead_id,
        project_id=project_id,
        metadata={"stage": stage, **(metadata or {})},
        success=success,
        base=base,
    )
    learning.record_conversion(
        stage=stage,
        success=success,
        lead_id=lead_id,
        project_id=project_id,
        org_key=org_key,
        campaign_id=campaign_id,
        variant=variant,
        metadata=metadata,
        base=base,
    )


def _upload_conversion_rate(base: Optional[Path] = None) -> Dict[str, Any]:
    interactions = telemetry.load_interactions(limit=500, base=base)
    started = sum(1 for i in interactions if i.get("metadata", {}).get("stage") == "upload_started" or i.get("event_type") == "pre_contact_upload_started")
    completed = sum(1 for i in interactions if "upload_completed" in str(i.get("event_type", "")) or i.get("metadata", {}).get("stage") == "workspace_created")
    if not interactions:
        from .memory import _load_outcomes

        outcomes = _load_outcomes(base)
        completed = sum(1 for o in outcomes if o.get("success"))
        started = len(outcomes) or 1
    rate = (completed / started) if started else 0.0
    return {"started": started, "completed": completed, "rate": round(rate, 4)}


def get_operator_dashboard(base: Optional[Path] = None) -> Dict[str, Any]:
    """Acquisition Intelligence panel data for operator cockpit."""
    targets = _load_intel(TARGETS_JSONL, base)
    targets.sort(key=lambda t: t.get("priority_score", 0), reverse=True)
    hottest = targets[:12]

    winners = learning.load_winners(base, 20)
    failures = learning.load_failures(base, 20)
    experiments = learning.load_experiments(base, 10)

    tel = load_telemetry(limit=80, subsystem="acquisition_organism")
    if not tel:
        tel = load_telemetry(limit=40, subsystem="acquisition")

    conv = _upload_conversion_rate(base)
    channels: Dict[str, int] = {}
    for t in targets:
        ch = t.get("source") or "unknown"
        channels[ch] = channels.get(ch, 0) + 1
    best_channels = sorted(channels.items(), key=lambda x: -x[1])[:6]

    emotional: Dict[str, int] = {}
    for t in targets:
        for tag in (t.get("signal_bundle") or {}).get("emotional_tags") or []:
            emotional[tag] = emotional.get(tag, 0) + 1

    return {
        "ok": True,
        "doctrine": {
            "positioning": "burden_removal",
            "message": messaging.CORE_HEADLINE + " " + messaging.CORE_SUBLINE,
            "primary_route": "/ui/inquiry.html",
            "success_metric": "real_paperwork_submitted",
        },
        "hottest_targets": hottest,
        "upload_conversion": conv,
        "best_channels": [{"channel": k, "targets": v} for k, v in best_channels],
        "active_experiments": [e for e in experiments if e.get("status") == "active"],
        "recent_winners": winners[-8:],
        "recent_failures": failures[-8:],
        "abandonment_hotspots": [f for f in failures if "abandon" in f.get("reason", "")][-5:],
        "emotional_trends": sorted(emotional.items(), key=lambda x: -x[1])[:8],
        "telemetry_recent": tel[-25:],
        "organism_learning": learning.run_learning_cycle(base),
        "what_organism_is_learning": _learning_summary(winners, failures, conv),
    }


def _learning_summary(winners: List[Dict], failures: List[Dict], conv: Dict) -> str:
    parts = []
    if conv.get("rate"):
        parts.append(f"Upload/workspace conversion rate ~{conv['rate']*100:.1f}% from tracked events.")
    if winners:
        parts.append(f"Recent wins: {winners[-1].get('reason', 'conversion')}.")
    if failures:
        parts.append(f"Watch failures: {failures[-1].get('reason', 'unknown')}.")
    if not parts:
        parts.append("Collecting real upload telemetry — run discovery cycle and route traffic to inquiry.")
    return " ".join(parts)

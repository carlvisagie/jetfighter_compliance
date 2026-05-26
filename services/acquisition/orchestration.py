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
from .discovery import row_to_lead
from .models import normalize_segment
from .storage import append_lead, dedupe_key, load_all_leads, next_lead_id

from ..memory.telemetry import load_telemetry

# Pain context for federal award recipients (lawful public metadata only)
_FEDERAL_BURDEN_HINT = (
    "federal award recipient defense supply chain compliance documentation burden"
)


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


def load_recent_target_keys(base: Optional[Path] = None) -> set:
    """Dedupe keys for live connectors (company name lower)."""
    keys: set = set()
    for t in _load_intel(TARGETS_JSONL, base, limit=5000):
        k = (t.get("company_name") or "").strip().lower()
        if k:
            keys.add(k)
    leads, _ = load_all_leads()
    for lead in leads:
        k = (lead.company_name or "").strip().lower()
        if k:
            keys.add(k)
    return keys


def format_target_for_panel(
    lead: Lead,
    sig: Dict[str, Any],
    qual: Dict[str, Any],
    msg: Dict[str, Any],
    *,
    source: str,
    source_url: str = "",
    target_id: str = "",
) -> Dict[str, Any]:
    """Flat fields for operator Acquisition Intelligence panel."""
    pain_tags = sig.get("pain_tags") or list(lead.pain_signals) or []
    pain_signal = ", ".join(pain_tags[:5]) if pain_tags else "compliance_burden_likely"
    preview = msg if isinstance(msg, dict) else {}
    headline = preview.get("headline") or messaging.CORE_HEADLINE
    body = preview.get("body") or ""
    route = lead.inquiry_routed_link or ""
    return {
        "target_id": target_id or f"TGT-{lead.lead_id}",
        "lead_id": lead.lead_id,
        "company_name": lead.company_name,
        "source": source,
        "source_url": source_url or lead.source_url,
        "signal_level": sig.get("signal_level", "medium"),
        "signal_bundle": sig,
        "pain_signal": pain_signal,
        "qualification": qual,
        "qualification_score": qual.get("overall_confidence", lead.confidence_score),
        "fit_score": lead.fit_score,
        "priority_score": lead.acquisition_priority_score,
        "routed_url": route,
        "route_url": route,
        "suggested_message": f"{headline} — {body[:220]}".strip(" —"),
        "message_preview": preview,
        "message_draft": preview,
        "outreach_status": "draft_only",
        "status": lead.status,
        "when_utc": utc_now(),
    }


def ingest_discovery_candidate(
    row: Dict[str, Any],
    *,
    campaign_id: str = "upload-first",
    message_variant: str = "A",
    min_fit_score: int = 0,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Ingest a lawful public discovery row → lead store + acquisition target.
  Does not contact anyone.
    """
    company = (row.get("company_name") or "").strip()
    if not company:
        return {"ok": False, "skipped": True, "reason": "missing_company"}

    segment = normalize_segment(row.get("segment") or "government-subcontractor") or "government-subcontractor"
    cleaned = {
        "company_name": company,
        "website": row.get("website", ""),
        "contact_name": row.get("contact_name", ""),
        "contact_title": row.get("contact_title", ""),
        "contact_email": row.get("contact_email", ""),
        "linkedin_url": row.get("linkedin_url", ""),
        "industry": row.get("industry", ""),
        "segment": segment,
        "source": row.get("source") or "public_discovery",
        "source_url": row.get("source_url", ""),
        "location": row.get("location", ""),
        "notes": row.get("notes", ""),
    }

    leads, by_key = load_all_leads()
    tmp = row_to_lead(cleaned, "pending")
    key = dedupe_key(tmp)
    if key in by_key:
        return {"ok": True, "skipped": True, "reason": "duplicate_lead"}

    lead_id = next_lead_id(leads)
    lead = row_to_lead(cleaned, lead_id)
    lead = routing.route_lead(lead, campaign_id=campaign_id, variant=message_variant)

    blob = " ".join(
        [
            lead.notes,
            _FEDERAL_BURDEN_HINT,
            " ".join(lead.pain_signals),
            " ".join(lead.compliance_signals),
            lead.company_name,
        ]
    )
    sig = signals.detect_signals(blob)
    qual = qualification.qualify_lead(lead, sig)
    msg = messaging.generate_message(lead, variant=message_variant)

    if min_fit_score and lead.fit_score < min_fit_score:
        return {"ok": True, "skipped": True, "reason": "below_fit_threshold", "fit_score": lead.fit_score}

    append_lead(lead, base)
    try:
        from services.memory import link_lead, resolve_or_create_entity

        eid = resolve_or_create_entity(
            email=lead.contact_email or f"prospect-{lead.lead_id}@acquisition.local",
            company=lead.company_name,
            contact_name=lead.contact_name or lead.company_name,
            display_name=lead.company_name,
        )
        link_lead(lead.lead_id, eid, {"source": lead.source, "segment": lead.segment})
    except Exception:
        pass

    target = format_target_for_panel(
        lead,
        sig,
        qual,
        msg,
        source=cleaned["source"],
        source_url=cleaned["source_url"],
    )
    _append_intel(TARGETS_JSONL, target, base)
    _append_intel(
        SIGNALS_JSONL,
        {"target_id": target["target_id"], **sig, "source": cleaned["source"], "when_utc": utc_now()},
        base,
    )

    telemetry.emit(
        "acquisition_target_detected",
        target_id=target["target_id"],
        lead_id=lead.lead_id,
        metadata=target,
        base=base,
    )
    telemetry.emit(
        "acquisition_signal_detected",
        target_id=target["target_id"],
        metadata=sig,
        base=base,
    )
    telemetry.emit(
        "acquisition_message_sent",
        target_id=target["target_id"],
        success=False,
        message="draft_only",
        metadata=msg,
        base=base,
    )
    try:
        from services.alerts import alert_high_fit_target

        alert_high_fit_target(target)
    except Exception:
        pass

    return {"ok": True, "target": target, "lead": lead.to_dict()}


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

    target = format_target_for_panel(
        lead,
        sig,
        qual,
        msg,
        source=source,
        source_url=source_url,
        target_id=target_id,
    )
    target["status"] = "discovered"
    target["routed_url"] = routes["primary_url"]
    target["route_url"] = routes["primary_url"]
    _append_intel(TARGETS_JSONL, target, base)
    _append_intel(SIGNALS_JSONL, {"target_id": target_id, **sig, "source": source, "when_utc": utc_now()}, base)

    telemetry.emit("acquisition_target_detected", target_id=target_id, lead_id=lead_id, metadata=target, base=base)
    telemetry.emit("acquisition_signal_detected", target_id=target_id, metadata=sig, base=base)
    telemetry.emit("acquisition_message_sent", target_id=target_id, success=False, message="draft_only", metadata=msg, base=base)
    try:
        from services.alerts import alert_high_fit_target

        alert_high_fit_target(target)
    except Exception:
        pass

    return {"ok": True, "target": target, "lead": lead.to_dict()}


def run_acquisition_cycle(
    *,
    import_csv: Optional[Path] = None,
    run_finder: bool = False,
    run_live_connector: bool = False,
    connector: str = "usaspending",
    campaign_id: str = "upload-first",
    message_variant: str = "A",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Discovery → signals → qualification → score → message → route."""
    telemetry.emit("acquisition_target_detected", metadata={"phase": "cycle_start"}, base=base)
    stats: Dict[str, Any] = {"targets_created": 0, "leads_processed": 0, "high_priority": 0}

    if import_csv and Path(import_csv).is_file():
        run_csv_import(import_csv)
    live_ran = False
    if run_live_connector and connector == "usaspending":
        from .connectors.usaspending_live import run_usaspending_live_connector

        live = run_usaspending_live_connector(
            campaign_id=campaign_id,
            message_variant=message_variant,
            base=base,
        )
        stats["live_connector"] = live
        stats["targets_created"] += live.get("targets_created", 0)
        live_ran = True
    elif run_finder:
        run_finder_discovery()

    if live_ran:
        _append_intel(
            CAMPAIGNS_JSONL,
            {
                "campaign_id": campaign_id,
                "variant": message_variant,
                "when_utc": utc_now(),
                "targets": stats["targets_created"],
                "connector": "usaspending_live",
                "doctrine": "upload_first",
            },
            base,
        )
        learning.run_learning_cycle(base)
        telemetry.emit("acquisition_learning", metadata=stats, base=base)
        return {"ok": True, **stats}

    leads, _by_key = load_all_leads()
    stats["leads_processed"] = len(leads)
    for lead in leads:
        blob = " ".join([lead.notes, " ".join(lead.pain_signals), " ".join(lead.compliance_signals)])
        sig = signals.detect_signals(blob) if blob.strip() else signals.detect_signals(lead.company_name)
        qual = qualification.qualify_lead(lead, sig)
        lead = score_lead_full(lead)
        lead = routing.route_lead(lead, campaign_id=campaign_id, variant=message_variant)
        msg = messaging.generate_message(lead, variant=message_variant)

        target = format_target_for_panel(
            lead,
            sig,
            qual,
            msg,
            source=lead.source,
            source_url=lead.source_url,
        )
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
    if success and stage == "workspace_created":
        try:
            from services.alerts import raise_alert

            raise_alert(
                "acquisition_conversion",
                title="Acquisition conversion — workspace created",
                body=f"Funnel stage {stage} completed.",
                context={
                    "project_id": project_id,
                    "lead_id": lead_id,
                    "campaign": campaign_id,
                    "message_variant": variant,
                    "stage": stage,
                    **(metadata or {}),
                },
                dedupe_key=f"conversion:{project_id}",
            )
        except Exception:
            pass

    try:
        from .connectors.reddit.learning import ingest_funnel_signal

        ingest_funnel_signal(
            stage,
            project_id=project_id,
            lead_id=lead_id,
            metadata={"campaign_id": campaign_id, "variant": variant, **(metadata or {})},
            base=base,
        )
    except Exception:
        pass

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
        "live_connectors": [
            {"id": "usaspending_live", "status": "active", "lawful": True},
            {"id": "reddit_live", "status": "active", "lawful": True, "operator_review": True, "auto_post": False},
        ],
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

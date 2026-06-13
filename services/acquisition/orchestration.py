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


def _reddit_auto_post_enabled() -> bool:
    try:
        from .connectors.reddit.poster import reddit_configured
        return reddit_configured()
    except Exception:
        return False


def _append_intel(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> None:
    root = ensure_intel_dirs(base)
    path = root / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_intel(filename: str, base: Optional[Path] = None, limit: int = 300) -> List[Dict[str, Any]]:
    from ..lazy_io import load_jsonl

    root = ensure_intel_dirs(base)
    path = root / filename
    if not path.is_file():
        return []
    return load_jsonl(path, limit=limit)


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
    panel = {
        "target_id": target_id or f"TGT-{lead.lead_id}",
        "lead_id": lead.lead_id,
        "company_name": lead.company_name,
        "source": source,
        "source_url": source_url or lead.source_url,
        "signal_level": sig.get("signal_level", "medium"),
        "signal_bundle": sig,
        "pain_signal": pain_signal,
        "qualification": qual,
        "prey_score": qual.get("prey_score", 0),  # TUNED ENGINE - primary score
        "prey_tier": qual.get("prey_tier", 0),  # TUNED ENGINE - tier classification
        "queue_eligible": qual.get("queue_eligible", False),
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
    return panel


def enrich_target_with_founding_pilot(
    panel: Dict[str, Any],
    row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Attach paperwork prediction fields for operator Acquisition panel."""
    row = row or {}
    fb = row.get("founding_pilot_enrichment")
    if not fb and "usaspending" in (panel.get("source") or ""):
        try:
            from services.intake.paperwork_prediction import predict_federal_supplier_paperwork

            fb = predict_federal_supplier_paperwork(
                panel.get("company_name", ""),
                notes=row.get("notes", ""),
                segment=row.get("segment", ""),
            )
        except Exception:
            fb = {}
    if fb:
        panel.update(
            {
                "likely_paperwork_prediction": fb.get("likely_paperwork_prediction"),
                "likely_paperwork_indicators": fb.get("likely_paperwork_indicators"),
                "likely_compliance_burden": fb.get("likely_compliance_burden"),
                "likely_outreach_angle": fb.get("likely_outreach_angle"),
                "likely_evidence_request": fb.get("likely_evidence_request"),
                "recommended_founding_pilot_pitch": fb.get("recommended_founding_pilot_pitch"),
                "why_might_upload_paperwork": fb.get("why_might_upload_paperwork"),
                "pilot_fit": fb.get("pilot_fit"),
                "recommended_next_action": fb.get("recommended_next_action"),
            }
        )
    return panel


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
    target = enrich_target_with_founding_pilot(target, row=row)
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

    # PATCH 13A-14A: Create CustomerIntelligenceRecord for the new intelligence system
    intelligence_record = None
    intelligence_created = False
    try:
        from .ideal_customer_profile import create_or_update_intelligence
        
        intelligence_record, intelligence_created = create_or_update_intelligence(
            company_name=company,
            uei=row.get("uei", ""),
            location=cleaned.get("location", ""),
            source=cleaned.get("source", "public_discovery"),
            lead_id=lead.lead_id,
            website=cleaned.get("website", ""),
            contact_email=cleaned.get("contact_email", ""),
            industry=cleaned.get("industry", ""),
            notes=cleaned.get("notes", ""),
            contract_value=row.get("contract_value"),
            naics=row.get("naics", ""),
        )
        
        telemetry.emit(
            "intelligence_record_created" if intelligence_created else "intelligence_record_updated",
            lead_id=lead.lead_id,
            target_id=target["target_id"],
            metadata={
                "record_id": intelligence_record.record_id if intelligence_record else None,
                "company_name": company,
                "is_new": intelligence_created,
            },
            base=base,
        )
    except Exception as e:
        # Intelligence creation failure must not break discovery
        telemetry.emit(
            "intelligence_creation_failed",
            lead_id=lead.lead_id,
            target_id=target["target_id"],
            success=False,
            metadata={"error": str(e)[:200], "company_name": company},
            base=base,
        )

    # PATCH 13A-8A: Autonomous outreach safety gate
    # Auto-send is DISABLED by default. All leads remain draft_only until
    # explicitly approved by operator via send-approved endpoints.
    email_sent = False
    email_result: Dict[str, Any] = {}
    has_valid_email = lead.contact_email and "@" in lead.contact_email
    meets_quality_threshold = lead.fit_score >= 60 and qual.get("overall_confidence", 0) >= 0.6
    
    # Import safety module
    from . import outreach_safety
    
    # Check if auto-send is enabled via environment flag
    auto_send_flag_enabled = outreach_safety.is_auto_send_enabled()
    
    # SAFETY GATE: Even if doctrine says auto_send, we check the env flag first
    if auto_send_flag_enabled and has_valid_email and meets_quality_threshold:
        # Check full eligibility (suppression, optout, daily cap, etc.)
        eligibility = outreach_safety.check_send_eligibility(
            lead.contact_email,
            lead.lead_id,
            require_operator_approval=True,  # Still require operator approval
            operator_approved=False,  # Discovery never auto-approves
        )
        
        if eligibility.get("eligible"):
            # This path is currently unreachable because require_operator_approval=True
            # and operator_approved=False. This is intentional safety behavior.
            pass
        else:
            # Log that we blocked the auto-send due to policy
            telemetry.emit(
                "blocked_auto_send_due_to_policy",
                lead_id=lead.lead_id,
                target_id=target["target_id"],
                metadata={
                    "reason": eligibility.get("reason"),
                    "detail": eligibility.get("detail"),
                    "email": lead.contact_email,
                    "auto_send_flag_enabled": auto_send_flag_enabled,
                },
                base=base,
            )
            outreach_safety.log_send_attempt(
                lead.lead_id,
                lead.contact_email,
                approved=False,
                sent=False,
                blocked_reason=eligibility.get("reason", "policy"),
                operator_approved=False,
                auto_send=True,
            )
            outreach_safety.increment_daily_blocked_count(eligibility.get("reason", "policy"))
    elif has_valid_email and meets_quality_threshold and not auto_send_flag_enabled:
        # Log that auto-send was blocked because flag is disabled
        telemetry.emit(
            "blocked_auto_send_due_to_policy",
            lead_id=lead.lead_id,
            target_id=target["target_id"],
            metadata={
                "reason": "auto_send_disabled",
                "detail": "ACQUISITION_AUTO_SEND_ENABLED=false",
                "email": lead.contact_email,
                "auto_send_flag_enabled": False,
            },
            base=base,
        )

    # Target always remains draft_only during discovery — operator must approve
    target["outreach_status"] = "draft_only"
    target["auto_send_blocked"] = not auto_send_flag_enabled
    target["requires_operator_approval"] = True

    telemetry.emit(
        "acquisition_message_sent",
        target_id=target["target_id"],
        success=False,  # Never auto-sent during discovery
        message="draft_only",
        metadata={
            **msg,
            "auto_send_flag_enabled": auto_send_flag_enabled,
            "blocked_reason": "operator_approval_required" if auto_send_flag_enabled else "auto_send_disabled",
        },
        base=base,
    )
    try:
        from services.alerts import alert_high_fit_target

        alert_high_fit_target(target)
    except Exception:
        pass

    # PATCH 13A-8A: email_sent is always False during discovery — operator must approve
    return {
        "ok": True,
        "target": target,
        "lead": lead.to_dict(),
        "email_sent": False,
        "email_result": {},
        "requires_operator_approval": True,
        "auto_send_enabled": auto_send_flag_enabled,
    }


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
    
    # RE-SCORE WITH LIVE TUNED ENGINE - don't trust cached scores
    from .acquisition_probability import compute_acquisition_probability
    for t in targets:
        if not t.get("qualification"):
            continue
        try:
            # Apply live scoring using current tuned logic
            prob = compute_acquisition_probability(
                qualification=t.get("qualification", {}),
                classification=t.get("classification", {}),
                discovery_meta=t.get("discovery_meta", {}),
            )
            # Update with fresh scores
            t["qualification_score"] = prob.get("overall_confidence", t.get("qualification_score", 0))
            t["fit_score"] = prob.get("fit_score", t.get("fit_score", 0))
            t["priority_score"] = prob.get("acquisition_priority_score", t.get("priority_score", 0))
        except Exception:
            pass  # Keep cached scores if re-scoring fails
    
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

    founding_pilot: Dict[str, Any] = {}
    try:
        from services.intake.stats import get_intake_status as get_founding_pilot_status

        founding_pilot = get_founding_pilot_status(base)
    except Exception:
        pass

    return {
        "ok": True,
        "founding_pilot": founding_pilot,
        "doctrine": {
            "positioning": "burden_removal",
            "message": messaging.CORE_HEADLINE + " " + messaging.CORE_SUBLINE,
            "primary_route": "/ui/shop.html",
            "upload_route": "/ui/intake",
            "success_metric": "real_paperwork_submitted",
        },
        "hottest_targets": hottest,
        "live_connectors": [
            {"id": "usaspending_live", "status": "active", "lawful": True},
            {
                "id": "reddit_live",
                "status": "active",
                "lawful": True,
                "auto_post": _reddit_auto_post_enabled(),
                "note": "Autonomous post when REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD are set.",
            },
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
        parts.append("Collecting real upload telemetry — run discovery cycle and route traffic to shop/upload.")
    return " ".join(parts)


def approve_and_invite_lead(
    lead_id: str,
    *,
    base: Optional[Path] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Operator approves a lead — system builds a tracked upload URL and drafts the outreach."""
    from .storage import load_all_leads, rewrite_leads_csv, leads_dir, LEAD_JSONL
    import json as _json

    leads, _ = load_all_leads(base)
    target: Optional[Lead] = None
    for lead in leads:
        if lead.lead_id == lead_id:
            target = lead
            break
    if target is None:
        return {"ok": False, "error": "lead_not_found", "lead_id": lead_id}

    if target.status in ("rejected", "do_not_contact"):
        return {"ok": False, "error": "lead_not_eligible", "lead_id": lead_id, "status": target.status}

    from .routing import build_upload_route, get_public_base_url

    route = build_upload_route(
        lead_id=lead_id,
        segment=target.segment or "compliance-heavy",
        campaign_id="operator-approved",
        message_variant="invite",
        destination="shop",
        base_url=base_url or get_public_base_url(),
    )
    invite_url = route["primary_url"]
    # Direct upload URL bypasses shop page — drops the prospect straight into the upload form
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    _parsed = urlparse(invite_url)
    upload_url = urlunparse(_parsed._replace(path="/ui/intake"))

    from services.communications.email_service import send_outreach_invite

    # Autonomous send — KYC email service owns dispatch, fallback, and record
    email_result = send_outreach_invite(
        to_email=target.contact_email,
        company_name=target.company_name,
        contact_name=target.contact_name,
        invite_url=invite_url,
        upload_url=upload_url,
        lead_id=lead_id,
    )
    email_sent = bool(email_result.get("sent"))

    prev_status = target.status
    if target.status in ("new", "reviewed"):
        target.status = "approved_for_outreach" if email_sent else "approved_pending_send"
    target.updated_utc = utc_now()
    target.inquiry_routed_link = invite_url

    # Persist updated lead
    path = leads_dir(base) / LEAD_JSONL
    with path.open("w", encoding="utf-8") as f:
        for lead in leads:
            f.write(_json.dumps(lead.to_dict(), ensure_ascii=False) + "\n")
    rewrite_leads_csv(leads)

    # Telemetry
    telemetry.emit(
        event_type="lead_approved_for_outreach",
        lead_id=lead_id,
        metadata={
            "invite_url": invite_url,
            "email_sent": email_sent,
            "email_skipped_reason": email_result.get("reason") or email_result.get("error") or "",
            "prev_status": prev_status,
            "company": target.company_name,
        },
    )

    return {
        "ok": True,
        "lead_id": lead_id,
        "company_name": target.company_name,
        "contact_name": target.contact_name,
        "contact_email": target.contact_email,
        "status": target.status,
        "invite_url": invite_url,
        "upload_url": upload_url,
        "email_sent": email_sent,
        "email_result": {k: v for k, v in email_result.items() if k != "draft"},
        # Only include the draft if email was NOT sent — so operator can manually follow up
        "email_draft": email_result.get("draft") if not email_sent else None,
        "smtp_note": "" if email_sent else (
            email_result.get("reason") or email_result.get("error") or "smtp_unconfigured"
        ),
    }

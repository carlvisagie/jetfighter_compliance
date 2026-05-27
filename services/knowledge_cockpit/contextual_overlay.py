"""Contextual Knowledge Overlay — explain what the operator is viewing right now."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .acquisition_context import build_acquisition_context
from .compliance_context import build_compliance_context
from .concept_graph import related_concepts, suggest_next_learning
from .evidence_context import build_evidence_context
from .operational_explainer import explain_text


def _five_questions(
    *,
    what_am_i_looking_at: str,
    why_it_matters: str,
    terms_explained: List[Dict[str, Any]],
    watch_for: List[str],
    do_next: List[str],
    good_or_bad: Optional[List[str]] = None,
) -> Dict[str, Any]:
    out = {
        "what_am_i_looking_at": what_am_i_looking_at,
        "why_it_matters": why_it_matters,
        "what_terms_mean": terms_explained,
        "what_to_watch_for": watch_for,
        "what_to_do_next": do_next,
    }
    if good_or_bad:
        out["what_is_good_or_bad"] = good_or_bad
    return out


def build_overlay(*, view: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return overlay bundle for Control Center contextual assistant."""
    p = payload or {}
    view_key = (view or "generic").strip().lower()

    if view_key == "reddit_opportunity":
        return _overlay_reddit(p)
    if view_key == "compliance_update":
        return _overlay_compliance(p)
    if view_key == "evidence_upload":
        return _overlay_evidence(p)
    if view_key == "telemetry_signal":
        return _overlay_telemetry(p)
    if view_key == "acquisition_target":
        return _overlay_acquisition_target(p)
    if view_key == "organism_health":
        return _overlay_organism_health(p)
    if view_key == "reddit_panel":
        return _overlay_reddit_panel(p)
    if view_key == "acquisition_panel":
        return _overlay_acquisition_panel(p)
    if view_key == "compliance_panel":
        return _overlay_compliance_panel(p)
    if view_key == "evidence_panel":
        return _overlay_evidence_panel(p)
    if view_key == "alerts_panel":
        return _overlay_alerts_panel(p)
    if view_key == "friction_panel":
        return _overlay_friction_panel(p)
    if view_key == "telemetry_panel":
        return _overlay_telemetry_panel(p)
    if view_key == "cockpit_guidance":
        return _overlay_cockpit_guidance(p)
    return _overlay_generic(p)


def _overlay_reddit(p: Dict[str, Any]) -> Dict[str, Any]:
    title = p.get("title", "")
    body = p.get("body", "") or p.get("selftext", "") or " ".join(p.get("pain_themes") or [])
    ctx = build_acquisition_context(
        title=title,
        body=body,
        discovery_cluster=p.get("discovery_source_cluster", ""),
        burden_category=p.get("burden_category", ""),
        prey_reasons=p.get("prey_reasons") or [],
    )
    prey = int(p.get("prey_score") or 0)
    intent = p.get("author_intent", "")
    what = (
        f"Reddit acquisition opportunity: prey score {prey}, intent {intent or 'unknown'}. "
        f"{ctx.get('prospect_likely_means', '')}"
    )
    why = (
        "This person may be operationally burdened — a potential upload-first customer if they are "
        "seeking help (not giving advice or promoting services)."
    )
    if prey < 52:
        why += " Prey score is below queue threshold — organism suggests caution."
    terms = []
    for c in ctx.get("related_concepts") or []:
        terms.append({"term": c.get("term"), "id": c.get("id"), "hint": "Related compliance concept"})
    if p.get("discovery_source_cluster"):
        terms.insert(0, {"term": p["discovery_source_cluster"], "hint": "Discovery cluster"})
    watch = [
        "Predator signals (consultant, AMA, book a call)",
        "Topic-only discussion without operational need",
        "Advice-giver vs advice-seeker intent mismatch",
    ]
    if (p.get("prey_reasons") or []):
        watch.append("Prey reasons: " + ", ".join((p.get("prey_reasons") or [])[:4]))
    nxt = list(ctx.get("suggested_actions") or [])[:3]
    nxt.append("Approve only if burden + seeker intent align; deny predators and topic chatter.")
    good_bad = []
    if prey >= 52 and (intent or "").lower() in ("seeker", "question", "help"):
        good_bad.append("Good: prey score and seeker intent — strong upload-first candidate.")
    elif prey >= 52:
        good_bad.append("Watch: prey score OK but verify intent is seeker not advisor.")
    else:
        good_bad.append("Bad: low prey score — likely not operational burden.")
    if p.get("burden_category"):
        good_bad.append(f"Signal: burden category {p.get('burden_category')}.")
    return {
        "ok": True,
        "view": "reddit_opportunity",
        "title": "Reddit prey — operational context",
        "acquisition_context": ctx,
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=terms[:8],
            watch_for=watch,
            do_next=nxt,
            good_or_bad=good_bad,
        ),
        "related_concepts": ctx.get("related_concepts", []),
        "suggested_next_learning": suggest_next_learning("vendor-questionnaire"),
    }


def _overlay_compliance(p: Dict[str, Any]) -> Dict[str, Any]:
    summary = p.get("diff_summary") or p.get("summary") or ""
    frameworks = p.get("frameworks") or []
    if isinstance(frameworks, str):
        frameworks = [frameworks]
    ctx = build_compliance_context(
        summary=summary,
        frameworks=frameworks,
        change_id=p.get("change_id", ""),
    )
    what = f"Compliance intelligence change from {p.get('source_id', 'source')}: {summary[:300]}"
    why = ctx.get("why_operator_should_care", "")
    terms = [{"term": c.get("term"), "id": c.get("id")} for c in ctx.get("affected_concepts") or []]
    watch = ["Not legal advice — operator review required", "Customer auto-publish is off in v1"]
    if p.get("severity") in ("high", "critical"):
        watch.append("Elevated severity — check SSP/POA&M and customer messaging")
    nxt = ["Review change in Compliance Intelligence panel", "Update runbooks if approved", "Note acquisition messaging if frameworks affect prospects"]
    return {
        "ok": True,
        "view": "compliance_update",
        "title": "Compliance update",
        "compliance_context": ctx,
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=terms,
            watch_for=watch,
            do_next=nxt,
        ),
        "related_concepts": ctx.get("affected_concepts", []),
        "plain_english": ctx.get("plain_english", ""),
    }


def _overlay_evidence(p: Dict[str, Any]) -> Dict[str, Any]:
    ctx = build_evidence_context(
        filename=p.get("filename", "") or p.get("source_file", ""),
        document_type=p.get("document_type", ""),
        text_preview=p.get("text_preview", ""),
    )
    what = f"Uploaded evidence ({ctx.get('document_type', 'unknown')}): {p.get('filename', 'file')}"
    why = "Customers upload messy real paperwork — the organism classifies and maps it to controls for gap analysis."
    primary = ctx.get("primary_concept") or {}
    terms = [{"term": primary.get("term"), "id": primary.get("id")}]
    for c in ctx.get("related_concepts") or []:
        if c.get("id") != primary.get("id"):
            terms.append({"term": c.get("term"), "id": c.get("id")})
    watch = ["Wrong environment screenshot", "Stale policy date", "Missing owner on policy"]
    nxt = list(ctx.get("what_to_check_next") or [])
    nxt.append("Map to questionnaire row and POA&M if gap")
    return {
        "ok": True,
        "view": "evidence_upload",
        "title": "Evidence upload",
        "evidence_context": ctx,
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=terms,
            watch_for=watch,
            do_next=nxt,
        ),
        "operational_meaning": ctx.get("operational_meaning", ""),
    }


def _overlay_telemetry(p: Dict[str, Any]) -> Dict[str, Any]:
    et = p.get("event_type", "")
    sub = p.get("subsystem", "")
    msg = p.get("message", "")
    what = f"Telemetry: {sub}/{et}. {msg}"
    why = "The organism nervous system — confirms subsystems are alive and surfaces anomalies early."
    action_needed = et in (
        "fetch_failed",
        "moderation_removed",
        "intent_false_positive",
        "source_unreachable",
        "source_stale",
    )
    watch = ["Repeated failures may need threshold tuning", "Silence can mean subsystem not emitting"]
    nxt = ["Acknowledge alert if critical", "Drill into central memory timeline"] if action_needed else ["No immediate action — monitor"]
    explain = explain_text(msg or et)
    return {
        "ok": True,
        "view": "telemetry_signal",
        "title": "Organism telemetry",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=explain.get("matched_concepts") or [],
            watch_for=watch,
            do_next=nxt,
        ),
        "action_needed": action_needed,
    }


def _overlay_acquisition_target(p: Dict[str, Any]) -> Dict[str, Any]:
    blob = f"{p.get('company_name', '')} {p.get('pain_signal', '')} {p.get('source', '')}"
    explain = explain_text(blob)
    what = f"Acquisition target: {p.get('company_name', 'unknown')} via {p.get('source', '')}"
    why = "Pipeline prospect — organism scored fit and pain for controlled outreach (manual approval)."
    nxt = ["Verify burden is operational not consultant", "Use upload-first route if outreach approved"]
    return {
        "ok": True,
        "view": "acquisition_target",
        "title": "Acquisition target",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=explain.get("matched_concepts") or [],
            watch_for=["Low qualification score", "No pain signal"],
            do_next=nxt,
        ),
    }


def _overlay_organism_health(p: Dict[str, Any]) -> Dict[str, Any]:
    verdict = p.get("verdict", "")
    orphans = p.get("orphan_count", 0)
    what = f"Organism health: {verdict or 'checking'}. Orphan warnings: {orphans}."
    why = "Central memory and telemetry integrity keep the solo operator from flying blind."
    nxt = []
    if orphans:
        nxt.append("Run self-heal and link orphan projects")
    nxt.append("Review bottlenecks in guidance panel")
    return {
        "ok": True,
        "view": "organism_health",
        "title": "Organism health",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[],
            watch_for=["Rising orphan count", "Telemetry silence > 24h"],
            do_next=nxt,
        ),
    }


def _overlay_reddit_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    selected = p.get("selected_opportunity")
    if isinstance(selected, dict) and selected.get("post_id"):
        return _overlay_reddit(selected)
    pending = int(p.get("pending_count") or 0)
    what = f"Reddit acquisition queue — {pending} prospect(s) awaiting approve/deny."
    why = (
        "The organism hunted operational burden (not topic chatter). You only approve or deny; "
        "it handles pacing, safety, and reply wording."
    )
    good_bad = []
    if pending:
        good_bad.append(f"Good: {pending} real candidate(s) in queue — review prey score and intent.")
    else:
        good_bad.append("Neutral: queue empty — run discovery or wait for next cycle.")
    good_bad.append("Bad: approving predators, consultants, or advice-givers wastes trust.")
    nxt = ["Click a prospect card to see prey/burden detail", "Approve only burdened seekers", "Deny predators and topic-only posts"]
    if not pending:
        nxt = ["Run discovery", "Check acquisition intelligence for other channels"]
    return {
        "ok": True,
        "view": "reddit_panel",
        "title": "Reddit acquisition",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[
                {"term": "Prey score", "hint": "Burden + seeker intent composite"},
                {"term": "Burden signals", "hint": "Operational pain indicators"},
            ],
            watch_for=["Prey score below ~52", "Predator badges", "Intent mismatch"],
            do_next=nxt,
            good_or_bad=good_bad,
        ),
    }


def _overlay_acquisition_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    conv = p.get("upload_conversion") or {}
    rate = float(conv.get("rate") or 0)
    started = int(conv.get("started") or 0)
    completed = int(conv.get("completed") or 0)
    hottest = p.get("hottest_targets") or []
    what = (
        f"Acquisition intelligence — upload conversion {rate * 100:.1f}% "
        f"({completed}/{started}). Success = real paperwork submitted."
    )
    why = (
        "The organism finds operational burden and routes prospects to upload-first onboarding. "
        "No auto-spam — drafts await your judgment."
    )
    good_bad = []
    if rate >= 0.15 and completed > 0:
        good_bad.append("Good: real paperwork is converting — engine is producing outcomes.")
    elif started > 0:
        good_bad.append("Watch: uploads started but conversion low — friction or targeting issue.")
    else:
        good_bad.append("Watch: no upload conversions yet — pipeline warming or outreach not landed.")
    if hottest:
        good_bad.append(f"Good: {len(hottest)} hot target(s) scored with pain signals.")
    terms = [{"term": "Upload-first", "hint": "Customer uploads before self-diagnosing compliance"}]
    explain = explain_text(p.get("what_organism_is_learning") or "CMMC questionnaire burden")
    terms.extend(
        {"term": c.get("term"), "id": c.get("id")}
        for c in (explain.get("matched_concepts") or [])[:4]
    )
    return {
        "ok": True,
        "view": "acquisition_panel",
        "title": "Acquisition intelligence",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=terms,
            watch_for=["Consultant pain vs real SMB burden", "Outreach without upload route", "Low qualification scores"],
            do_next=[
                "Review hottest targets for operational pain",
                "Use upload-first route links only after manual approval",
                "Run live fetch when pipeline is thin",
            ],
            good_or_bad=good_bad,
        ),
    }


def _overlay_compliance_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    pending = int(p.get("pending_review_count") or 0)
    changes = p.get("latest_changes") or []
    stale = p.get("stale_sources") or []
    unreachable = p.get("unreachable_sources") or []
    what = (
        f"Compliance intelligence watch — {pending} change(s) pending review, "
        f"{len(changes)} recent source update(s) tracked."
    )
    why = "Authoritative public sources are monitored so you know when frameworks or guidance shift — operator review required."
    good_bad = []
    if pending:
        good_bad.append(f"Watch: {pending} item(s) need your review before customers are affected.")
    else:
        good_bad.append("Good: no pending compliance reviews right now.")
    if stale or unreachable:
        good_bad.append(f"Bad: source health issues — stale={len(stale)}, unreachable={len(unreachable)}.")
    else:
        good_bad.append("Good: sources reachable and fresh.")
    terms = []
    for c in changes[-3:]:
        blob = (c.get("diff_summary") or "")[:200]
        for m in explain_text(blob).get("matched_concepts") or []:
            terms.append({"term": m.get("term"), "id": m.get("id")})
    return {
        "ok": True,
        "view": "compliance_panel",
        "title": "Compliance intelligence",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=terms[:6],
            watch_for=["Not legal advice", "High severity without SSP/POA&M check", "Customer auto-publish off"],
            do_next=[
                "Open a recent change for plain-English impact",
                "Update runbooks if you approve a change",
                "Note acquisition messaging if frameworks shift",
            ],
            good_or_bad=good_bad,
        ),
    }


def _overlay_evidence_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    pid = p.get("project_id") or ""
    uploaded = int(p.get("files_uploaded") or 0)
    analyzed = int(p.get("files_analyzed") or 0)
    missing = int(p.get("missing_item_count") or 0)
    pending = int(p.get("pending_analysis") or 0)
    cs = p.get("confidence_summary") or {}
    what = (
        f"Evidence intelligence for project {pid or '(none selected)'} — "
        f"{uploaded} uploaded, {analyzed} analyzed, {missing} gaps flagged."
    )
    why = "Upload-first customers send messy real files — the organism classifies, maps controls, and surfaces what is still missing."
    good_bad = []
    if not pid:
        good_bad.append("Watch: pick a project in the command strip to analyze evidence.")
    elif uploaded and analyzed:
        good_bad.append("Good: files are flowing through classification.")
    if missing:
        good_bad.append(f"Watch: {missing} missing item(s) — likely questionnaire or policy gaps.")
    if pending:
        good_bad.append(f"Watch: {pending} file(s) still pending analysis.")
    if cs.get("uncertain", 0) > cs.get("confirmed", 0):
        good_bad.append("Watch: more uncertain than confirmed — operator confirmation may be needed.")
    nxt = list(p.get("next_actions") or [])[:3]
    if not pid:
        nxt = ["Select project ID in command strip", "Refresh organism"]
    elif not nxt:
        nxt = ["Review missing items", "Confirm uncertain classifications"]
    return {
        "ok": True,
        "view": "evidence_panel",
        "title": "Evidence intelligence",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[
                {"term": "Evidence", "id": "evidence"},
                {"term": "SSP", "id": "ssp"},
            ],
            watch_for=["Wrong-environment screenshots", "Stale policy dates", "Unlabeled exports"],
            do_next=nxt,
            good_or_bad=good_bad,
        ),
    }


def _overlay_alerts_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    cfg = p.get("config") or {}
    tg = bool(cfg.get("telegram_configured"))
    email_on = bool(cfg.get("email_enabled"))
    crit = p.get("unacknowledged_critical") or []
    recent = p.get("recent_alerts") or []
    what = (
        f"Operational alerts — Telegram {'on' if tg else 'off'}, email {'on' if email_on else 'off'}, "
        f"{len(crit)} critical unacknowledged, {len(recent)} recent."
    )
    why = "Organism nervous system — tells you about conversions, paperwork, and failures without exposing customer documents in alerts."
    good_bad = []
    if tg or email_on:
        good_bad.append("Good: at least one alert channel is configured.")
    else:
        good_bad.append("Bad: neither Telegram nor email alerts configured — you may miss conversions.")
    if crit:
        good_bad.append(f"Bad: {len(crit)} critical alert(s) need acknowledgment.")
    else:
        good_bad.append("Good: no unacknowledged critical alerts.")
    nxt = []
    if crit:
        nxt.append("Acknowledge critical alerts first")
    if not tg:
        nxt.append("Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID for realtime")
    if not email_on:
        nxt.append("Enable email alerts in config")
    if not nxt:
        nxt = ["Monitor recent feed", "Send daily digest if quiet"]
    return {
        "ok": True,
        "view": "alerts_panel",
        "title": "Operational alerts",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[],
            watch_for=["Alert fatigue", "Missing first-paperwork notification", "Quiet hours blocking urgent"],
            do_next=nxt,
            good_or_bad=good_bad,
        ),
    }


def _overlay_friction_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    opened = int(p.get("continuation_opened") or 0)
    completed = int(p.get("continuation_completed") or 0)
    recovery = p.get("continuation_recovery_rate_pct")
    what = (
        f"Customer friction — continuation {completed}/{opened}"
        + (f" ({recovery}% recovery)" if recovery is not None else "")
        + "."
    )
    why = "Shows where customers stall during upload-first onboarding — fix friction before adding acquisition volume."
    good_bad = []
    if recovery is not None and recovery >= 50:
        good_bad.append("Good: continuation recovery is healthy.")
    elif opened:
        good_bad.append("Watch: customers open continuation links but do not finish.")
    else:
        good_bad.append("Neutral: limited continuation data in window.")
    return {
        "ok": True,
        "view": "friction_panel",
        "title": "Customer friction",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[{"term": "Upload-first", "id": "vendor-questionnaire"}],
            watch_for=["Abandonment at upload step", "Repeated help clicks", "Low continuation recovery"],
            do_next=["Fix top abandonment step", "Simplify inquiry page if upload stalls", "Review help telemetry items"],
            good_or_bad=good_bad,
        ),
    }


def _overlay_telemetry_panel(p: Dict[str, Any]) -> Dict[str, Any]:
    verdict = p.get("verdict") or p.get("observability_verdict") or ""
    events = int(p.get("telemetry_count") or 0)
    orphans = int(p.get("orphan_count") or 0)
    recent = p.get("recent_events") or []
    what = f"Organism telemetry & health — observability {verdict or 'unknown'}, {events} recent events, {orphans} orphan warnings."
    why = "Confirms subsystems are emitting signals and central memory integrity — fly blind if this goes quiet."
    good_bad = []
    if verdict == "organism_observable":
        good_bad.append("Good: organism is observable end-to-end.")
    elif verdict:
        good_bad.append(f"Watch: observability {verdict} — some subsystems may be warming up.")
    if orphans:
        good_bad.append(f"Bad: {orphans} orphan project(s) — run self-heal.")
    if events < 5:
        good_bad.append("Watch: low telemetry volume — check subsystem emitters.")
    nxt = ["Acknowledge critical telemetry", "Open central intelligence for timeline"] if orphans else ["Monitor recent activity feed"]
    if recent:
        last = recent[0]
        return {
            "ok": True,
            "view": "telemetry_panel",
            "title": "Telemetry & organism health",
            "overlay": _five_questions(
                what_am_i_looking_at=what + f" Latest: {last.get('subsystem', '')}/{last.get('event_type', '')}.",
                why_it_matters=why,
                terms_explained=[],
                watch_for=["fetch_failed", "source_stale", "Silence > 24h"],
                do_next=nxt,
                good_or_bad=good_bad,
            ),
        }
    return {
        "ok": True,
        "view": "telemetry_panel",
        "title": "Telemetry & organism health",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[],
            watch_for=["fetch_failed", "source_stale", "Silence > 24h"],
            do_next=nxt,
            good_or_bad=good_bad,
        ),
    }


def _overlay_cockpit_guidance(p: Dict[str, Any]) -> Dict[str, Any]:
    kind = p.get("panel") or "priority"
    what = f"Cockpit guidance — {kind.replace('_', ' ')} view for the solo operator."
    why = "Adaptive command surfaces what matters most so you do not scan every subsystem manually."
    return {
        "ok": True,
        "view": "cockpit_guidance",
        "title": "Cockpit guidance",
        "overlay": _five_questions(
            what_am_i_looking_at=what,
            why_it_matters=why,
            terms_explained=[],
            watch_for=["Stale guidance after refresh", "Missing project context in strip"],
            do_next=["Follow do-now in command strip", "Scroll to the panel that needs action"],
            good_or_bad=["Good: guidance refreshes with organism state."],
        ),
    }


def _overlay_generic(p: Dict[str, Any]) -> Dict[str, Any]:
    text = p.get("text", "") or p.get("query", "")
    explain = explain_text(text) if text else {"ok": False}
    return {
        "ok": True,
        "view": "generic",
        "title": "Knowledge overlay",
        "overlay": _five_questions(
            what_am_i_looking_at="Operator cockpit context",
            why_it_matters="The organism teaches in place so you do not memorize every framework.",
            terms_explained=explain.get("matched_concepts") or [] if explain.get("ok") else [],
            watch_for=["Predator prey", "Topic-only chatter"],
            do_next=["Select an item to explain", "Use search in overlay for any term"],
        ),
        "explain": explain,
    }

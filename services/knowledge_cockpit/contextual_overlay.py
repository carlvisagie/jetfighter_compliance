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
) -> Dict[str, Any]:
    return {
        "what_am_i_looking_at": what_am_i_looking_at,
        "why_it_matters": why_it_matters,
        "what_terms_mean": terms_explained,
        "what_to_watch_for": watch_for,
        "what_to_do_next": do_next,
    }


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

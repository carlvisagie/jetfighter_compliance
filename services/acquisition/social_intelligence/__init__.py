"""
Socially intelligent adaptive acquisition — trust before traffic.

The organism behaves like a calm knowledgeable human, not a sales bot.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from ..models import utc_now
from . import (
    conversational_memory,
    emotional_resonance,
    engagement_strategy,
    etiquette,
    familiarity,
    pacing,
    relationship_scoring,
    subreddit_culture,
    trust_building,
)
from .paths import SOCIAL_TELEMETRY_JSONL, ensure_social_intel_dir

__all__ = [
    "enrich_engagement_plan",
    "emit_social_telemetry",
    "record_engagement_outcome",
    "plan_social_engagement",
]


def emit_social_telemetry(
    event_type: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Any] = None,
) -> None:
    rec = {
        "event_id": f"SOC-{uuid.uuid4().hex[:10]}",
        "event_type": event_type,
        "when_utc": utc_now(),
        "metadata": metadata or {},
    }
    path = ensure_social_intel_dir(base) / SOCIAL_TELEMETRY_JSONL
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        from ..connectors.reddit import telemetry as rdt

        rdt.emit(event_type, metadata=metadata, base=base)
    except Exception:
        pass


def plan_social_engagement(
    post: Dict[str, Any],
    classification: Dict[str, Any],
    qualification: Dict[str, Any],
    base_plan: Dict[str, Any],
    *,
    state: Optional[Dict[str, Any]] = None,
    base: Optional[Any] = None,
) -> Dict[str, Any]:
    """Full social intelligence overlay on an autonomy plan."""
    return enrich_engagement_plan(
        base_plan, post, classification, qualification, state=state, base=base
    )


def enrich_engagement_plan(
    plan: Dict[str, Any],
    post: Dict[str, Any],
    classification: Dict[str, Any],
    qualification: Dict[str, Any],
    *,
    state: Optional[Dict[str, Any]] = None,
    base: Optional[Any] = None,
) -> Dict[str, Any]:
    """Apply trust-first social layer; may suppress links and adjust stage."""
    sub = (post.get("subreddit") or "").lower()
    author = post.get("author") or ""
    safety = (plan.get("subreddit_safety") or {})
    safety_score = int(safety.get("safety_score", 50))

    profile = subreddit_culture.get_subreddit_profile(sub, base)
    prior = conversational_memory.count_prior_touches(
        author=author, subreddit=sub, base=base
    )
    sub_stats = ((state or {}).get("subreddit_stats") or {}).get(sub, {})
    fam_score = familiarity.compute_familiarity(
        prior, subreddit_positive=int(profile.get("positive_engagements", 0))
    )

    trust_score = trust_building.compute_trust_score(
        safety_score=safety_score,
        familiarity_score=fam_score,
        emotional_burden=int(classification.get("emotional_burden_score", 0)),
        fit_score=int(qualification.get("fit_score", 0)),
        prior_approvals=prior.get("approved", 0),
        prior_removals=prior.get("removed", 0),
        prior_denials=prior.get("denied", 0),
    )

    rel = trust_building.relationship_state_from_signals(
        trust_score=trust_score,
        familiarity_score=fam_score,
        burden_score=int(classification.get("burden_score", 0)),
        prior_approvals=prior.get("approved", 0),
        link_tolerance=profile.get("link_tolerance", "cautious"),
    )

    relationship_stage = rel["relationship_stage"]
    relationship_state = rel["relationship_state"]

    strategy = engagement_strategy.choose_strategy(
        relationship_stage=relationship_stage,
        classification=classification,
        subreddit_profile=profile,
        trust_score=trust_score,
        show_queue=bool(plan.get("show_operator_queue")),
    )

    engagement_before_route = bool(plan.get("engagement_before_route"))
    link_allowed = trust_building.link_allowed_for_stage(
        relationship_stage,
        trust_score,
        link_tolerance=profile.get("link_tolerance", "cautious"),
        engagement_before_route=engagement_before_route,
    )

    # First contact on Reddit threads is almost always no-link
    if prior.get("total", 0) == 0 and relationship_stage < trust_building.STAGE_BURDEN_RELIEF:
        link_allowed = False

    if conversational_memory.over_engagement_risk(author, sub, base):
        plan["show_operator_queue"] = False
        plan["engagement_stage"] = "defer"
        plan["rationale"] = "Over-engagement risk — organism pauses to avoid unnatural cadence."
        strategy = "observe_only"

    pacing_info = pacing.decide_pacing(
        subreddit_profile=profile,
        last_approved_utc=str(sub_stats.get("last_approved_utc", "")),
        cooldown_hours=float(plan.get("cooldown_hours", 24)),
        relationship_stage=relationship_stage,
        over_engagement=conversational_memory.over_engagement_risk(author, sub, base),
    )

    rel_score = relationship_scoring.score_relationship(
        trust_score=trust_score,
        familiarity_score=fam_score,
        emotional_burden=int(classification.get("emotional_burden_score", 0)),
        safety_score=safety_score,
    )

    resonance = emotional_resonance.build_reply_guidance(classification, strategy)

    if plan.get("show_operator_queue"):
        mapped_stage = engagement_strategy.strategy_to_engagement_stage(
            strategy, plan.get("engagement_stage", "assist_soft")
        )
        plan["engagement_stage"] = mapped_stage
        if not link_allowed:
            plan["link_in_public_reply"] = False
            plan["link_appropriate"] = False
            if plan["engagement_stage"] == "assist_route":
                plan["engagement_stage"] = "assist_soft"
                plan["rationale"] = (
                    "Trust-first policy — helpful reply without link; "
                    + (plan.get("rationale") or "")
                )[:280]
        elif strategy == "upload_first_invitation" and link_allowed:
            plan["link_in_public_reply"] = True
            plan["link_appropriate"] = True
            plan["engagement_stage"] = "assist_route"

        plan["deployment_timing"] = pacing_info.get("deployment_timing", plan.get("deployment_timing"))

    social = {
        "relationship_state": relationship_state,
        "relationship_stage": relationship_stage,
        "trust_score": trust_score,
        "familiarity_score": fam_score,
        "engagement_strategy": strategy,
        "link_allowed": link_allowed,
        "subreddit_profile": {
            "link_tolerance": profile.get("link_tolerance"),
            "prefers_concise": profile.get("prefers_concise"),
            "moderation_strictness": profile.get("moderation_strictness"),
        },
        "pacing": pacing_info,
        "relationship_score": rel_score["relationship_score"],
        "relationship_band": rel_score["relationship_band"],
        "emotional_resonance": resonance,
        "prior_touches": prior,
        "trust_first": True,
    }
    plan["social_intelligence"] = social
    plan["relationship_state"] = relationship_state
    plan["relationship_stage"] = relationship_stage
    plan["trust_score"] = trust_score
    plan["engagement_strategy"] = strategy

    emit_social_telemetry(
        "trust_progression",
        metadata={
            "post_id": post.get("post_id"),
            "subreddit": sub,
            "relationship_state": relationship_state,
            "relationship_stage": relationship_stage,
            "trust_score": trust_score,
            "strategy": strategy,
            "link_allowed": link_allowed,
        },
        base=base,
    )
    return plan


def record_engagement_outcome(
    outcome: str,
    *,
    post: Dict[str, Any],
    plan: Optional[Dict[str, Any]] = None,
    phrasing: str = "",
    base: Optional[Any] = None,
) -> None:
    """Record outcome for memory + subreddit culture learning."""
    sub = (post.get("subreddit") or "").lower()
    social = (plan or {}).get("social_intelligence") or plan or {}
    conversational_memory.record_engagement(
        post_id=post.get("post_id", ""),
        subreddit=sub,
        author=post.get("author", ""),
        outcome=outcome,
        phrasing=phrasing,
        relationship_state=social.get("relationship_state", ""),
        trust_score=int(social.get("trust_score", 0)),
        strategy=social.get("engagement_strategy", ""),
        base=base,
    )
    subreddit_culture.record_subreddit_outcome(sub, outcome, base=base)
    emit_social_telemetry(
        "engagement_outcome",
        metadata={"outcome": outcome, "subreddit": sub, "post_id": post.get("post_id")},
        base=base,
    )

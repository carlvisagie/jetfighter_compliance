"""
Reddit engagement autonomy — organism decides pacing, safety, wording, links.

Operator role: strategic approve / deny only. No auto-post to Reddit.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...models import utc_now
from .learning import load_learning_state

# Subreddits where helpful tone is usually welcome (learned stats can override)
DEFAULT_SAFE_SUBREDDITS = frozenset(
    {
        "smallbusiness",
        "cybersecurity",
        "cmmc",
        "nist800171",
        "govcontracts",
        "defensecontracting",
        "manufacturing",
        "entrepreneur",
    }
)

RISKY_SUBREDDITS = frozenset(
    {
        "politics",
        "news",
        "worldnews",
        "antiwork",
        "jobs",
    }
)

STAGES = (
    "skip_unsafe",
    "defer",
    "empathize_only",
    "assist_soft",
    "assist_route",
)


def assess_subreddit_safety(subreddit: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sub = (subreddit or "").lower().strip()
    state = state or load_learning_state()
    stats = (state.get("subreddit_stats") or {}).get(sub, {})
    score = 70
    if sub in DEFAULT_SAFE_SUBREDDITS:
        score += 15
    if sub in RISKY_SUBREDDITS:
        score -= 50
    mod_removed = int(stats.get("moderation_removed", 0))
    ignores = int(stats.get("operator_denied", 0))
    approvals = int(stats.get("operator_approved", 0))
    uploads = int(stats.get("uploads_completed", 0))
    score += min(20, approvals * 2 + uploads * 5)
    score -= min(40, mod_removed * 15 + ignores * 3)
    score = max(0, min(100, score))
    return {
        "subreddit": sub,
        "safety_score": score,
        "safe": score >= 55,
        "reason": "learned_trust" if approvals or uploads else ("default_safe" if sub in DEFAULT_SAFE_SUBREDDITS else "caution"),
    }


def decide_engagement(
    post: Dict[str, Any],
    classification: Dict[str, Any],
    qualification: Dict[str, Any],
    *,
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Full organism plan for one Reddit opportunity.
    Determines stage, link use, pacing, wording, and operator queue eligibility.
    """
    state = state or load_learning_state()
    sub = (post.get("subreddit") or "").lower()
    safety = assess_subreddit_safety(sub, state)
    fit = int(qualification.get("fit_score", 0))
    burden = int(classification.get("burden_score", 0))
    emotional = int(classification.get("emotional_burden_score", 0))
    num_comments = int(post.get("num_comments") or 0)

    sub_stats = (state.get("subreddit_stats") or {}).get(sub, {})
    cooldown_h = float(sub_stats.get("cooldown_hours", state.get("default_cooldown_hours", 24)))
    wording_variant = _pick_wording_variant(state, burden, emotional)

    if not safety["safe"]:
        return _plan(
            stage="skip_unsafe",
            safety=safety,
            link_in_public_reply=False,
            show_operator=False,
            rationale="Subreddit trust too low — organism will not engage.",
            wording_variant=wording_variant,
            cooldown_hours=cooldown_h,
        )

    intent = classification.get("author_intent", "UNKNOWN")
    recommended = classification.get("recommended_action", "ignore")
    seeker = int(classification.get("advice_seeker_score", 0))
    giver = int(classification.get("advice_giver_score", 0))

    if intent == "GIVING_ADVICE" or recommended in ("competitor_or_expert", "monitor_only"):
        return _plan(
            stage="defer",
            safety=safety,
            link_in_public_reply=False,
            show_operator=False,
            rationale="Advice-giver or expert — monitor thread only, no outreach.",
            wording_variant=wording_variant,
            cooldown_hours=cooldown_h,
        )

    if intent == "PROMOTING_SERVICE":
        return _plan(
            stage="defer",
            safety=safety,
            link_in_public_reply=False,
            show_operator=False,
            rationale="Promotional post — ignored (competitor watch only).",
            wording_variant=wording_variant,
            cooldown_hours=cooldown_h,
        )

    if intent == "DISCUSSING_NEWS" and seeker <= giver:
        return _plan(
            stage="defer",
            safety=safety,
            link_in_public_reply=False,
            show_operator=False,
            rationale="News discussion — context only, not a prospect thread.",
            wording_variant=wording_variant,
            cooldown_hours=cooldown_h,
        )

    prob = qualification.get("acquisition_probability") or {}
    prey_tier = int(qualification.get("prey_tier") or prob.get("prey_tier", 4))
    operational_prey = bool(
        qualification.get("queue_eligible")
        or (
            prey_tier <= 3
            and prob.get("has_operational_need")
            and int(qualification.get("prey_score") or prob.get("prey_score", 0)) >= 46
        )
    )

    if (
        intent not in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED")
        and recommended != "approve_engagement"
        and not operational_prey
    ):
        return _plan(
            stage="defer",
            safety=safety,
            link_in_public_reply=False,
            show_operator=False,
            rationale=f"Intent {intent} — not deployable for outreach.",
            wording_variant=wording_variant,
            cooldown_hours=cooldown_h,
        )

    if fit < 45:
        return _plan(
            stage="defer",
            safety=safety,
            link_in_public_reply=False,
            show_operator=False,
            rationale="Low fit — deferred by organism.",
            wording_variant=wording_variant,
            cooldown_hours=cooldown_h,
        )

    engagement_before_route = burden >= 60 and num_comments < 5 and emotional >= 50
    link_ok = fit >= 60 and burden >= 40 and not engagement_before_route
    high_trust = safety["safety_score"] >= 75 and fit >= 70

    if engagement_before_route:
        stage = "empathize_only"
        rationale = "High burden thread — empathize first; route only after rapport (organism policy)."
    elif link_ok and high_trust:
        stage = "assist_route"
        rationale = "Safe subreddit and strong fit — soft upload-first route may help."
    elif fit >= 55:
        stage = "assist_soft"
        rationale = "Helpful reply without link — build trust naturally."
    else:
        stage = "empathize_only"
        rationale = "Calm helper tone only — no link yet."

    pacing = "ready_now"
    if sub_stats.get("last_approved_utc"):
        pacing = "respect_cooldown"
    follow_up_h = int(state.get("default_follow_up_hours", 48))
    if stage == "assist_route":
        follow_up_h = 72

    plan = _plan(
        stage=stage,
        safety=safety,
        link_in_public_reply=(stage == "assist_route"),
        show_operator=True,
        rationale=rationale,
        wording_variant=wording_variant,
        cooldown_hours=cooldown_h,
        pacing=pacing,
        follow_up_hours=follow_up_h,
        engagement_before_route=engagement_before_route,
        organism_confidence=min(95, (fit + safety["safety_score"]) // 2),
    )
    try:
        from ...social_intelligence import enrich_engagement_plan

        plan = enrich_engagement_plan(plan, post, classification, qualification, state=state)
    except Exception:
        pass

    prey_score = int(qualification.get("prey_score", 0))
    plan["prey_score"] = prey_score
    plan["prey_reasons"] = qualification.get("prey_reasons") or (qualification.get("acquisition_probability") or {}).get("prey_reasons", [])
    return plan


def _pick_wording_variant(state: Dict[str, Any], burden: int, emotional: int) -> str:
    winners = state.get("wording_winners") or {"A": 0, "B": 0}
    if emotional >= 60 and winners.get("B", 0) >= winners.get("A", 0):
        return "B"
    if burden >= 50:
        return "A"
    return "A" if winners.get("A", 0) >= winners.get("B", 0) else "B"


def _plan(
    *,
    stage: str,
    safety: Dict[str, Any],
    link_in_public_reply: bool,
    show_operator: bool,
    rationale: str,
    wording_variant: str,
    cooldown_hours: float,
    pacing: str = "ready_now",
    follow_up_hours: int = 48,
    engagement_before_route: bool = False,
    organism_confidence: int = 50,
) -> Dict[str, Any]:
    return {
        "engagement_stage": stage,
        "link_in_public_reply": link_in_public_reply,
        "link_appropriate": link_in_public_reply,
        "subreddit_safety": safety,
        "wording_variant": wording_variant,
        "deployment_timing": pacing,
        "cooldown_hours": cooldown_hours,
        "follow_up_cadence_hours": follow_up_hours,
        "engagement_before_route": engagement_before_route,
        "organism_confidence": organism_confidence,
        "show_operator_queue": show_operator,
        "operator_actions": ["approve", "deny"],
        "rationale": rationale,
        "platform_trust_priority": True,
        "when_utc": utc_now(),
    }

"""Trust-building relationship states — trust before route."""
from __future__ import annotations

from typing import Any, Dict

RELATIONSHIP_STATES = (
    "first_contact",
    "familiar_presence",
    "trusted_participant",
    "burden_relief_opportunity",
    "onboarding_ready",
)

# Numeric stages 0–5 for progression gating
STAGE_OBSERVE = 0
STAGE_HELP_NO_LINK = 1
STAGE_VALUE_NO_LINK = 2
STAGE_FAMILIAR = 3
STAGE_BURDEN_RELIEF = 4
STAGE_ONBOARDING = 5

STATE_TO_STAGE = {
    "first_contact": STAGE_HELP_NO_LINK,
    "familiar_presence": STAGE_VALUE_NO_LINK,
    "trusted_participant": STAGE_FAMILIAR,
    "burden_relief_opportunity": STAGE_BURDEN_RELIEF,
    "onboarding_ready": STAGE_ONBOARDING,
}


def compute_trust_score(
    *,
    safety_score: int,
    familiarity_score: int,
    emotional_burden: int,
    fit_score: int,
    prior_approvals: int = 0,
    prior_removals: int = 0,
    prior_denials: int = 0,
) -> int:
    """0–100 trust score — platform + relationship, not sales pressure."""
    score = 25
    score += min(25, safety_score // 4)
    score += min(20, familiarity_score // 5)
    score += min(15, emotional_burden // 7)
    score += min(15, fit_score // 7)
    score += min(10, prior_approvals * 4)
    score -= min(35, prior_removals * 12 + prior_denials * 4)
    return max(0, min(100, score))


def relationship_state_from_signals(
    *,
    trust_score: int,
    familiarity_score: int,
    burden_score: int,
    prior_approvals: int,
    link_tolerance: str,
) -> Dict[str, Any]:
    """Map trust + history to relationship_state and stage."""
    if trust_score < 30:
        state = "first_contact"
    elif trust_score < 50 or familiarity_score < 15:
        state = "familiar_presence"
    elif trust_score < 65:
        state = "trusted_participant"
    elif burden_score >= 50 and trust_score >= 70 and prior_approvals >= 1:
        state = "burden_relief_opportunity"
    elif (
        trust_score >= 78
        and familiarity_score >= 40
        and burden_score >= 45
        and prior_approvals >= 2
        and link_tolerance in ("tolerate", "welcome")
    ):
        state = "onboarding_ready"
    elif trust_score >= 60 and burden_score >= 55:
        state = "burden_relief_opportunity"
    else:
        state = "trusted_participant"

    stage = STATE_TO_STAGE.get(state, STAGE_HELP_NO_LINK)
    return {
        "relationship_state": state,
        "relationship_stage": stage,
        "trust_score": trust_score,
    }


def link_allowed_for_stage(
    relationship_stage: int,
    trust_score: int,
    *,
    link_tolerance: str,
    engagement_before_route: bool,
) -> bool:
    """KYC/upload route only when trust and culture allow."""
    if engagement_before_route:
        return False
    if link_tolerance == "hate":
        return False
    min_trust = {0: 999, 1: 999, 2: 999, 3: 88, 4: 78, 5: 68}.get(relationship_stage, 999)
    if trust_score < min_trust:
        return False
    if relationship_stage < STAGE_BURDEN_RELIEF:
        return False
    if link_tolerance == "cautious" and relationship_stage < STAGE_ONBOARDING:
        return False
    return True

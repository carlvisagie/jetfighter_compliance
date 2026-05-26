"""Engagement strategy selection — help first, route last."""
from __future__ import annotations

from typing import Any, Dict

STRATEGIES = (
    "observe_only",
    "helpful_clarification",
    "practical_checklist",
    "emotional_reassurance",
    "technical_explanation",
    "follow_up_engagement",
    "burden_relief_introduction",
    "upload_first_invitation",
)


def choose_strategy(
    *,
    relationship_stage: int,
    classification: Dict[str, Any],
    subreddit_profile: Dict[str, Any],
    trust_score: int,
    show_queue: bool,
) -> str:
    if not show_queue:
        return "observe_only"

    emotional = int(classification.get("emotional_burden_score", 0))
    themes = classification.get("pain_themes") or []
    intent = classification.get("author_intent", "")

    if relationship_stage <= 0:
        return "observe_only"
    if relationship_stage <= 1:
        if emotional >= 55 or intent == "VENTING_OR_OVERWHELMED":
            return "emotional_reassurance"
        return "helpful_clarification"
    if relationship_stage == 2:
        if "paperwork" in str(themes) or "documentation" in str(themes):
            return "practical_checklist"
        return "technical_explanation"
    if relationship_stage == 3:
        return "follow_up_engagement"
    if relationship_stage == 4:
        return "burden_relief_introduction"
    if relationship_stage >= 5 and trust_score >= 70:
        if subreddit_profile.get("link_tolerance") in ("tolerate", "welcome"):
            return "upload_first_invitation"
        return "burden_relief_introduction"
    return "helpful_clarification"


def strategy_to_engagement_stage(strategy: str, base_stage: str) -> str:
    """Map social strategy to reddit autonomy stage."""
    if strategy == "observe_only":
        return "defer"
    if strategy == "upload_first_invitation":
        return "assist_route"
    if strategy in ("burden_relief_introduction", "follow_up_engagement"):
        return "assist_soft"
    if strategy in ("emotional_reassurance", "helpful_clarification", "practical_checklist"):
        return "empathize_only" if strategy == "emotional_reassurance" else "assist_soft"
    return base_stage

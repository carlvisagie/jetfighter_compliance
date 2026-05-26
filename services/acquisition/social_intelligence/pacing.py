"""Engagement pacing — no rush, respect cooldowns."""
from __future__ import annotations

from typing import Any, Dict, Optional


def decide_pacing(
    *,
    subreddit_profile: Dict[str, Any],
    last_approved_utc: str = "",
    cooldown_hours: float = 24.0,
    relationship_stage: int = 1,
    over_engagement: bool = False,
) -> Dict[str, Any]:
    if over_engagement:
        return {
            "deployment_timing": "wait_extended",
            "pacing_rationale": "Prior touches without rapport — slow down cadence.",
            "recommended_wait_hours": max(cooldown_hours * 2, 48),
        }
    if last_approved_utc:
        return {
            "deployment_timing": "respect_cooldown",
            "pacing_rationale": "Subreddit cooldown after last approval.",
            "recommended_wait_hours": cooldown_hours,
        }
    if relationship_stage <= 1:
        return {
            "deployment_timing": "patient_first_touch",
            "pacing_rationale": "First helpful presence — no rush.",
            "recommended_wait_hours": 0,
        }
    return {
        "deployment_timing": "ready_when_helpful",
        "pacing_rationale": "Trust supports timely helpful reply.",
        "recommended_wait_hours": 0,
    }

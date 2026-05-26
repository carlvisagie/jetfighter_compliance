"""Familiarity scoring from prior platform presence."""
from __future__ import annotations

from typing import Any, Dict


def compute_familiarity(
    prior_touches: Dict[str, int],
    subreddit_positive: int = 0,
) -> int:
    """0–100 familiarity — gradual, not instant trust."""
    score = 0
    score += min(40, prior_touches.get("approved", 0) * 15)
    score += min(25, prior_touches.get("total", 0) * 5)
    score += min(20, subreddit_positive * 4)
    score -= min(30, prior_touches.get("denied", 0) * 8)
    score -= min(40, prior_touches.get("removed", 0) * 15)
    return max(0, min(100, score))

"""Combined relationship score for engagement decisions."""
from __future__ import annotations

from typing import Any, Dict


def score_relationship(
    *,
    trust_score: int,
    familiarity_score: int,
    emotional_burden: int,
    safety_score: int,
) -> Dict[str, Any]:
    composite = (
        trust_score * 0.35
        + familiarity_score * 0.25
        + emotional_burden * 0.2
        + safety_score * 0.2
    )
    composite = int(max(0, min(100, composite)))
    band = "low"
    if composite >= 75:
        band = "high"
    elif composite >= 50:
        band = "medium"
    return {
        "relationship_score": composite,
        "relationship_band": band,
    }

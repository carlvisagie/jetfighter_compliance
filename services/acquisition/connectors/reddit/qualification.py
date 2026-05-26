"""Qualify Reddit opportunities for KYC fit — prioritizes advice-seekers."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ...acquisition_probability import DEFAULT_MIN_PREY_SCORE, score_acquisition_probability
from .author_intent import DEPLOYABLE_INTENTS
from .classifier import classify_post


def qualify_post(
    post: Dict[str, Any],
    classification: Dict[str, Any] | None = None,
    *,
    learning_state: Optional[Dict[str, Any]] = None,
    min_prey_score: int = DEFAULT_MIN_PREY_SCORE,
) -> Dict[str, Any]:
    """Fit and urgency for upload-first assistance (not legal/certainty claims)."""
    cls = classification or classify_post(post.get("title", ""), post.get("selftext", ""))
    sub = (post.get("subreddit") or "").lower()
    intent = cls.get("author_intent", "UNKNOWN")
    seeker = int(cls.get("advice_seeker_score", 0))
    giver = int(cls.get("advice_giver_score", 0))

    fit = 25
    if cls.get("relevant"):
        fit += 15
    if intent in DEPLOYABLE_INTENTS:
        fit += 25
    elif intent == "GIVING_ADVICE":
        fit -= 35
    elif intent == "PROMOTING_SERVICE":
        fit -= 45
    elif intent == "DISCUSSING_NEWS":
        fit -= 20

    fit += min(20, seeker // 5)
    fit -= min(30, giver // 4)

    if sub in (
        "smallbusiness",
        "cybersecurity",
        "cmmc",
        "nist800171",
        "govcontracts",
        "defensecontracting",
        "manufacturing",
    ):
        fit += 10
    if cls.get("burden_score", 0) >= 50:
        fit += 12
    if "?" in (post.get("title") or ""):
        fit += 5

    fit = max(0, min(100, fit))

    weights = (learning_state or {}).get("prey_learning") or {}
    prob = score_acquisition_probability(
        post.get("title", ""),
        post.get("selftext", ""),
        classification=cls,
        post=post,
        min_prey_score=min_prey_score,
        weight_adjustments=weights,
    )
    # Fit reflects topic; prey_score reflects acquisition probability — gate on prey
    if prob["prey_score"] >= 70:
        fit = min(100, fit + 8)
    elif prob["prey_score"] < DEFAULT_MIN_PREY_SCORE:
        fit = min(fit, 40)

    return {
        "fit_score": fit,
        "prey_score": prob["prey_score"],
        "predator_penalty": prob["predator_penalty"],
        "predator_class": prob["predator_class"],
        "queue_eligible": prob["queue_eligible"],
        "acquisition_probability": prob,
        "urgency_score": cls.get("urgency_score", 0),
        "burden_score": cls.get("burden_score", 0),
        "emotional_burden_score": cls.get("emotional_burden_score", 0),
        "signal_confidence": cls.get("signal_confidence", 40),
        "intent_confidence": cls.get("intent_confidence", 40),
        "overall_confidence": int((fit + cls.get("signal_confidence", 0) + cls.get("intent_confidence", 0)) / 3),
        "qualification_note": "Prioritizes advice-seekers over advice-givers. Public post only.",
        "likely_buyer": prob["queue_eligible"],
        "author_intent": intent,
        "recommended_action": cls.get("recommended_action", "ignore"),
        "prey_reasons": prob.get("prey_reasons", []),
    }

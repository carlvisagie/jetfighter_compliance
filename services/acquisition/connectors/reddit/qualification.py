"""Qualify Reddit opportunities for KYC fit — prioritizes advice-seekers."""
from __future__ import annotations

from typing import Any, Dict

from .author_intent import DEPLOYABLE_INTENTS
from .classifier import classify_post


def qualify_post(post: Dict[str, Any], classification: Dict[str, Any] | None = None) -> Dict[str, Any]:
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

    return {
        "fit_score": fit,
        "urgency_score": cls.get("urgency_score", 0),
        "burden_score": cls.get("burden_score", 0),
        "emotional_burden_score": cls.get("emotional_burden_score", 0),
        "signal_confidence": cls.get("signal_confidence", 40),
        "intent_confidence": cls.get("intent_confidence", 40),
        "overall_confidence": int((fit + cls.get("signal_confidence", 0) + cls.get("intent_confidence", 0)) / 3),
        "qualification_note": "Prioritizes advice-seekers over advice-givers. Public post only.",
        "likely_buyer": fit >= 55 and intent in DEPLOYABLE_INTENTS,
        "author_intent": intent,
        "recommended_action": cls.get("recommended_action", "ignore"),
    }

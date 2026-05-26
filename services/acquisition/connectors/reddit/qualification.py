"""Qualify Reddit opportunities for KYC fit — estimates with confidence."""
from __future__ import annotations

from typing import Any, Dict

from .classifier import classify_post


def qualify_post(post: Dict[str, Any], classification: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Fit and urgency for upload-first assistance (not legal/certainty claims)."""
    cls = classification or classify_post(post.get("title", ""), post.get("selftext", ""))
    sub = (post.get("subreddit") or "").lower()

    fit = 35
    if cls.get("relevant"):
        fit += 20
    if sub in (
        "smallbusiness",
        "cybersecurity",
        "cmmc",
        "nist800171",
        "govcontracts",
        "defensecontracting",
        "manufacturing",
    ):
        fit += 15
    if cls.get("burden_score", 0) >= 50:
        fit += 15
    fit = min(100, fit)

    return {
        "fit_score": fit,
        "urgency_score": cls.get("urgency_score", 0),
        "burden_score": cls.get("burden_score", 0),
        "emotional_burden_score": cls.get("emotional_burden_score", 0),
        "signal_confidence": cls.get("signal_confidence", 40),
        "overall_confidence": int((fit + cls.get("signal_confidence", 0)) / 2),
        "qualification_note": "Public post only — verify context before any reply. No auto-post.",
        "likely_buyer": fit >= 55,
    }

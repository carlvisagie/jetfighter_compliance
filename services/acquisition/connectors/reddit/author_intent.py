"""Classify Reddit author intent — advice-seekers vs advice-givers."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

INTENTS = (
    "SEEKING_HELP",
    "GIVING_ADVICE",
    "VENTING_OR_OVERWHELMED",
    "PROMOTING_SERVICE",
    "DISCUSSING_NEWS",
    "UNKNOWN",
)

DEPLOYABLE_INTENTS = frozenset({"SEEKING_HELP", "VENTING_OR_OVERWHELMED"})

INTENT_BADGES = {
    "SEEKING_HELP": "Needs help",
    "GIVING_ADVICE": "Giving advice",
    "VENTING_OR_OVERWHELMED": "Overwhelmed",
    "PROMOTING_SERVICE": "Selling service",
    "DISCUSSING_NEWS": "News only",
    "UNKNOWN": "Unknown intent",
}

INTENT_SORT_RANK = {
    "VENTING_OR_OVERWHELMED": 0,
    "SEEKING_HELP": 1,
    "UNKNOWN": 2,
    "DISCUSSING_NEWS": 3,
    "GIVING_ADVICE": 4,
    "PROMOTING_SERVICE": 5,
}

# High-value advice-seeker signals
SEEKING_PATTERNS: List[Tuple[str, int]] = [
    (r"\bwhere do i start\b", 12),
    (r"\bcan someone explain\b", 12),
    (r"\bi'?m new to this\b", 10),
    (r"\bi was tasked with\b", 12),
    (r"\bi don'?t know what to do\b", 14),
    (r"\bwhat do i need\b", 10),
    (r"\bhow do i prepare\b", 10),
    (r"\bwhat documents do i need\b", 12),
    (r"\bwhat paperwork\b", 10),
    (r"\bwhat evidence counts\b", 10),
    (r"\bhow do we prove\b", 10),
    (r"\bwe'?re overwhelmed\b", 14),
    (r"\bhelp\b", 6),
    (r"\bany advice\??\b", 12),
    (r"\bi'?m confused\b", 12),
    (r"\bmy boss asked\b", 12),
    (r"\bprime contractor asked\b", 12),
    (r"\bcustomer sent us a questionnaire\b", 14),
    (r"\bwe need cmmc\b", 10),
    (r"\bdo we need level [12]\b", 10),
    (r"\bhow do i\b", 6),
    (r"\bwhat should i\b", 8),
    (r"\bneed help\b", 10),
    (r"\blost\b", 5),
    (r"\btrying to understand\b", 12),
    (r"\bwhat applies to (us|our)\b", 12),
    (r"\bnot sure whether\b", 12),
    (r"\bdoes this mean\b", 10),
    (r"\bwe receive cui\b", 10),
    (r"\bwe don'?t know if\b", 12),
    (r"\?", 4),
]

GIVING_PATTERNS: List[Tuple[str, int]] = [
    (r"\byou should\b", 14),
    (r"\bthe answer is\b", 12),
    (r"\bhere'?s how (this|it|cmmc|dfars) works\b", 16),
    (r"\bhere is how\b", 12),
    (r"\bi advise clients\b", 18),
    (r"\bin my experience as a consultant\b", 18),
    (r"\bas a consultant\b", 14),
    (r"\bas a c3pao\b", 18),
    (r"\bas an assessor\b", 16),
    (r"\bas a cpa\b", 12),
    (r"\bi recommend (that|you|clients)\b", 10),
    (r"\bwhat you need to (know|do) is\b", 12),
    (r"\blet me explain\b", 10),
    (r"\bpro tip\b", 10),
    (r"\bfyi[, ]", 6),
]

PROMOTING_PATTERNS: List[Tuple[str, int]] = [
    (r"\bwe offer\b", 16),
    (r"\bbook a call\b", 18),
    (r"\bdm me\b", 16),
    (r"\bmy company helps\b", 18),
    (r"\bhere is my guide\b", 14),
    (r"\bi wrote an article\b", 14),
    (r"\bcheck out (our|my)\b", 12),
    (r"\bschedule a (call|demo)\b", 14),
    (r"\bwww\.", 8),
    (r"\b\.com\b", 4),
]

VENTING_PATTERNS: List[Tuple[str, int]] = [
    (r"\bi was tasked with\b.*\b(lost|overwhelm|confus)", 18),
    (r"\boverwhelm", 12),
    (r"\bpanic\b", 10),
    (r"\bstress(ed|ful)?\b", 8),
    (r"\bfrustrat", 10),
    (r"\bi'?m lost\b", 14),
    (r"\bso confused\b", 12),
    (r"\bdon'?t know where to start\b", 14),
    (r"\bthis is a nightmare\b", 10),
    (r"\bnightmare\b", 6),
    (r"\bburden\b", 8),
]

NEWS_PATTERNS: List[Tuple[str, int]] = [
    (r"\brule change\b", 12),
    (r"\bnew (deadline|requirement|rule)\b", 10),
    (r"\bannounced\b", 8),
    (r"\beffective date\b", 10),
    (r"\bupdated guidance\b", 10),
    (r"\bjust released\b", 8),
    (r"\bnews\b", 6),
    (r"\bdeadline extended\b", 10),
]


def _score_patterns(blob: str, patterns: List[Tuple[str, int]]) -> int:
    total = 0
    for pattern, weight in patterns:
        if re.search(pattern, blob, re.I):
            total += weight
    return total


def _recommended_action(intent: str, seeker: int, giver: int) -> str:
    if intent == "PROMOTING_SERVICE":
        return "competitor_or_expert"
    if intent == "GIVING_ADVICE":
        return "competitor_or_expert" if giver >= seeker + 10 else "monitor_only"
    if intent == "DISCUSSING_NEWS":
        return "news_context_only"
    if intent in DEPLOYABLE_INTENTS:
        return "approve_engagement"
    if intent == "UNKNOWN" and seeker > giver + 8:
        return "monitor_only"
    return "ignore"


def classify_author_intent(title: str, body: str = "") -> Dict[str, Any]:
    """Classify poster intent and advice-seeker vs giver scores."""
    text = f"{title}\n{body}".strip()
    blob = text.lower()

    seeker = _score_patterns(blob, SEEKING_PATTERNS)
    giver = _score_patterns(blob, GIVING_PATTERNS)
    promoting = _score_patterns(blob, PROMOTING_PATTERNS)
    venting = _score_patterns(blob, VENTING_PATTERNS)
    news = _score_patterns(blob, NEWS_PATTERNS)

    # Title question strongly suggests seeker
    if "?" in (title or "") and seeker < 8:
        seeker += 8

    scores = {
        "SEEKING_HELP": seeker,
        "GIVING_ADVICE": giver,
        "VENTING_OR_OVERWHELMED": venting,
        "PROMOTING_SERVICE": promoting,
        "DISCUSSING_NEWS": news,
    }

    # Disambiguation rules
    if promoting >= 14 and promoting >= max(seeker, giver):
        intent = "PROMOTING_SERVICE"
    elif giver >= 14 and giver > seeker + 4:
        intent = "GIVING_ADVICE"
    elif venting >= 12 and venting >= seeker:
        intent = "VENTING_OR_OVERWHELMED"
    elif news >= 12 and news > seeker and "?" not in blob:
        intent = "DISCUSSING_NEWS"
    elif seeker >= 8 and seeker >= giver:
        intent = "SEEKING_HELP"
    elif venting >= 8:
        intent = "VENTING_OR_OVERWHELMED"
    elif giver >= 10:
        intent = "GIVING_ADVICE"
    elif news >= 8:
        intent = "DISCUSSING_NEWS"
    else:
        intent = "UNKNOWN"

    advice_seeker_score = min(100, seeker * 4 + (15 if intent == "SEEKING_HELP" else 0) + (10 if intent == "VENTING_OR_OVERWHELMED" else 0))
    advice_giver_score = min(100, giver * 5 + promoting * 4 + (20 if intent == "GIVING_ADVICE" else 0) + (15 if intent == "PROMOTING_SERVICE" else 0))

    top = max(scores.items(), key=lambda x: x[1])
    confidence = min(95, 40 + top[1] * 3)
    if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED") and advice_seeker_score > advice_giver_score + 15:
        confidence = min(98, confidence + 10)

    recommended = _recommended_action(intent, advice_seeker_score, advice_giver_score)

    return {
        "author_intent": intent,
        "intent_confidence": confidence,
        "advice_seeker_score": advice_seeker_score,
        "advice_giver_score": advice_giver_score,
        "recommended_action": recommended,
        "intent_badges": [INTENT_BADGES.get(intent, "Unknown intent")],
        "intent_scores": scores,
        "deployable_engagement": intent in DEPLOYABLE_INTENTS and recommended == "approve_engagement",
    }


def sort_priority_for_opportunity(opp: Dict[str, Any]) -> Tuple[int, int, int]:
    """Sort: venting → seeking → fit → urgency (advice-givers last)."""
    intent = opp.get("author_intent") or (opp.get("author_intent_detail") or {}).get("author_intent", "UNKNOWN")
    rank = INTENT_SORT_RANK.get(intent, 9)
    return (
        rank,
        -int(opp.get("fit_score") or 0),
        -int(opp.get("urgency_score") or opp.get("burden_score") or 0),
    )

"""
Acquisition probability — helplessness + burden + operational need, not topic chat.

Scores likelihood a poster is a real overwhelmed prospect (prey) vs
consultant/educator/moderator/promoter (predator).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Default minimum prey_score to reach operator approval queue
DEFAULT_MIN_PREY_SCORE = 58

# --- High-value prey signals (helplessness + operational burden) ---
PREY_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\bwhere do i start\b", 14, "guidance_need"),
    (r"\bwhat documents do i need\b", 14, "paperwork_need"),
    (r"\bwhat paperwork\b", 12, "paperwork_need"),
    (r"\bwhat do i need\b", 10, "guidance_need"),
    (r"\bwe can'?t afford\b", 14, "budget_stress"),
    (r"\bcan'?t afford (this|it|cmmc|compliance)\b", 14, "budget_stress"),
    (r"\b(got|were) asked for cmmc\b", 16, "operational_trigger"),
    (r"\bwe got asked for cmmc\b", 16, "operational_trigger"),
    (r"\b(customer|prime|client) (sent|asked|required)\b.*(questionnaire|cmmc|dfars|800-171)", 16, "operational_trigger"),
    (r"\bprime contractor (sent|asked|required)\b", 14, "operational_trigger"),
    (r"\bi was tasked with\b", 14, "operational_trigger"),
    (r"\bmy boss asked\b", 12, "operational_trigger"),
    (r"\bsmall (business|company|shop|contractor)\b", 10, "small_contractor"),
    (r"\bsubcontractor\b", 10, "small_contractor"),
    (r"\bwe'?re overwhelmed\b", 14, "overwhelm"),
    (r"\bi'?m (lost|confused)\b", 12, "overwhelm"),
    (r"\bdon'?t know what to do\b", 14, "guidance_need"),
    (r"\bfirst time (doing|with)\b", 10, "guidance_need"),
    (r"\bnever done this before\b", 12, "guidance_need"),
    (r"\bany advice\??\b", 10, "guidance_need"),
    (r"\bcan someone explain\b", 10, "guidance_need"),
    (r"\bhow do (we|i) (prepare|get started)\b", 10, "guidance_need"),
    (r"\bsecurity questionnaire\b", 8, "paperwork_need"),
    (r"\bdo we need (level|cmmc)\b", 10, "guidance_need"),
]

# --- Predator / non-buyer signals ---
PREDATOR_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\b(ama|ask me anything)\b", 28, "ama"),
    (r"\bi am a (moderator|mod)\b", 26, "moderator"),
    (r"\b(mod team|moderator announcement)\b", 24, "moderator"),
    (r"\bas a consultant\b", 22, "consultant"),
    (r"\bas a c3pao\b", 24, "consultant"),
    (r"\bas an assessor\b", 22, "consultant"),
    (r"\bi advise clients\b", 22, "consultant"),
    (r"\bmy (clients|customers) (ask|need)\b", 14, "consultant"),
    (r"\bin my experience (as|helping)\b", 16, "authority"),
    (r"\bi teach\b", 20, "educator"),
    (r"\b(webinar|course|certification class|training program)\b", 18, "educator"),
    (r"\bi wrote (an |this )?(article|guide|ebook|whitepaper)\b", 18, "educator"),
    (r"\bhere is (my |our )?guide\b", 16, "educator"),
    (r"\bhere'?s how (this|it|cmmc|dfars) works\b", 18, "educator"),
    (r"\blet me explain\b", 12, "educator"),
    (r"\bthe answer is\b", 14, "authority"),
    (r"\byou should\b", 12, "authority"),
    (r"\bpro tip\b", 14, "authority"),
    (r"\b(influencer|podcast|newsletter|subscribe)\b", 16, "influencer"),
    (r"\bwe offer\b", 22, "promoter"),
    (r"\bbook a call\b", 22, "promoter"),
    (r"\bdm me\b", 18, "promoter"),
    (r"\bmy company helps\b", 22, "promoter"),
    (r"\b(rule change|new rule|deadline announced|effective date)\b", 12, "news_explainer"),
    (r"\bjust announced\b", 10, "news_explainer"),
    (r"\bcommunity (builder|manager|guidelines)\b", 14, "community_builder"),
    (r"\b(upvote|karma|crosspost)\b", 10, "community_builder"),
]

# Generic topic discussion without personal operational need
GENERIC_DISCUSSION_PATTERNS: List[Tuple[str, int]] = [
    (r"\bthoughts on\b", 10),
    (r"\bwhat do you think about\b", 10),
    (r"\bdiscussion:\b", 12),
    (r"\bdebate\b", 8),
    (r"\bhot take\b", 10),
    (r"\banyone else (notice|seen)\b", 8),
]


def _score_patterns(blob: str, patterns: List[Tuple[str, int, str]]) -> Tuple[int, Dict[str, int], List[str]]:
    total = 0
    by_dim: Dict[str, int] = {}
    hits: List[str] = []
    for pattern, weight, dim in patterns:
        if re.search(pattern, blob, re.I):
            total += weight
            by_dim[dim] = by_dim.get(dim, 0) + weight
            hits.append(dim)
    return total, by_dim, hits


def _score_simple(blob: str, patterns: List[Tuple[str, int]]) -> int:
    return sum(w for pat, w in patterns if re.search(pat, blob, re.I))


def score_acquisition_probability(
    title: str,
    body: str = "",
    *,
    classification: Optional[Dict[str, Any]] = None,
    post: Optional[Dict[str, Any]] = None,
    min_prey_score: int = DEFAULT_MIN_PREY_SCORE,
) -> Dict[str, Any]:
    """
    Score acquisition probability and prey_score.

    prey_score prioritizes helpless operational prospects over topical discussants.
    """
    text = f"{title}\n{body}".strip()
    blob = text.lower()
    cls = classification or {}

    prey_raw, prey_dims, prey_hits = _score_patterns(blob, PREY_PATTERNS)
    predator_raw, predator_dims, predator_hits = _score_patterns(blob, PREDATOR_PATTERNS)
    generic_penalty = _score_simple(blob, GENERIC_DISCUSSION_PATTERNS)

    intent = cls.get("author_intent", "UNKNOWN")
    seeker = int(cls.get("advice_seeker_score", 0))
    giver = int(cls.get("advice_giver_score", 0))
    burden = int(cls.get("burden_score", 0))
    emotional = int(cls.get("emotional_burden_score", 0))

    # Dimension likelihoods 0–100
    likelihood_real_buyer = min(100, 15 + prey_raw + (20 if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED") else 0))
    likelihood_existing_paperwork = min(
        100, 10 + prey_dims.get("paperwork_need", 0) * 3 + (10 if re.search(r"partial|messy|spreadsheet|policy", blob) else 0)
    )
    likelihood_operational_pain = min(
        100, prey_dims.get("operational_trigger", 0) * 4 + burden // 2 + prey_dims.get("overwhelm", 0) * 3
    )
    likelihood_budget_authority = min(100, prey_dims.get("budget_stress", 0) * 5 + (8 if re.search(r"\bboss|owner|ceo|president asked\b", blob) else 0))
    likelihood_emotional_overwhelm = min(100, prey_dims.get("overwhelm", 0) * 4 + emotional // 2 + burden // 3)
    likelihood_needing_guidance = min(
        100, prey_dims.get("guidance_need", 0) * 4 + seeker // 2 + (12 if "?" in (title or "") else 0)
    )
    likelihood_small_contractor_confusion = min(
        100, prey_dims.get("small_contractor", 0) * 5 + prey_dims.get("guidance_need", 0) * 2
    )

    # Predator penalty collapses prey
    predator_penalty = min(80, predator_raw + generic_penalty + giver // 2)
    if intent == "GIVING_ADVICE":
        predator_penalty = min(80, predator_penalty + 25)
    elif intent == "PROMOTING_SERVICE":
        predator_penalty = min(80, predator_penalty + 35)
    elif intent == "DISCUSSING_NEWS" and "?" not in blob:
        predator_penalty = min(80, predator_penalty + 20)

    # Topical relevance alone must not dominate
    has_personal_need = bool(
        re.search(
            r"\b(i|we|my|our)\b.*\b(was|were|got|need|can't|cannot|don't|tasked|lost|confused|afford)\b",
            blob,
        )
        or re.search(r"\b(where do i|what documents|what paperwork|any advice)\b", blob)
    )
    topical_only = (
        (cls.get("relevant") or burden >= 20)
        and prey_raw < 14
        and predator_penalty < 20
        and not has_personal_need
        and (generic_penalty >= 8 or "?" not in (title or ""))
    )
    if topical_only:
        predator_penalty = min(80, predator_penalty + 22)

    stacking_bonus = 0
    if len(set(prey_hits)) >= 3:
        stacking_bonus += 10
    elif len(set(prey_hits)) >= 2:
        stacking_bonus += 5
    if intent == "VENTING_OR_OVERWHELMED" and prey_raw >= 18:
        stacking_bonus += 6
    if intent == "SEEKING_HELP" and "?" in (title or ""):
        stacking_bonus += 4

    positive = (
        likelihood_real_buyer * 0.22
        + likelihood_operational_pain * 0.2
        + likelihood_emotional_overwhelm * 0.16
        + likelihood_needing_guidance * 0.16
        + likelihood_small_contractor_confusion * 0.12
        + likelihood_existing_paperwork * 0.07
        + likelihood_budget_authority * 0.07
    )

    prey_score = int(max(0, min(100, positive + stacking_bonus - predator_penalty * 0.85)))

    predator_class = _primary_predator_class(predator_dims, intent)
    queue_eligible = (
        prey_score >= min_prey_score
        and intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED")
        and predator_penalty < 45
        and predator_class not in ("consultant", "educator", "moderator", "promoter", "ama")
    )

    return {
        "prey_score": prey_score,
        "predator_penalty": predator_penalty,
        "predator_class": predator_class,
        "queue_eligible": queue_eligible,
        "min_prey_score": min_prey_score,
        "prey_signals": prey_hits,
        "predator_signals": predator_hits,
        "likelihood_real_buyer": likelihood_real_buyer,
        "likelihood_existing_paperwork": likelihood_existing_paperwork,
        "likelihood_operational_pain": likelihood_operational_pain,
        "likelihood_budget_authority": likelihood_budget_authority,
        "likelihood_emotional_overwhelm": likelihood_emotional_overwhelm,
        "likelihood_needing_guidance": likelihood_needing_guidance,
        "likelihood_small_contractor_confusion": likelihood_small_contractor_confusion,
        "topical_only_risk": topical_only,
    }


def _primary_predator_class(predator_dims: Dict[str, int], intent: str) -> str:
    if not predator_dims:
        if intent == "PROMOTING_SERVICE":
            return "promoter"
        if intent == "GIVING_ADVICE":
            return "consultant"
        if intent == "DISCUSSING_NEWS":
            return "news_explainer"
        return "none"
    return max(predator_dims.items(), key=lambda x: x[1])[0]


def sort_key_by_prey(opp: Dict[str, Any]) -> Tuple[int, int, int]:
    """Higher prey first, then intent rank, then fit."""
    from services.acquisition.connectors.reddit.author_intent import sort_priority_for_opportunity

    intent_rank = sort_priority_for_opportunity(opp)[0]
    prey = int(opp.get("prey_score") or (opp.get("acquisition_probability") or {}).get("prey_score", 0))
    return (intent_rank, -prey, -int(opp.get("fit_score") or 0))

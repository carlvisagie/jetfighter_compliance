"""
Acquisition probability — operational pain over topical relevance.

High precision + high sensitivity: real overwhelmed prospects, not topic chat or predators.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MIN_PREY_SCORE = 52
MIN_PREY_FLOOR = 48
MAX_PREY_CEILING = 62
TARGET_QUEUE_MIN = 1
TARGET_QUEUE_MAX = 10
NEAR_MISS_MARGIN = 6

# --- High-value prey signals (operational burden, not topic intensity) ---
PREY_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\bwhere do i start\b", 14, "guidance_need"),
    (r"\bwhat (documents|paperwork) do (we|i) need\b", 16, "paperwork_need"),
    (r"\bwhat paperwork\b", 12, "paperwork_need"),
    (r"\bwhat do (we|i) need\b", 12, "guidance_need"),
    (r"\bwhat level (do we|should we|to)\b", 16, "level_uncertainty"),
    (r"\bwhich cmmc level\b", 16, "level_uncertainty"),
    (r"\bwhat level do we need\b", 16, "level_uncertainty"),
    (r"\bwhat actually applies to (us|our)\b", 14, "compliance_uncertainty"),
    (r"\bwhat applies to us\b", 14, "compliance_uncertainty"),
    (r"\bwe can'?t afford\b", 16, "budget_stress"),
    (r"\bcannot afford\b", 14, "budget_stress"),
    (r"\bcan'?t afford (this|it|cmmc|compliance)\b", 16, "budget_stress"),
    (r"\btoo expensive\b", 14, "budget_stress"),
    (r"\bcosts?\s+(are\s+)?beyond what we can afford\b", 18, "budget_stress"),
    (r"\bwe cannot afford\b", 16, "budget_stress"),
    (r"\bwe got quoted\b", 12, "budget_stress"),
    (r"\b(got|were) (asked|told) (for|to|about)\b.*(cmmc|dfars|800-171|compliance)\b", 16, "operational_trigger"),
    (r"\bwe were told\b", 14, "operational_trigger"),
    (r"\b(customer|prime|client) (sent|asked|required)\b", 14, "operational_trigger"),
    (r"\bprime contractor\b", 12, "operational_trigger"),
    (r"\bquestionnaire\b", 12, "operational_trigger"),
    (r"\bi was tasked with\b", 14, "operational_trigger"),
    (r"\bmy boss asked\b", 12, "operational_trigger"),
    (r"\bsmall business\b", 14, "small_contractor"),
    (r"\bsmall (company|shop|contractor|supplier)\b", 12, "small_contractor"),
    (r"\bsubcontractor\b", 10, "small_contractor"),
    (r"\bvery basic\b", 12, "small_contractor"),
    (r"\bwe'?re overwhelmed\b", 14, "overwhelm"),
    (r"\bmore confused than ever\b", 18, "overwhelm"),
    (r"\bi'?m (lost|confused)\b", 12, "overwhelm"),
    (r"\bno idea (what|how|where)\b", 14, "overwhelm"),
    (r"\bdon'?t know what to do\b", 14, "guidance_need"),
    (r"\bfirst time (doing|with)\b", 10, "guidance_need"),
    (r"\bnever done this before\b", 12, "guidance_need"),
    (r"\bany advice\??\b", 10, "guidance_need"),
    (r"\bneed help\b", 12, "guidance_need"),
    (r"\bcan anyone (provide|give|share) (simple |some )?(insight|advice|guidance)\b", 16, "guidance_need"),
    (r"\bcan someone explain\b", 10, "guidance_need"),
    (r"\bhow do (we|i) (prepare|get started)\b", 10, "guidance_need"),
    (r"\bsecurity questionnaire\b", 10, "paperwork_need"),
    (r"\bwe house (information|data|pii)\b", 12, "operational_trigger"),
    (r"\b(messy|partial|spreadsheet|policies?)\b", 8, "paperwork_need"),
]

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

GENERIC_DISCUSSION_PATTERNS: List[Tuple[str, int]] = [
    (r"\bthoughts on\b", 12),
    (r"\bwhat do you think about\b", 12),
    (r"\bdiscussion:\b", 14),
    (r"\bdebate\b", 8),
    (r"\bhot take\b", 10),
    (r"\banyone else (notice|seen)\b", 8),
    (r"\bin general\b", 6),
    (r"\bacademically\b", 10),
]

CONFUSION_TERMS = (
    "confus",
    "lost",
    "overwhelm",
    "no idea",
    "don't know",
    "unclear",
    "not sure",
    "basic question",
    "help",
)


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


def _confusion_density(blob: str) -> int:
    hits = sum(1 for t in CONFUSION_TERMS if t in blob)
    words = max(1, len(blob.split()))
    density = min(100, hits * 18 + (hits * 40 // max(1, words // 30)))
    return density


def _has_operational_personal_need(blob: str, title: str) -> bool:
    return bool(
        re.search(
            r"\b(i|we|my|our)\b.*\b(was|were|got|told|need|can't|cannot|don't|tasked|lost|confused|afford|provide)\b",
            blob,
        )
        or re.search(
            r"\b(where do i|what (documents|level|paperwork)|any advice|small business|can't afford|more confused)\b",
            blob,
        )
        or re.search(r"\b(which|what) cmmc level\b", blob, re.I)
        or ("?" in (title or "") and re.search(r"\b(we|our|my|i)\b", blob))
    )


def _compute_dimension_scores(
    blob: str,
    prey_dims: Dict[str, int],
    cls: Dict[str, Any],
    burden: int,
    emotional: int,
    seeker: int,
    weight_adjustments: Dict[str, float],
) -> Dict[str, int]:
    def adj(key: str, val: int) -> int:
        mult = float(weight_adjustments.get(key, 1.0))
        return int(min(100, val * mult))

    financial = min(
        100,
        prey_dims.get("budget_stress", 0) * 5
        + (20 if re.search(r"afford|expensive|quoted|cost|cannot afford", blob) else 0),
    )
    operational = min(
        100,
        prey_dims.get("operational_trigger", 0) * 4
        + prey_dims.get("level_uncertainty", 0) * 4
        + burden // 2,
    )
    confusion = _confusion_density(blob)
    small_biz = min(
        100,
        prey_dims.get("small_contractor", 0) * 5
        + (12 if re.search(r"\bvery basic\b", blob) else 0),
    )
    compliance_unc = min(
        100,
        prey_dims.get("level_uncertainty", 0) * 5
        + prey_dims.get("compliance_uncertainty", 0) * 5
        + prey_dims.get("guidance_need", 0) * 2,
    )
    paperwork = min(
        100,
        prey_dims.get("paperwork_need", 0) * 5
        + (12 if re.search(r"questionnaire|ssp|policy|evidence|document", blob) else 0),
    )

    return {
        "financial_stress_score": adj("financial_stress", financial),
        "operational_pressure_score": adj("operational_pressure", operational),
        "confusion_density_score": adj("confusion_density", confusion),
        "small_business_stress_score": adj("small_business_stress", small_biz),
        "compliance_uncertainty_score": adj("compliance_uncertainty", compliance_unc),
        "paperwork_likelihood_score": adj("paperwork_likelihood", paperwork),
        "emotional_overwhelm_score": adj("emotional_overwhelm", min(100, prey_dims.get("overwhelm", 0) * 4 + emotional // 2)),
    }


def _build_prey_reasons(dims: Dict[str, int], prey_hits: List[str]) -> List[str]:
    reasons: List[str] = []
    if dims.get("financial_stress_score", 0) >= 40:
        reasons.append("Financial stress")
    if dims.get("small_business_stress_score", 0) >= 35:
        reasons.append("Small business confusion")
    if dims.get("operational_pressure_score", 0) >= 40:
        reasons.append("Operational pressure")
    if dims.get("paperwork_likelihood_score", 0) >= 35:
        reasons.append("Likely paperwork")
    if dims.get("compliance_uncertainty_score", 0) >= 40:
        reasons.append("Compliance uncertainty")
    if dims.get("confusion_density_score", 0) >= 35:
        reasons.append("High confusion")
    if dims.get("emotional_overwhelm_score", 0) >= 40:
        reasons.append("Emotional overwhelm")
    if "level_uncertainty" in prey_hits:
        reasons.append("Level uncertainty (what applies?)")
    if "operational_trigger" in prey_hits and "Operational pressure" not in reasons:
        reasons.append("Contract/questionnaire pressure")
    return reasons[:6]


def score_acquisition_probability(
    title: str,
    body: str = "",
    *,
    classification: Optional[Dict[str, Any]] = None,
    post: Optional[Dict[str, Any]] = None,
    min_prey_score: int = DEFAULT_MIN_PREY_SCORE,
    weight_adjustments: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    text = f"{title}\n{body}".strip()
    blob = text.lower()
    cls = classification or {}
    weights = weight_adjustments or {}

    prey_raw, prey_dims, prey_hits = _score_patterns(blob, PREY_PATTERNS)
    predator_raw, predator_dims, predator_hits = _score_patterns(blob, PREDATOR_PATTERNS)
    generic_penalty = _score_simple(blob, GENERIC_DISCUSSION_PATTERNS)

    intent = cls.get("author_intent", "UNKNOWN")
    seeker = int(cls.get("advice_seeker_score", 0))
    giver = int(cls.get("advice_giver_score", 0))
    burden = int(cls.get("burden_score", 0))
    emotional = int(cls.get("emotional_burden_score", 0))

    dimension_scores = _compute_dimension_scores(
        blob, prey_dims, cls, burden, emotional, seeker, weights
    )

    has_personal_need = _has_operational_personal_need(blob, title)
    topical_only = (
        (cls.get("relevant") or burden >= 15)
        and prey_raw < 16
        and predator_raw < 12
        and not has_personal_need
        and generic_penalty >= 10
    )

    predator_penalty = min(75, predator_raw + generic_penalty + giver // 3)
    if intent == "GIVING_ADVICE":
        predator_penalty = min(75, predator_penalty + 22)
    elif intent == "PROMOTING_SERVICE":
        predator_penalty = min(75, predator_penalty + 32)
    elif intent == "DISCUSSING_NEWS" and "?" not in blob:
        predator_penalty = min(75, predator_penalty + 18)
    if topical_only:
        predator_penalty = min(75, predator_penalty + 24)

    # Strong operational signals reduce over-penalization
    op_strength = dimension_scores["operational_pressure_score"] + dimension_scores["small_business_stress_score"]
    penalty_mult = 0.72 if op_strength >= 70 and predator_raw < 15 else 0.82

    stacking_bonus = 0
    unique_hits = set(prey_hits)
    if len(unique_hits) >= 4:
        stacking_bonus += 14
    elif len(unique_hits) >= 3:
        stacking_bonus += 10
    elif len(unique_hits) >= 2:
        stacking_bonus += 6
    if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED"):
        stacking_bonus += 8
    if has_personal_need and "?" in (title or ""):
        stacking_bonus += 5
    if dimension_scores["financial_stress_score"] >= 45 and dimension_scores["small_business_stress_score"] >= 30:
        stacking_bonus += 8

    positive = (
        dimension_scores["operational_pressure_score"] * 0.24
        + dimension_scores["emotional_overwhelm_score"] * 0.14
        + dimension_scores["confusion_density_score"] * 0.12
        + dimension_scores["small_business_stress_score"] * 0.14
        + dimension_scores["compliance_uncertainty_score"] * 0.12
        + dimension_scores["financial_stress_score"] * 0.12
        + dimension_scores["paperwork_likelihood_score"] * 0.12
    )
    positive += min(12, seeker // 8)

    prey_score = int(max(0, min(100, positive + stacking_bonus - predator_penalty * penalty_mult)))

    predator_class = _primary_predator_class(predator_dims, intent)
    prey_reasons = _build_prey_reasons(dimension_scores, prey_hits)

    queue_eligible = (
        prey_score >= min_prey_score
        and intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED")
        and predator_penalty < 48
        and predator_class not in ("consultant", "educator", "moderator", "promoter", "ama")
        and not topical_only
        and (has_personal_need or prey_raw >= 20)
    )

    return {
        "prey_score": prey_score,
        "predator_penalty": predator_penalty,
        "predator_class": predator_class,
        "queue_eligible": queue_eligible,
        "min_prey_score": min_prey_score,
        "prey_signals": prey_hits,
        "predator_signals": predator_hits,
        "prey_reasons": prey_reasons,
        "topical_only_risk": topical_only,
        "has_operational_need": has_personal_need,
        **dimension_scores,
        "likelihood_real_buyer": min(100, 20 + prey_raw + (15 if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED") else 0)),
        "likelihood_existing_paperwork": dimension_scores["paperwork_likelihood_score"],
        "likelihood_operational_pain": dimension_scores["operational_pressure_score"],
        "likelihood_budget_authority": dimension_scores["financial_stress_score"],
        "likelihood_emotional_overwhelm": dimension_scores["emotional_overwhelm_score"],
        "likelihood_needing_guidance": dimension_scores["compliance_uncertainty_score"],
        "likelihood_small_contractor_confusion": dimension_scores["small_business_stress_score"],
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


def compute_adaptive_prey_threshold(
    base_threshold: int,
    scored_candidates: List[Dict[str, Any]],
    *,
    learning_state: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Avoid starvation: relax slightly when strong near-miss prospects exist but none queued.
    Tighten when many low-quality pass.
    """
    state = learning_state or {}
    threshold = int(state.get("min_prey_threshold", base_threshold))
    threshold = max(MIN_PREY_FLOOR, min(MAX_PREY_CEILING, threshold))

    eligible = [c for c in scored_candidates if c.get("deployable_intent")]
    if not eligible:
        return threshold

    would_queue = [c for c in eligible if c.get("prey_score", 0) >= threshold and c.get("low_predator")]
    near_miss = [
        c
        for c in eligible
        if threshold - NEAR_MISS_MARGIN <= c.get("prey_score", 0) < threshold
        and c.get("low_predator")
        and c.get("has_operational_need")
    ]

    if len(would_queue) >= TARGET_QUEUE_MIN:
        return threshold

    if near_miss:
        relaxed = max(MIN_PREY_FLOOR, threshold - 4)
        return relaxed

    # Starvation: strongest operational burden prospect
    if eligible:
        best = max(eligible, key=lambda c: c.get("prey_score", 0))
        if best.get("prey_score", 0) >= MIN_PREY_FLOOR and best.get("low_predator") and best.get("has_operational_need"):
            return max(MIN_PREY_FLOOR, min(threshold, best.get("prey_score", 0)))

    return threshold


def apply_operator_prey_feedback(
    learning_state: Dict[str, Any],
    *,
    approved: bool,
    prey_reasons: Optional[List[str]] = None,
    topical_only: bool = False,
) -> Dict[str, Any]:
    """Adjust dimension weights from operator approve/deny patterns."""
    pl = learning_state.setdefault(
        "prey_learning",
        {
            "financial_stress": 1.0,
            "operational_pressure": 1.0,
            "confusion_density": 1.0,
            "small_business_stress": 1.0,
            "compliance_uncertainty": 1.0,
            "paperwork_likelihood": 1.0,
            "emotional_overwhelm": 1.0,
            "topical_weight": 1.0,
        },
    )
    reasons = prey_reasons or []
    if approved:
        if any("Financial" in r for r in reasons):
            pl["financial_stress"] = min(1.35, pl.get("financial_stress", 1.0) + 0.04)
        if any("Small business" in r for r in reasons):
            pl["small_business_stress"] = min(1.35, pl.get("small_business_stress", 1.0) + 0.04)
        if any("confusion" in r.lower() or "Confusion" in r for r in reasons):
            pl["confusion_density"] = min(1.3, pl.get("confusion_density", 1.0) + 0.03)
        if any("Operational" in r or "Contract" in r for r in reasons):
            pl["operational_pressure"] = min(1.35, pl.get("operational_pressure", 1.0) + 0.04)
        learning_state["min_prey_threshold"] = max(MIN_PREY_FLOOR, int(learning_state.get("min_prey_threshold", DEFAULT_MIN_PREY_SCORE)) - 1)
    else:
        if topical_only:
            pl["topical_weight"] = max(0.85, pl.get("topical_weight", 1.0) - 0.03)
            learning_state["min_prey_threshold"] = min(MAX_PREY_CEILING, int(learning_state.get("min_prey_threshold", DEFAULT_MIN_PREY_SCORE)) + 1)
    return learning_state


BANNED_PREDATOR_CLASSES = frozenset({"consultant", "educator", "moderator", "promoter", "ama"})


def passes_prey_gate(
    qualification: Dict[str, Any],
    classification: Dict[str, Any],
    *,
    min_prey_score: int,
) -> bool:
    """Gate operator queue on prey_score + predator profile."""
    prob = qualification.get("acquisition_probability") or {}
    intent = classification.get("author_intent", "UNKNOWN")
    return bool(
        int(qualification.get("prey_score", 0)) >= min_prey_score
        and intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED")
        and int(prob.get("predator_penalty", 99)) < 48
        and prob.get("predator_class") not in BANNED_PREDATOR_CLASSES
        and not prob.get("topical_only_risk")
        and prob.get("has_operational_need")
    )


def sort_key_by_prey(opp: Dict[str, Any]) -> Tuple[int, int, int]:
    from services.acquisition.connectors.reddit.author_intent import sort_priority_for_opportunity

    intent_rank = sort_priority_for_opportunity(opp)[0]
    prey = int(opp.get("prey_score") or (opp.get("acquisition_probability") or {}).get("prey_score", 0))
    return (intent_rank, -prey, -int(opp.get("fit_score") or 0))

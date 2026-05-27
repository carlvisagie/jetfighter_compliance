"""
Acquisition probability — operational pain over topical relevance.

High precision + high sensitivity: real overwhelmed prospects, not topic chat or predators.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MIN_PREY_SCORE = 50
MIN_PREY_FLOOR = 46
MAX_PREY_CEILING = 60
TARGET_QUEUE_MIN = 5
TARGET_QUEUE_MAX = 15
NEAR_MISS_MARGIN = 8
BANNED_PREDATOR_CLASSES = frozenset({"consultant", "educator", "moderator", "promoter", "ama"})

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
    (r"\bpartial documentation\b", 14, "paperwork_need"),
    (r"\bwhat paperwork is needed\b", 16, "paperwork_need"),
    (r"\b(customer|client) asked (for|us)\b", 14, "operational_trigger"),
    (r"\bdo we actually need\b", 14, "compliance_uncertainty"),
    (r"\bwhere do we start\b", 14, "guidance_need"),
    (r"\bimplementation (confusion|burden|pressure)\b", 12, "operational_trigger"),
    (r"\bquestionnaire burden\b", 12, "paperwork_need"),
    (r"\bvendor (pressure|requirements)\b", 10, "operational_trigger"),
    (r"\bquiet\b.*\b(confus|uncertain)\b", 10, "guidance_need"),
    (r"\bwhich level applies\b", 16, "level_uncertainty"),
    (r"\bwhat level applies\b", 16, "level_uncertainty"),
    (r"\bprime contractor asked\b", 16, "operational_trigger"),
    (r"\b(customer|client) asked (for|us)\b.*\b(mfa|questionnaire|documentation|security)\b", 16, "operational_trigger"),
    (r"\b(customer|client) asked for\b", 14, "operational_trigger"),
    (r"\bwe store (drawings|cui|data)\b", 14, "operational_trigger"),
    (r"\b(cui|controlled unclassified)\b.*\b(handl|stor|process)\b", 14, "operational_trigger"),
    (r"\bwhat documentation (is )?(needed|required)\b", 16, "paperwork_need"),
    (r"\bwhat (evidence|policies) (do we|are)\b", 14, "paperwork_need"),
    (r"\b(sprs|supplier performance risk system)\b", 14, "operational_trigger"),
    (r"\bvendor onboarding\b", 14, "operational_trigger"),
    (r"\b(mfa|multi.?factor).{0,40}\b(require|required|asked|need)\b", 14, "operational_trigger"),
    (r"\bsecurity questionnaire\b", 14, "paperwork_need"),
    (r"\b(flowdown|flow.?down)\b.*\b(security|requirements)\b", 12, "operational_trigger"),
    (r"\b(audit|assessment)\b.*\b(prepar|evidence|document)\b", 12, "paperwork_need"),
    (r"\b(spreadsheet|screenshot|policy draft)\b", 10, "paperwork_need"),
    (r"\bimplementation (uncertain|gap|unclear)\b", 12, "operational_trigger"),
    (r"\bdo we (actually )?need level\b", 14, "level_uncertainty"),
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
    "no idea",
    "don't know",
    "unclear",
    "not sure",
    "basic question",
    "trying to understand",
    "what applies",
    "which level",
    "do we need",
    "documentation",
    "questionnaire",
)

OPERATIONAL_ENTANGLEMENT_TERMS = (
    "prime contractor",
    "subcontractor",
    "vendor onboarding",
    "questionnaire",
    "sprs",
    "mfa",
    "cui",
    "drawings",
    "customer asked",
    "documentation",
    "evidence",
    "policy",
    "audit",
    "flowdown",
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
    op_hits = sum(1 for t in OPERATIONAL_ENTANGLEMENT_TERMS if t in blob)
    words = max(1, len(blob.split()))
    density = min(100, hits * 14 + op_hits * 10 + (hits * 35 // max(1, words // 30)))
    return density


def _operational_entanglement(blob: str, prey_dims: Dict[str, int]) -> int:
    op_hits = sum(1 for t in OPERATIONAL_ENTANGLEMENT_TERMS if t in blob)
    base = prey_dims.get("operational_trigger", 0) * 4 + prey_dims.get("paperwork_need", 0) * 3
    return min(100, base + op_hits * 12)


def _has_operational_personal_need(blob: str, title: str, soft: Optional[Dict[str, Any]] = None) -> bool:
    soft = soft or {}
    if soft.get("has_quiet_operational_need"):
        return True
    if any(t in blob for t in OPERATIONAL_ENTANGLEMENT_TERMS):
        return bool(re.search(r"\b(we|our|my|i|us)\b", blob) or "?" in (title or ""))
    return bool(
        re.search(
            r"\b(i|we|my|our)\b.*\b(was|were|got|told|need|tasked|store|house|receive|quoted|asked)\b",
            blob,
        )
        or re.search(
            r"\b(where do i|what (documents|level|paperwork|documentation|evidence)|any advice|small business|trying to understand|what applies|which level|do we actually need|sprs|vendor onboarding|security questionnaire)\b",
            blob,
        )
        or re.search(r"\b(which|what) (cmmc )?level\b", blob, re.I)
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
        prey_dims.get("operational_trigger", 0) * 5
        + prey_dims.get("level_uncertainty", 0) * 4
        + _operational_entanglement(blob, prey_dims) // 3
        + burden // 3,
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
        prey_dims.get("paperwork_need", 0) * 6
        + (14 if re.search(r"questionnaire|ssp|policy|evidence|document|sprs|audit", blob) else 0),
    )

    return {
        "financial_stress_score": adj("financial_stress", financial),
        "operational_pressure_score": adj("operational_pressure", operational),
        "confusion_density_score": adj("confusion_density", confusion),
        "small_business_stress_score": adj("small_business_stress", small_biz),
        "compliance_uncertainty_score": adj("compliance_uncertainty", compliance_unc),
        "paperwork_likelihood_score": adj("paperwork_likelihood", paperwork),
        "emotional_overwhelm_score": adj("emotional_overwhelm", min(100, prey_dims.get("overwhelm", 0) * 3 + emotional // 4)),
        "operational_entanglement_score": adj("operational_pressure", _operational_entanglement(blob, prey_dims)),
    }


def _build_prey_reasons(
    dims: Dict[str, int],
    prey_hits: List[str],
    soft_badges: Optional[List[str]] = None,
) -> List[str]:
    reasons: List[str] = list(soft_badges or [])
    if dims.get("financial_stress_score", 0) >= 40:
        reasons.append("Financial stress")
    if dims.get("small_business_stress_score", 0) >= 35:
        reasons.append("Small business confusion")
    if dims.get("operational_pressure_score", 0) >= 40:
        reasons.append("Operational pressure")
    if dims.get("operational_entanglement_score", 0) >= 40:
        reasons.append("Operational entanglement")
    if dims.get("paperwork_likelihood_score", 0) >= 35:
        reasons.append("Likely paperwork")
    if dims.get("compliance_uncertainty_score", 0) >= 40:
        reasons.append("Compliance uncertainty")
    if dims.get("confusion_density_score", 0) >= 35:
        reasons.append("Implementation uncertainty")
    if dims.get("emotional_overwhelm_score", 0) >= 55:
        reasons.append("Emotional overwhelm")
    if "level_uncertainty" in prey_hits:
        reasons.append("Level uncertainty (what applies?)")
    if "operational_trigger" in prey_hits and "Operational pressure" not in reasons:
        reasons.append("Contract/questionnaire pressure")
    seen = set()
    unique: List[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique[:8]


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

    from .intelligence.soft_burden import score_soft_burden

    soft = score_soft_burden(title, body)
    soft_mult = float(weights.get("soft_burden", 1.0))
    soft_score = int(min(100, soft["soft_burden_score"] * soft_mult))
    dimension_scores["soft_burden_score"] = soft_score

    topical_relevance = min(100, (15 if cls.get("relevant") else 0) + burden // 3 + len(cls.get("pain_themes") or []) * 4)

    has_personal_need = _has_operational_personal_need(blob, title, soft)
    topical_only = (
        (cls.get("relevant") or burden >= 15)
        and prey_raw < 16
        and predator_raw < 12
        and not has_personal_need
        and generic_penalty >= 10
    )

    predator_penalty = min(75, predator_raw + generic_penalty + giver // 4)
    if intent == "GIVING_ADVICE":
        predator_penalty = min(75, predator_penalty + 22)
    elif intent == "PROMOTING_SERVICE":
        predator_penalty = min(75, predator_penalty + 32)
    elif intent == "DISCUSSING_NEWS" and "?" not in blob:
        predator_penalty = min(75, predator_penalty + 18)
    if topical_only:
        predator_penalty = min(75, predator_penalty + 24)

    # Practical implementation questions — lighter penalty (not consultants/AMAs)
    if soft.get("is_practical_clarification") and predator_class_hint_safe(predator_dims):
        predator_penalty = max(0, predator_penalty - 12)

    op_strength = (
        dimension_scores["operational_pressure_score"]
        + dimension_scores["small_business_stress_score"]
        + soft_score
    )
    penalty_mult = 0.68 if op_strength >= 75 and predator_raw < 12 else 0.78
    if soft_score >= 55 and predator_raw < 10:
        penalty_mult = 0.65

    stacking_bonus = 0
    unique_hits = set(prey_hits)
    if len(unique_hits) >= 4:
        stacking_bonus += 14
    elif len(unique_hits) >= 3:
        stacking_bonus += 10
    elif len(unique_hits) >= 2:
        stacking_bonus += 6
    if intent == "SEEKING_HELP":
        stacking_bonus += 8
    elif intent == "VENTING_OR_OVERWHELMED":
        stacking_bonus += 2
    if has_personal_need and "?" in (title or ""):
        stacking_bonus += 6
    if dimension_scores.get("operational_entanglement_score", 0) >= 45:
        stacking_bonus += 8
    if dimension_scores["financial_stress_score"] >= 45 and dimension_scores["small_business_stress_score"] >= 30:
        stacking_bonus += 6

    # prey = topical + operational dimensions + soft burden - predator penalty
    positive = (
        topical_relevance * 0.05
        + dimension_scores["financial_stress_score"] * 0.09
        + dimension_scores["operational_pressure_score"] * 0.22
        + dimension_scores["operational_entanglement_score"] * 0.08
        + dimension_scores["compliance_uncertainty_score"] * 0.12
        + dimension_scores["paperwork_likelihood_score"] * 0.13
        + soft_score * 0.26
        + dimension_scores["confusion_density_score"] * 0.07
        + dimension_scores["small_business_stress_score"] * 0.10
        + dimension_scores["emotional_overwhelm_score"] * 0.03
    )
    positive += min(12, seeker // 8)

    prey_score = int(max(0, min(100, positive + stacking_bonus - predator_penalty * penalty_mult)))

    predator_class = _primary_predator_class(predator_dims, intent)
    prey_reasons = _build_prey_reasons(dimension_scores, prey_hits, soft.get("soft_burden_badges"))

    from .founding_beta_mode import deployable_intent

    deployable = deployable_intent(
        intent,
        soft_score=soft_score,
        has_personal_need=has_personal_need,
        predator_raw=predator_raw,
    )
    queue_eligible = (
        prey_score >= min_prey_score
        and deployable
        and predator_penalty < 48
        and predator_class not in ("consultant", "educator", "moderator", "promoter", "ama")
        and not topical_only
        and (has_personal_need or prey_raw >= 14 or soft_score >= 40)
    )

    prey_tier = classify_prey_tier(
        prey_score,
        predator_class=predator_class,
        predator_penalty=predator_penalty,
        queue_eligible=queue_eligible,
        topical_only=topical_only,
        dimension_scores=dimension_scores,
        soft_score=soft_score,
        has_operational_need=has_personal_need,
    )

    return {
        "prey_score": prey_score,
        "prey_tier": prey_tier,
        "predator_penalty": predator_penalty,
        "predator_class": predator_class,
        "queue_eligible": queue_eligible,
        "min_prey_score": min_prey_score,
        "prey_signals": prey_hits,
        "predator_signals": predator_hits,
        "prey_reasons": prey_reasons,
        "topical_only_risk": topical_only,
        "has_operational_need": has_personal_need,
        "topical_relevance_score": topical_relevance,
        "soft_burden": soft,
        "soft_burden_badges": soft.get("soft_burden_badges", []),
        **dimension_scores,
        "likelihood_real_buyer": min(100, 20 + prey_raw + (15 if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED") else 0)),
        "likelihood_existing_paperwork": dimension_scores["paperwork_likelihood_score"],
        "likelihood_operational_pain": dimension_scores["operational_pressure_score"],
        "likelihood_budget_authority": dimension_scores["financial_stress_score"],
        "likelihood_emotional_overwhelm": dimension_scores["emotional_overwhelm_score"],
        "likelihood_needing_guidance": dimension_scores["compliance_uncertainty_score"],
        "likelihood_small_contractor_confusion": dimension_scores["small_business_stress_score"],
        "likelihood_operational_entanglement": dimension_scores["operational_entanglement_score"],
    }


def classify_prey_tier(
    prey_score: int,
    *,
    predator_class: str,
    predator_penalty: int,
    queue_eligible: bool,
    topical_only: bool,
    dimension_scores: Dict[str, int],
    soft_score: int,
    has_operational_need: bool,
) -> int:
    """
    Prey tiers for operator UI and queue prioritization.

    1 — immediate operational burden (high-confidence uploads)
    2 — quiet implementation confusion (likely uploads)
    3 — emerging compliance realization (future uploads)
    4 — topic-only discussion (skip)
    5 — consultants / promoters / AMAs (block)
    """
    if predator_class in BANNED_PREDATOR_CLASSES or predator_penalty >= 48:
        return 5
    op_strength = (
        dimension_scores.get("operational_pressure_score", 0)
        + dimension_scores.get("operational_entanglement_score", 0)
        + dimension_scores.get("paperwork_likelihood_score", 0)
        + soft_score
    )
    if topical_only and prey_score < DEFAULT_MIN_PREY_SCORE:
        return 4
    if queue_eligible and prey_score >= 55 and op_strength >= 75:
        return 1
    if queue_eligible or (prey_score >= MIN_PREY_FLOOR and has_operational_need and op_strength >= 50):
        if soft_score >= 40 or dimension_scores.get("operational_entanglement_score", 0) >= 35:
            return 2
        return 2 if prey_score >= MIN_PREY_FLOOR else 3
    if prey_score >= MIN_PREY_FLOOR - 4 or (has_operational_need and soft_score >= 32):
        return 3
    if topical_only or prey_score < MIN_PREY_FLOOR - 4:
        return 4
    return 4


def predator_class_hint_safe(predator_dims: Dict[str, int]) -> bool:
    """No hard predator hits — safe to reduce penalty for practical questions."""
    banned = {"consultant", "educator", "moderator", "promoter", "ama", "authority", "influencer"}
    return not predator_dims or not any(k in banned for k in predator_dims)


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

    # Starvation / thin cycle: admit best operational prospect (target 5–15 per cycle)
    if eligible and not would_queue:
        best = max(
            eligible,
            key=lambda c: (
                c.get("prey_score", 0),
                c.get("operational_strength", 0),
                c.get("soft_burden_score", 0),
            ),
        )
        ps = int(best.get("prey_score", 0))
        if ps >= MIN_PREY_FLOOR and best.get("low_predator") and best.get("has_operational_need"):
            return max(MIN_PREY_FLOOR, min(threshold, ps))

    if near_miss:
        relaxed = max(MIN_PREY_FLOOR, threshold - 4)
        return relaxed

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
            "soft_burden": 1.0,
            "topical_weight": 1.0,
        },
    )
    reasons = prey_reasons or []
    if approved:
        if any("Quiet" in r or "Operational uncertainty" in r for r in reasons):
            pl["soft_burden"] = min(1.35, pl.get("soft_burden", 1.0) + 0.04)
    if approved:
        if any("Financial" in r for r in reasons):
            pl["financial_stress"] = min(1.35, pl.get("financial_stress", 1.0) + 0.04)
        if any("Small business" in r for r in reasons):
            pl["small_business_stress"] = min(1.35, pl.get("small_business_stress", 1.0) + 0.04)
        if any("confusion" in r.lower() or "Confusion" in r for r in reasons):
            pl["confusion_density"] = min(1.3, pl.get("confusion_density", 1.0) + 0.03)
        if any("Operational" in r or "Contract" in r or "entanglement" in r for r in reasons):
            pl["operational_pressure"] = min(1.35, pl.get("operational_pressure", 1.0) + 0.04)
            pl["paperwork_likelihood"] = min(1.35, pl.get("paperwork_likelihood", 1.0) + 0.03)
        if any("Emotional" in r for r in reasons) and not any("Operational" in r for r in reasons):
            pl["emotional_overwhelm"] = max(0.85, pl.get("emotional_overwhelm", 1.0) - 0.02)
        learning_state["min_prey_threshold"] = max(MIN_PREY_FLOOR, int(learning_state.get("min_prey_threshold", DEFAULT_MIN_PREY_SCORE)) - 1)
    else:
        if topical_only:
            pl["topical_weight"] = max(0.85, pl.get("topical_weight", 1.0) - 0.03)
            learning_state["min_prey_threshold"] = min(MAX_PREY_CEILING, int(learning_state.get("min_prey_threshold", DEFAULT_MIN_PREY_SCORE)) + 1)
    return learning_state


def passes_prey_gate(
    qualification: Dict[str, Any],
    classification: Dict[str, Any],
    *,
    min_prey_score: int,
) -> bool:
    """Gate operator queue on prey_score + predator profile."""
    from .founding_beta_mode import intent_passes_prey_gate

    prob = qualification.get("acquisition_probability") or {}
    intent = classification.get("author_intent", "UNKNOWN")
    soft = int(prob.get("soft_burden_score", 0))
    return bool(
        int(qualification.get("prey_score", 0)) >= min_prey_score
        and intent_passes_prey_gate(intent, soft_score=soft, prob=prob)
        and int(prob.get("predator_penalty", 99)) < 48
        and prob.get("predator_class") not in BANNED_PREDATOR_CLASSES
        and not prob.get("topical_only_risk")
        and (prob.get("has_operational_need") or soft >= 35)
        and int(prob.get("prey_tier", 4)) <= 3
    )


def sort_key_by_prey(opp: Dict[str, Any]) -> Tuple[int, int, int, int]:
    from services.acquisition.connectors.reddit.author_intent import sort_priority_for_opportunity

    intent_rank = sort_priority_for_opportunity(opp)[0]
    prob = opp.get("acquisition_probability") or {}
    tier = int(opp.get("prey_tier") or prob.get("prey_tier", 4))
    prey = int(opp.get("prey_score") or prob.get("prey_score", 0))
    return (intent_rank, tier, -prey, -int(opp.get("fit_score") or 0))

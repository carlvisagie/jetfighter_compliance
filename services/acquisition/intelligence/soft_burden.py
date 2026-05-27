"""
Soft burden intelligence — quiet operational confusion without panic language.

Detects real buyers who say "trying to understand" rather than "HELP ME."
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# (pattern, weight, category)
SOFT_UNCERTAINTY: List[Tuple[str, int, str]] = [
    (r"\bwhat applies to (us|our)\b", 14, "operational_uncertainty"),
    (r"\bnot sure whether\b", 14, "operational_uncertainty"),
    (r"\bdoes this mean\b", 12, "operational_uncertainty"),
    (r"\btrying to understand\b", 16, "operational_uncertainty"),
    (r"\bwhat level\b", 12, "operational_uncertainty"),
    (r"\bwhich level\b", 12, "operational_uncertainty"),
    (r"\bwhich cmmc level\b", 14, "operational_uncertainty"),
    (r"\bdo we need\b", 12, "operational_uncertainty"),
    (r"\bwhat counts\b", 12, "operational_uncertainty"),
    (r"\bwhat actually (counts|applies|means)\b", 14, "operational_uncertainty"),
    (r"\bhow do we know\b", 12, "operational_uncertainty"),
    (r"\bwe don'?t know if\b", 14, "operational_uncertainty"),
    (r"\bnot sure if\b", 12, "operational_uncertainty"),
    (r"\bcan anyone provide (simple |some )?insight\b", 14, "quiet_confusion"),
    (r"\bmore confused than ever\b", 16, "quiet_confusion"),
    (r"\bconflicting information\b", 14, "quiet_confusion"),
    (r"\bi'?ve been all over the web\b", 12, "quiet_confusion"),
    (r"\bwe currently\b", 8, "operational_context"),
    (r"\bdo we actually need\b", 14, "operational_uncertainty"),
    (r"\bwhere do we start\b", 12, "operational_uncertainty"),
    (r"\bwhat paperwork is needed\b", 14, "operational_uncertainty"),
    (r"\bpartial (documentation|paperwork|files)\b", 12, "operational_uncertainty"),
    (r"\bcustomer asked (for|us)\b", 12, "implementation"),
    (r"\bprime contractor requested\b", 12, "implementation"),
    (r"\bwe got quoted\b", 10, "financial"),
    (r"\bimplementation (confusion|burden)\b", 12, "quiet_confusion"),
    (r"\bquestionnaire burden\b", 10, "implementation"),
    (r"\bwhich level applies\b", 14, "operational_uncertainty"),
    (r"\bwhat documentation (is )?(needed|required)\b", 14, "operational_uncertainty"),
    (r"\b(customer|client) asked for (mfa|documentation|security)\b", 14, "implementation"),
    (r"\b(mfa|multi.?factor).{0,30}\b(require|required|asked)\b", 12, "implementation"),
    (r"\b(sprs|supplier performance risk)\b", 12, "implementation"),
    (r"\bvendor onboarding\b", 12, "implementation"),
    (r"\bwe store (drawings|cui)\b", 14, "implementation"),
    (r"\b(cui|controlled unclassified)\b", 10, "implementation"),
    (r"\bsecurity questionnaire\b", 12, "implementation"),
    (r"\b(evidence|policy|audit)\b.*\b(gap|uncertain|need|required)\b", 12, "operational_uncertainty"),
    (r"\b(flowdown|prime contractor asked)\b", 12, "implementation"),
]

SOFT_OPERATIONAL: List[Tuple[str, int, str]] = [
    (r"\bwe receive cui\b", 16, "implementation"),
    (r"\bwe (store|house|host) (information|data|cui)\b", 14, "implementation"),
    (r"\bwe support\b.*\b(contract|government|military|defense)\b", 12, "implementation"),
    (r"\bprime contractor\b", 12, "implementation"),
    (r"\bgovernment client\b", 12, "implementation"),
    (r"\bquestionnaire\b", 10, "implementation"),
    (r"\bautocad\b", 10, "implementation"),
    (r"\b(server|servers)\b", 8, "implementation"),
    (r"\bsubcontractor\b", 10, "implementation"),
    (r"\bcontract\b", 6, "implementation"),
    (r"\bsupplier\b", 6, "implementation"),
    (r"\bwe provide\b.*\b(military|defense|government|bases)\b", 12, "implementation"),
    (r"\boffice furniture\b", 8, "implementation"),
    (r"\bvendor (pressure|requirements)\b", 10, "implementation"),
    (r"\bcustomer (pressure|requirements)\b", 10, "implementation"),
    (r"\bvendor onboarding\b", 12, "implementation"),
    (r"\b(sprs|supplier performance risk)\b", 10, "implementation"),
    (r"\bwe store (drawings|cui)\b", 14, "implementation"),
    (r"\b(mfa|multi.?factor)\b", 8, "implementation"),
    (r"\b(evidence|policies?|audit)\b", 6, "implementation"),
    (r"\bsecurity questionnaire\b", 10, "implementation"),
]

SOFT_FINANCIAL: List[Tuple[str, int, str]] = [
    (r"\btoo expensive\b", 14, "financial"),
    (r"\bastronomical\b", 14, "financial"),
    (r"\bcannot afford\b", 14, "financial"),
    (r"\bcan'?t afford\b", 14, "financial"),
    (r"\bsmall business\b", 12, "financial"),
    (r"\bwe are small\b", 12, "financial"),
    (r"\bquoted\b", 10, "financial"),
    (r"\bcost seems insane\b", 14, "financial"),
    (r"\bcosts? beyond\b", 12, "financial"),
]

# Practical clarification — reduces mistaken predator reads (handled in acquisition_probability)
PRACTICAL_CLARIFICATION_MARKERS = (
    r"\btrying to understand\b",
    r"\bwhat applies to us\b",
    r"\bdo we need\b",
    r"\bwhat level\b",
    r"\bwhich level\b",
    r"\bwe receive cui\b",
    r"\bwe store cui\b",
    r"\bvendor onboarding\b",
    r"\bsprs\b",
    r"\bsecurity questionnaire\b",
)


def _match_patterns(blob: str, patterns: List[Tuple[str, int, str]]) -> Tuple[int, Dict[str, int], List[str]]:
    total = 0
    by_cat: Dict[str, int] = {}
    hits: List[str] = []
    for pat, weight, cat in patterns:
        if re.search(pat, blob, re.I):
            total += weight
            by_cat[cat] = by_cat.get(cat, 0) + weight
            if cat not in hits:
                hits.append(cat)
    return total, by_cat, hits


def score_soft_burden(title: str, body: str = "") -> Dict[str, Any]:
    """Return soft_burden_score 0–100 and badge-oriented signals."""
    blob = f"{title}\n{body}".strip().lower()

    u_total, u_by, u_hits = _match_patterns(blob, SOFT_UNCERTAINTY)
    o_total, o_by, o_hits = _match_patterns(blob, SOFT_OPERATIONAL)
    f_total, f_by, f_hits = _match_patterns(blob, SOFT_FINANCIAL)

    raw = u_total + o_total + f_total
    has_quiet = raw >= 12 or bool(
        re.search(r"\b(we|our|my|i)\b", blob) and ("?" in title or "?" in body)
    )
    is_practical_clarification = any(re.search(p, blob, re.I) for p in PRACTICAL_CLARIFICATION_MARKERS)

    operational_uncertainty = min(100, u_by.get("operational_uncertainty", 0) * 5 + (10 if "?" in (title or "") else 0))
    quiet_confusion = min(100, u_by.get("quiet_confusion", 0) * 5 + u_by.get("operational_uncertainty", 0) * 2)
    implementation = min(100, o_by.get("implementation", 0) * 4 + o_total)
    financial_soft = min(100, f_by.get("financial", 0) * 5 + f_total // 2)
    small_biz_pressure = min(100, f_by.get("financial", 0) * 3 + (15 if re.search(r"\b(small business|we are small|very basic)\b", blob) else 0))

    soft_burden_score = int(
        min(
            100,
            operational_uncertainty * 0.30
            + quiet_confusion * 0.16
            + implementation * 0.28
            + financial_soft * 0.16
            + small_biz_pressure * 0.10
            + min(20, raw // 2),
        )
    )

    badges: List[str] = []
    if implementation >= 30:
        badges.append("Operational entanglement")
    if operational_uncertainty >= 35:
        badges.append("Operational uncertainty")
    if quiet_confusion >= 30:
        badges.append("Quiet confusion")
    if financial_soft >= 35:
        badges.append("Financial stress")
    if implementation >= 35:
        badges.append("Real-world implementation")
    if small_biz_pressure >= 30:
        badges.append("Small business pressure")

    return {
        "soft_burden_score": soft_burden_score,
        "soft_burden_raw": raw,
        "has_quiet_operational_need": has_quiet and (u_total + o_total) >= 8,
        "is_practical_clarification": is_practical_clarification,
        "soft_burden_badges": badges[:5],
        "soft_categories": u_hits + o_hits + f_hits,
        "operational_uncertainty_component": operational_uncertainty,
        "quiet_confusion_component": quiet_confusion,
        "implementation_component": implementation,
        "financial_soft_component": financial_soft,
        "small_business_pressure_component": small_biz_pressure,
    }

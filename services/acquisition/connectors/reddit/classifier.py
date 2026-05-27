"""Classify Reddit posts for compliance burden and emotional signals."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from ...signals import detect_signals
from .author_intent import classify_author_intent

# Mission pain themes → search/classification hooks
PAIN_THEMES: List[tuple[str, str]] = [
    (r"\bcmmc\b", "cmmc_confusion"),
    (r"\bdfars\b", "dfars_confusion"),
    (r"\bnist\s*800[- ]?171\b", "nist_800_171"),
    (r"\bsprs\b", "cmmc_confusion"),
    (r"supplier onboarding", "supplier_onboarding_burden"),
    (r"vendor onboarding", "supplier_onboarding_burden"),
    (r"\bwe store (drawings|cui)\b", "documentation_stress"),
    (r"\b(cui|controlled unclassified)\b", "operational_security_burden"),
    (r"\bflowdown\b", "prime_contractor_requirements"),
    (r"\b(evidence|policies?)\b.*\b(gap|need|required)\b", "documentation_stress"),
    (r"security questionnaire", "security_questionnaire_overwhelm"),
    (r"customer security questionnaire", "customer_security_questionnaire"),
    (r"customer security requirements", "customer_security_questionnaire"),
    (r"vendor assessment", "vendor_assessment"),
    (r"vendor questionnaire", "vendor_assessment"),
    (r"prime contractor", "prime_contractor_requirements"),
    (r"cyber insurance", "security_questionnaire_overwhelm"),
    (r"\bmfa\b", "operational_security_burden"),
    (r"cybersecurity requirements", "operational_security_burden"),
    (r"security requirements", "operational_security_burden"),
    (r"security (paperwork|assessment)", "documentation_stress"),
    (r"compliance paperwork", "documentation_stress"),
    (r"documentation request", "documentation_stress"),
    (r"evidence request", "documentation_stress"),
    (r"need (cyber)?security polic", "documentation_stress"),
    (r"need policies", "documentation_stress"),
    (r"what documents do we need", "paperwork_uncertainty"),
    (r"we got asked for", "operational_trigger"),
    (r"government contract", "government_contract_burden"),
    (r"it compliance", "operational_security_burden"),
    (r"contract flowdown", "prime_contractor_requirements"),
    (r"where do i start", "where_to_start"),
    (r"what paperwork", "paperwork_uncertainty"),
    (r"small business compliance", "small_business_compliance"),
    (r"audit (anxiety|stress|fear|panic)", "audit_anxiety"),
    (r"\boverwhelm", "overwhelm"),
    (r"\bconfus", "confusion"),
    (r"documentation (gap|stress|mess)", "documentation_stress"),
]

EMOTION_MAP = {
    "overwhelm": "overwhelm",
    "confusion": "confusion",
    "where_to_start": "procrastination",
    "paperwork_uncertainty": "fear",
    "audit_anxiety": "fear",
    "cmmc_confusion": "confusion",
    "dfars_confusion": "confusion",
    "security_questionnaire_overwhelm": "overwhelm",
    "operational_security_burden": "confusion",
    "government_contract_burden": "fear",
    "operational_trigger": "procrastination",
}


def classify_post(title: str, body: str = "") -> Dict[str, Any]:
    """Return signal bundle with burden and emotional scores."""
    text = f"{title}\n{body}".strip()
    base = detect_signals(text)
    themes: List[str] = []
    blob = text.lower()
    for pattern, tag in PAIN_THEMES:
        if re.search(pattern, blob, re.I):
            if tag not in themes:
                themes.append(tag)

    emotional: List[str] = list(base.get("emotional_tags") or [])
    for t in themes:
        em = EMOTION_MAP.get(t)
        if em and em not in emotional:
            emotional.append(em)

    burden_score = min(
        100,
        base.get("signal_score", 0) * 8
        + len(themes) * 6
        + (8 if "overwhelm" in emotional else 0)
        + (5 if "fear" in emotional else 0),
    )
    urgency_score = min(100, burden_score // 2 + (20 if re.search(r"deadline|due|asap|urgent", blob) else 0))
    emotional_burden_score = min(100, burden_score + len(emotional) * 5)

    confidence = min(95, base.get("confidence", 30) + len(themes) * 5)

    level = base.get("signal_level", "low")
    if burden_score >= 75:
        level = "critical"
    elif burden_score >= 50:
        level = "high"
    elif burden_score >= 25:
        level = "medium"

    likely_gaps: List[str] = []
    if "documentation" in blob or "paperwork" in blob:
        likely_gaps.append("documentation_organization")
    if "questionnaire" in blob:
        likely_gaps.append("security_questionnaire_evidence")
    if "cmmc" in blob or "nist" in blob:
        likely_gaps.append("control_evidence_mapping")

    intent = classify_author_intent(title, body)
    if intent["author_intent"] in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED"):
        burden_score = min(100, burden_score + 10)
        emotional_burden_score = min(100, emotional_burden_score + 8)
    elif intent["author_intent"] in ("GIVING_ADVICE", "PROMOTING_SERVICE"):
        burden_score = max(0, burden_score - 25)
    elif intent["author_intent"] == "UNKNOWN" and any(
        t in themes
        for t in (
            "operational_trigger",
            "operational_security_burden",
            "prime_contractor_requirements",
            "paperwork_uncertainty",
            "documentation_stress",
        )
    ):
        burden_score = min(100, burden_score + 6)

    relevant = burden_score >= 20 or bool(themes)
    if intent["author_intent"] in ("GIVING_ADVICE", "PROMOTING_SERVICE") and intent["advice_giver_score"] > intent["advice_seeker_score"] + 10:
        relevant = False
    elif intent["deployable_engagement"]:
        relevant = True

    return {
        **base,
        **intent,
        "signal_level": level,
        "pain_themes": themes,
        "emotional_tags": emotional,
        "burden_score": burden_score,
        "urgency_score": urgency_score,
        "emotional_burden_score": emotional_burden_score,
        "signal_confidence": confidence,
        "likely_documentation_gaps": likely_gaps,
        "relevant": relevant,
    }

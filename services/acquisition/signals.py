"""Pain, urgency, and burden signals from public text (no private scraping)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

SIGNAL_LEVELS = ("low", "medium", "high", "critical")

PAIN_PATTERNS: List[Tuple[str, str, int]] = [
    (r"\boverwhelm", "overwhelm", 3),
    (r"\bconfus", "confusion", 2),
    (r"\bwhere do i start", "where_to_start", 3),
    (r"\bwhat paperwork", "paperwork_uncertainty", 3),
    (r"\bdocumentation gap", "documentation_gap", 3),
    (r"\bsecurity questionnaire", "security_questionnaire", 2),
    (r"\baudit (fear|stress|pressure)", "audit_pressure", 3),
    (r"\bdeadline", "deadline_pressure", 2),
    (r"\bcontract (risk|requirement)", "contract_risk", 2),
    (r"\bcmmc", "cmmc_uncertainty", 2),
    (r"\bdfars", "dfars_confusion", 2),
    (r"\bneed cmmc help", "cmmc_help_seeking", 3),
    (r"\bevidence", "evidence_stress", 1),
    (r"\bvendor (onboard|questionnaire)", "vendor_pressure", 2),
    (r"\bnot sure what to upload", "upload_uncertainty", 2),
    (r"\bprocrastinat", "procrastination", 2),
    (r"\bafraid|fear of doing", "compliance_fear", 2),
]

EMOTIONAL_TAGS = {
    "overwhelm": "emotional_overwhelm",
    "confusion": "emotional_confusion",
    "where_to_start": "readiness_uncertainty",
    "paperwork_uncertainty": "burden_uncertainty",
    "audit_pressure": "audit_fear",
    "deadline_pressure": "urgency_stress",
    "compliance_fear": "fear_of_wrong",
}


def detect_signals(text: str) -> Dict[str, Any]:
    """Classify acquisition opportunity from public discussion or notes."""
    blob = (text or "").lower()
    pain_tags: List[str] = []
    emotional: List[str] = []
    score = 0
    for pattern, tag, weight in PAIN_PATTERNS:
        if re.search(pattern, blob):
            if tag not in pain_tags:
                pain_tags.append(tag)
            score += weight
            emo = EMOTIONAL_TAGS.get(tag)
            if emo and emo not in emotional:
                emotional.append(emo)

    if score >= 8:
        level = "critical"
    elif score >= 5:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "low"

    confidence = min(95, 35 + score * 8) if pain_tags else 25

    return {
        "signal_level": level,
        "pain_tags": pain_tags,
        "emotional_tags": emotional,
        "signal_score": score,
        "confidence": confidence,
        "burden_detected": bool(pain_tags),
    }

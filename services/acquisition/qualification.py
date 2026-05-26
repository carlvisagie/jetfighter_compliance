"""Qualification estimates with explicit confidence — no fabricated certainty."""
from __future__ import annotations

import re
from typing import Any, Dict

from .models import Lead

SIZE_HINTS = [
    (r"\b(1[0-9]|[2-9][0-9]|[1-9][0-9]{2,})\s*employees", "medium_large"),
    (r"\b(startup|small business|smb)\b", "smb"),
    (r"\b(enterprise|fortune)\b", "enterprise"),
]

BUDGET_HINTS = [
    (r"\b(subcontract|prime|defense|govcon)\b", "likely_contract_exposure"),
    (r"\b(cmmc level [12]|sprs|dfars)\b", "compliance_investment_likely"),
]

MATURITY_LOW = ("where do i start", "overwhelm", "confus", "don't know")
MATURITY_MID = ("documentation", "policy", "audit", "questionnaire")


def _estimate(text: str, patterns: list, default: str, confidence: int) -> Dict[str, Any]:
    blob = text.lower()
    for pat, label in patterns:
        if re.search(pat, blob):
            return {"estimate": label, "confidence": min(90, confidence + 15)}
    return {"estimate": default, "confidence": confidence}


def qualify_lead(lead: Lead, signal_bundle: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Estimate fit dimensions; store confidence per field."""
    blob = " ".join(
        [
            lead.company_name,
            lead.website,
            lead.industry,
            lead.segment,
            lead.contact_title,
            lead.notes,
            " ".join(lead.pain_signals),
            " ".join(lead.compliance_signals),
        ]
    )
    sig = signal_bundle or {}
    base_conf = max(lead.confidence_score, sig.get("confidence", 30))

    size = _estimate(blob, SIZE_HINTS, "unknown_smb_manufacturing", base_conf)
    budget = _estimate(blob, BUDGET_HINTS, "moderate_if_defense_supply", base_conf - 10)
    if lead.ability_to_pay_score >= 60:
        budget = {"estimate": "likely_budget_capacity", "confidence": min(85, lead.ability_to_pay_score)}

    maturity = "early"
    mat_conf = 40
    if any(m in blob for m in MATURITY_MID):
        maturity = "developing"
        mat_conf = 55
    if lead.fit_score >= 70 and lead.compliance_signals:
        maturity = "active_compliance_burden"
        mat_conf = 65

    urgency = "low"
    urg_conf = 35
    if lead.urgency_score >= 70 or sig.get("signal_level") in ("high", "critical"):
        urgency = "high"
        urg_conf = min(90, lead.urgency_score or 70)
    elif lead.urgency_score >= 45 or sig.get("signal_level") == "medium":
        urgency = "medium"
        urg_conf = 55

    need = "compliance_burden_relief"
    if "cmmc" in blob or "dfars" in blob:
        need = "defense_compliance_paperwork"
    elif "dpp" in blob or "passport" in blob:
        need = "product_passport_paperwork"

    return {
        "company_size": size,
        "contract_exposure": budget,
        "likely_need": {"estimate": need, "confidence": min(80, base_conf)},
        "budget_capability": budget,
        "compliance_maturity": {"estimate": maturity, "confidence": mat_conf},
        "urgency": {"estimate": urgency, "confidence": urg_conf},
        "overall_confidence": int(
            (size["confidence"] + budget["confidence"] + mat_conf + urg_conf) / 4
        ),
        "qualification_note": "Estimates from public signals only — verify on upload.",
    }

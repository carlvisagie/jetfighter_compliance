"""USASpending / federal supplier paperwork likelihood — founding beta outreach angles."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .messaging import BETA_HEADLINE, beta_outreach_snippet


def predict_federal_supplier_paperwork(
    company_name: str,
    *,
    notes: str = "",
    segment: str = "",
    industry: str = "",
) -> Dict[str, Any]:
    """Enrich lawful public federal targets with paperwork-focused founding beta framing."""
    blob = f"{company_name} {notes} {segment} {industry}".lower()
    indicators: List[str] = []
    if re.search(r"defense|aerospace|machin|fabricat|supplier|subcontract", blob):
        indicators.append("DoD supplier flowdowns")
    if re.search(r"government|federal|contract", blob):
        indicators.append("Federal contract compliance")
    indicators.extend(
        [
            "Security questionnaires",
            "Contract flowdown requirements",
            "Onboarding evidence packets",
            "Cyber policy gaps",
            "Partial SSP/policies/spreadsheets",
        ]
    )
    likely = (
        "Likely has DoD supplier paperwork, security questionnaires, contract flowdowns, "
        "onboarding evidence, and cyber policy gaps — messy partial uploads are expected."
    )
    burden = (
        "Federal award recipient — operational entanglement with DFARS/CMMC-style burden "
        "even when public data does not show emotional distress."
    )
    angle = (
        "Offer a free Founding Beta paperwork review: upload what they already have "
        "(questionnaires, policies, screenshots, spreadsheets) — no perfect SSP required."
    )
    pitch = beta_outreach_snippet(include_route=False)
    why_upload = (
        "Small manufacturers and subcontractors often hold partial compliance artifacts "
        "before they know what applies — ideal for upload-first gap identification."
    )
    return {
        "likely_paperwork_prediction": likely,
        "likely_paperwork_indicators": indicators[:6],
        "likely_compliance_burden": burden,
        "likely_outreach_angle": angle,
        "likely_evidence_request": "Customer/prime questionnaires, flowdown clauses, cyber insurance forms",
        "recommended_founding_beta_pitch": pitch,
        "why_might_upload_paperwork": why_upload,
        "beta_headline": BETA_HEADLINE,
        "beta_fit": "moderate — federal supplier paperwork likely",
        "recommended_next_action": "Route to inquiry founding beta — do not cold-sell",
    }

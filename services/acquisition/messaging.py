"""Burden-removal messaging — no fearmongering, no certification guarantees."""
from __future__ import annotations

from typing import Any, Dict, List

from .models import Lead

CORE_HEADLINE = "Give us exactly what you have."
CORE_SUBLINE = "We'll handle the rest."

VARIANTS = {
    "A": {
        "headline": CORE_HEADLINE,
        "body": "Upload any paperwork you already have — messy, partial, or scattered. We organize it and show you what may still help.",
        "cta": "Upload my paperwork",
        "framing": "burden_removal",
    },
    "B": {
        "headline": "Start with what you have.",
        "body": "You do not need perfect documentation to begin. Send policies, spreadsheets, screenshots, or exports — we take it from there.",
        "cta": "Upload my paperwork",
        "framing": "imperfect_paperwork_ok",
    },
    "C": {
        "headline": "Overwhelmed by compliance paperwork?",
        "body": "Give us what you have today. We review, organize, and identify gaps — without asking you to become a compliance expert first.",
        "cta": "Upload what I have",
        "framing": "overwhelm_relief",
    },
}

FORBIDDEN_PHRASES = (
    "guaranteed certification",
    "legal advice",
    "you will pass audit",
    "act now or lose",
    "mandatory penalty",
)


def generate_message(
    lead: Lead | Dict[str, Any],
    variant: str = "A",
    *,
    experiment_id: str = "",
) -> Dict[str, Any]:
    """Generate upload-first outreach copy for operator review (not auto-sent)."""
    v = VARIANTS.get(variant.upper(), VARIANTS["A"])
    company = lead.company_name if isinstance(lead, Lead) else str(lead.get("company_name", "your organization"))
    pain = (
        lead.pain_signals
        if isinstance(lead, Lead)
        else (lead.get("pain_signals") or [])
    )
    pain_hint = ""
    if pain:
        pain_hint = f" We noticed signals like {', '.join(pain[:2])} — we help with that burden."

    body = v["body"] + pain_hint
    for bad in FORBIDDEN_PHRASES:
        if bad in body.lower():
            body = VARIANTS["A"]["body"]

    return {
        "variant": variant.upper(),
        "experiment_id": experiment_id,
        "headline": v["headline"],
        "body": body,
        "cta": v["cta"],
        "framing": v["framing"],
        "company_name": company,
        "doctrine": "upload_first_auto_send",
        "operator_note": "Autonomous outreach enabled — organism sends to qualified leads with valid contact info.",
    }


def list_variants() -> List[str]:
    return list(VARIANTS.keys())

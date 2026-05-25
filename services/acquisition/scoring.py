"""Rule-based lead scoring (0–100). No ML, no external APIs."""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import Lead, SEGMENTS

POSITIVE_KEYWORDS = [
    "aerospace",
    "manufacturing",
    "defense",
    "government contractor",
    "govcon",
    "subcontractor",
    "machining",
    "fabrication",
    "precision",
    "inspection",
    "supplier quality",
    "as9100",
    "iso 9001",
    "cmmc",
    "itar",
    "dfars",
    "nist",
    "audit",
    "documentation",
    "traceability",
    "quality manager",
    "compliance manager",
    "operations manager",
    "qa manager",
    "prime contractor",
    "nadcap",
]

NEGATIVE_KEYWORDS = [
    "fortune 500",
    "global enterprise",
    "retail consumer",
    "restaurant",
    "salon",
    "influencer",
    "crypto",
    "nft",
    "gambling",
    "adult",
    "mlm",
]

TITLE_POSITIVE = [
    "quality",
    "compliance",
    "operations",
    "qa ",
    "q.a.",
    "program manager",
    "document control",
]

ENTERPRISE_HINTS = [
    "boeing",
    "lockheed",
    "northrop",
    "raytheon",
    "general dynamics",
    "bae systems",
]


def _text_blob(lead: Lead) -> str:
    parts = [
        lead.company_name,
        lead.website,
        lead.contact_title,
        lead.industry,
        lead.segment,
        lead.notes,
        lead.location,
        " ".join(lead.pain_signals),
        " ".join(lead.compliance_signals),
    ]
    return " ".join(parts).lower()


def score_lead(lead: Lead) -> Tuple[int, int, List[str], List[str], str]:
    """
    Returns fit_score, confidence_score, pain_signals, compliance_signals, reason_summary.
    """
    blob = _text_blob(lead)
    pain: List[str] = []
    compliance: List[str] = []
    fit = 40
    confidence = 30
    reasons: List[str] = []

    seg = (lead.segment or "").lower()
    if seg in SEGMENTS:
        fit += 12
        confidence += 10
        reasons.append(f"segment:{seg}")
        if seg in ("aerospace", "government-subcontractor"):
            compliance.append("defense/aerospace supply chain")
        if seg == "manufacturing":
            compliance.append("manufacturing operations")
        if seg == "audit-stressed":
            pain.append("documentation/audit pressure")
        if seg == "compliance-heavy":
            compliance.append("regulated SMB profile")

    for kw in POSITIVE_KEYWORDS:
        if kw in blob:
            if kw in ("audit", "documentation", "traceability"):
                pain.append(kw)
            else:
                compliance.append(kw)
            fit += 3
            confidence += 2

    title = (lead.contact_title or "").lower()
    if any(t in title for t in TITLE_POSITIVE):
        fit += 10
        confidence += 12
        reasons.append("relevant contact title")
        compliance.append("quality/compliance/ops contact")

    if lead.contact_email and "@" in lead.contact_email:
        fit += 5
        confidence += 8
        domain = lead.contact_email.split("@", 1)[-1].lower()
        if domain and not any(x in domain for x in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com")):
            confidence += 6
            reasons.append("business email domain")
        else:
            pain.append("personal email domain")

    if lead.website:
        fit += 4
        confidence += 5
        reasons.append("website present")

    if lead.linkedin_url:
        confidence += 4
        reasons.append("linkedin profile listed (manual review)")

    if lead.company_name and 3 <= len(lead.company_name) <= 80:
        confidence += 5

    for kw in NEGATIVE_KEYWORDS:
        if kw in blob:
            fit -= 15
            confidence -= 5
            reasons.append(f"negative:{kw}")

    for ent in ENTERPRISE_HINTS:
        if ent in blob:
            fit -= 20
            reasons.append("enterprise-tier name (MVP poor fit)")

    if not lead.contact_name and not lead.contact_email:
        fit -= 12
        confidence -= 15
        pain.append("no reachable contact")

    if lead.source and "spam" in lead.source.lower():
        fit -= 25
        reasons.append("spam-risk source")

    fit = max(0, min(100, fit))
    confidence = max(0, min(100, confidence))

    pain = list(dict.fromkeys(pain))[:8]
    compliance = list(dict.fromkeys(compliance))[:10]
    summary = "; ".join(reasons[:6]) if reasons else "baseline import scoring"
    return fit, confidence, pain, compliance, summary

"""Rule-based lead scoring (0–100). No ML, no external APIs."""
from __future__ import annotations

import re
from typing import List, Tuple

from .memory import get_learned_weights
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
    
    # PATCH ACQ-SCORING-USASPENDING: Check if this is USASpending target
    is_usaspending = "usaspending" in (lead.source or "").lower()
    contract_value = 0
    dod_percentage = 0
    contract_count = 0
    
    if is_usaspending:
        # Extract contract data from notes (added by enrichment)
        import re
        notes = lead.notes or ""
        
        # Parse "$X.XM in contracts"
        value_match = re.search(r'\$([0-9.]+)M in contracts', notes)
        if value_match:
            contract_value = float(value_match.group(1))  # in millions
        
        # Parse "XX% DoD work"
        dod_match = re.search(r'(\d+)% DoD work', notes)
        if dod_match:
            dod_percentage = int(dod_match.group(1))
        
        # Parse "XX awards"
        awards_match = re.search(r'(\d+) awards', notes)
        if awards_match:
            contract_count = int(awards_match.group(1))
    
    # USASpending: Contract value and DoD work = better fit
    if is_usaspending:
        if contract_value >= 10:  # $10M+ contracts
            fit += 15
            confidence += 15
            reasons.append(f"${contract_value:.1f}M in contracts")
        elif contract_value >= 5:  # $5M-10M
            fit += 12
            confidence += 12
        elif contract_value >= 1:  # $1M-5M
            fit += 8
            confidence += 10
        
        if dod_percentage >= 50:  # 50%+ DoD work
            fit += 12
            confidence += 10
            compliance.append("defense supply chain (DoD)")
            reasons.append(f"{dod_percentage}% DoD work")
        elif dod_percentage >= 25:  # 25-50% DoD
            fit += 8
            compliance.append("partial defense exposure")
        
        if contract_count >= 20:  # 20+ contracts
            fit += 8
            confidence += 8
            pain.append("multiple_contract_compliance_burden")
        elif contract_count >= 10:  # 10-20 contracts
            fit += 5
            pain.append("active_contracting")

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


def apply_intelligence_scores(lead: Lead, weights: dict | None = None) -> Lead:
    """Buying capability, urgency, pain, complexity, trust, priority (adaptive weights)."""
    w = weights or get_learned_weights()
    blob = _text_blob(lead)

    # PATCH ACQ-SCORING-USASPENDING: Use contract data for USASpending targets
    is_usaspending = "usaspending" in (lead.source or "").lower()
    contract_value = 0
    dod_percentage = 0
    contract_count = 0
    
    if is_usaspending:
        # Extract contract data from notes (added by enrichment)
        notes = lead.notes or ""
        # Parse "$X.XM in contracts"
        import re
        value_match = re.search(r'\$([0-9.]+)M in contracts', notes)
        if value_match:
            contract_value = float(value_match.group(1))  # in millions
        
        # Parse "XX% DoD work"
        dod_match = re.search(r'(\d+)% DoD work', notes)
        if dod_match:
            dod_percentage = int(dod_match.group(1))
        
        # Parse "XX awards"
        awards_match = re.search(r'(\d+) awards', notes)
        if awards_match:
            contract_count = int(awards_match.group(1))

    ability = 35
    if lead.contact_email and "@" in lead.contact_email:
        domain = lead.contact_email.split("@", 1)[-1].lower()
        if domain and domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
            ability += 20 + int(w.get("business_email", 0))
    if lead.website:
        ability += 10
    if (lead.segment or "") in ("aerospace", "government-subcontractor", "manufacturing"):
        ability += 12 + int(w.get(f"segment_{lead.segment}", 0))
    if "machining" in blob or "fabrication" in blob:
        ability += 8
    
    # USASpending: Contract value = buying power
    if is_usaspending and contract_value > 0:
        if contract_value >= 50:  # $50M+
            ability += 25
        elif contract_value >= 10:  # $10M-50M
            ability += 20
        elif contract_value >= 5:  # $5M-10M
            ability += 15
        elif contract_value >= 1:  # $1M-5M
            ability += 10
        else:  # < $1M
            ability += 5
    
    ability = max(0, min(100, ability))

    urgency = 20
    for term in ("urgent", "deadline", "audit", "asap", "customer", "prime"):
        if term in blob:
            urgency += 12 + int(w.get("urgency_keyword", 0) / 2)
    
    # USASpending: Higher DoD percentage = higher urgency (CMMC/DFARS compliance needed)
    if is_usaspending and dod_percentage > 0:
        if dod_percentage >= 80:  # 80%+ DoD work = very high compliance urgency
            urgency += 25
        elif dod_percentage >= 50:  # 50-80% DoD
            urgency += 20
        elif dod_percentage >= 25:  # 25-50% DoD
            urgency += 15
        else:  # < 25% DoD
            urgency += 10
    
    urgency = max(0, min(100, urgency))

    pain_score = min(100, len(lead.pain_signals) * 12 + len(lead.compliance_signals) * 5 + 25)
    
    # USASpending: More contracts = more compliance pain (more paperwork, more audits)
    if is_usaspending and contract_count > 0:
        if contract_count >= 50:  # 50+ contracts
            pain_score = min(100, pain_score + 20)
        elif contract_count >= 20:  # 20-50 contracts
            pain_score = min(100, pain_score + 15)
        elif contract_count >= 10:  # 10-20 contracts
            pain_score = min(100, pain_score + 10)
        else:  # < 10 contracts
            pain_score = min(100, pain_score + 5)
    complexity = 25
    if (lead.industry or "").lower() in ("aerospace", "defense", "manufacturing"):
        complexity += 20
    if len(lead.compliance_signals) >= 4:
        complexity += 25
    elif len(lead.compliance_signals) >= 2:
        complexity += 12
    complexity = min(100, complexity)

    trust = 30
    if "readiness" in blob or "documentation" in blob or "upload" in blob:
        trust += 25
    if lead.contact_name:
        trust += 10
    trust = min(100, trust)

    priority = int(
        0.25 * lead.fit_score
        + 0.2 * ability
        + 0.2 * urgency
        + 0.15 * pain_score
        + 0.1 * trust
        + 0.1 * lead.confidence_score
    )
    priority = max(0, min(100, priority))

    lead.ability_to_pay_score = ability
    lead.urgency_score = urgency
    lead.compliance_pain_score = pain_score
    lead.operational_complexity_score = complexity
    lead.trust_readiness_score = trust
    lead.acquisition_priority_score = priority
    return lead


def score_lead_full(lead: Lead, memory_context: dict | None = None) -> Lead:
    fit, conf, pain, comp, summary = score_lead(lead)
    if memory_context and memory_context.get("known"):
        fit = min(100, fit + 3)
        if memory_context.get("prior_projects"):
            conf = min(100, conf + 5)
            summary = summary + "; central_memory:prior_engagement"
        for sig in memory_context.get("signals") or []:
            st = sig.get("signal_type", "")
            if st in ("acquisition", "paperwork", "operational_complexity"):
                pain.append(f"prior_{st}")
    lead.fit_score = fit
    lead.confidence_score = conf
    lead.pain_signals = list(dict.fromkeys(pain))[:8]
    lead.compliance_signals = comp
    lead.reason_summary = summary
    lead = apply_intelligence_scores(lead)
    try:
        from services.memory.telemetry import emit_telemetry

        high = lead.acquisition_priority_score >= 75 or lead.fit_score >= 80
        emit_telemetry(
            "acquisition",
            "lead_scored",
            lead_id=lead.lead_id,
            success=True,
            metadata={
                "fit_score": lead.fit_score,
                "priority": lead.acquisition_priority_score,
                "high_priority": high,
            },
        )
        if high:
            emit_telemetry(
                "acquisition",
                "high_priority_lead_found",
                lead_id=lead.lead_id,
                severity="info",
                metadata={"fit_score": lead.fit_score, "priority": lead.acquisition_priority_score},
            )
        if lead.fit_score < 40:
            emit_telemetry(
                "acquisition",
                "lead_rejected",
                lead_id=lead.lead_id,
                severity="info",
                success=True,
                metadata={"fit_score": lead.fit_score, "reason": "low_fit"},
            )
    except Exception:
        pass
    return lead

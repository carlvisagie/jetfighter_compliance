"""PATCH 13A-13: Customer Intelligence Enrichment Engine.

MISSION: The acquisition organism may NOT contact, score, prioritize, or recommend
action on a company until it has attempted enrichment.

Pipeline:
    DISCOVER → ENRICH → INTELLIGENCE → QUALIFY → OPERATOR

No company proceeds directly from discovery to qualification.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .ideal_customer_profile import (
    CustomerIntelligenceRecord,
    EvidencedValue,
    SignalState,
    ICPTier,
    evaluate_icp_match,
    save_intelligence_record,
    load_intelligence_record,
    list_intelligence_records,
    get_all_intelligence_records,
)


class EnrichmentState(str, Enum):
    """Enrichment pipeline state."""
    DISCOVERED = "DISCOVERED"      # Just found, no enrichment attempted
    ENRICHING = "ENRICHING"        # Enrichment in progress
    ENRICHED = "ENRICHED"          # Enrichment complete (may still have unknowns)
    QUALIFIED = "QUALIFIED"        # Passed qualification threshold
    OPERATOR_REVIEW = "OPERATOR_REVIEW"  # Ready for operator action


class Recommendation(str, Enum):
    """Allowed recommendations - based on evidence, not assumptions."""
    IGNORE = "IGNORE"              # Does not match ICP
    WATCH = "WATCH"                # Match but low priority
    ENRICH = "ENRICH"              # Need more evidence before action
    CONTACT = "CONTACT"            # Have enough evidence to contact
    HIGH_PRIORITY = "HIGH_PRIORITY"  # Tier 1 with sufficient evidence


# =============================================================================
# CRITICAL FIELDS - Cannot recommend CONTACT without these
# =============================================================================

CRITICAL_FIELDS = {
    "company_name",      # Must know who they are
    "contact_email",     # Must be able to reach them
    "contract_count",    # Must have evidence of federal activity
}

IMPORTANT_FIELDS = {
    "uei",
    "location",
    "website",
    "contract_value",
    "award_recency",
    "naics",
    "dod_exposure",
}

ENRICHMENT_FIELDS = {
    "contact_name",
    "industry",
    "company_size",
    "manufacturing_exposure",
    "aerospace_exposure",
    "cmmc_likelihood",
    "dfars_likelihood",
    "agency_mix",
}

ALL_TRACKED_FIELDS = CRITICAL_FIELDS | IMPORTANT_FIELDS | ENRICHMENT_FIELDS


# =============================================================================
# ENRICHMENT SCORE CALCULATION
# =============================================================================

# Points for each field when KNOWN
ENRICHMENT_POINTS = {
    # Identity (20 points)
    "company_name": 5,
    "uei": 10,
    "location": 5,
    
    # Contactability (25 points)
    "website": 10,
    "contact_email": 10,
    "contact_name": 5,
    
    # Contract Intelligence (30 points)
    "contract_count": 5,
    "contract_value": 10,
    "award_recency": 5,
    "naics": 5,
    "agency_mix": 5,
    
    # Compliance Profile (15 points)
    "dod_exposure": 5,
    "cmmc_likelihood": 3,
    "dfars_likelihood": 3,
    "manufacturing_exposure": 2,
    "aerospace_exposure": 2,
    
    # Business Profile (10 points)
    "industry": 5,
    "company_size": 5,
}


def compute_enrichment_score(record: CustomerIntelligenceRecord) -> int:
    """
    Compute enrichment score (0-100).
    
    Measures how much we KNOW about the company, not how good they are.
    """
    total = 0
    
    for field_name, points in ENRICHMENT_POINTS.items():
        ev = getattr(record, field_name, None)
        if ev and isinstance(ev, EvidencedValue):
            if ev.state == SignalState.KNOWN and ev.value is not None:
                total += points
    
    return min(100, total)


# =============================================================================
# UNKNOWN HUNTER - Track exactly what we don't know
# =============================================================================

@dataclass
class FieldStatus:
    """Status of a single intelligence field."""
    name: str
    state: SignalState
    value: Any = None
    source: str = ""
    confidence: float = 0.0
    importance: str = "normal"  # critical, important, normal


def get_field_statuses(record: CustomerIntelligenceRecord) -> Dict[str, FieldStatus]:
    """Get status of all tracked fields."""
    statuses = {}
    
    for field_name in ALL_TRACKED_FIELDS:
        ev = getattr(record, field_name, None)
        
        if field_name in CRITICAL_FIELDS:
            importance = "critical"
        elif field_name in IMPORTANT_FIELDS:
            importance = "important"
        else:
            importance = "normal"
        
        if ev and isinstance(ev, EvidencedValue):
            statuses[field_name] = FieldStatus(
                name=field_name,
                state=ev.state,
                value=ev.value,
                source=ev.source,
                confidence=ev.confidence,
                importance=importance,
            )
        else:
            statuses[field_name] = FieldStatus(
                name=field_name,
                state=SignalState.UNKNOWN,
                importance=importance,
            )
    
    return statuses


def get_known_fields(record: CustomerIntelligenceRecord) -> List[str]:
    """Get list of KNOWN fields with actual values."""
    known = []
    statuses = get_field_statuses(record)
    
    for name, status in statuses.items():
        if status.state == SignalState.KNOWN and status.value is not None:
            known.append(name)
    
    return sorted(known)


def get_unknown_fields(record: CustomerIntelligenceRecord) -> List[str]:
    """Get list of UNKNOWN fields."""
    unknown = []
    statuses = get_field_statuses(record)
    
    for name, status in statuses.items():
        if status.state == SignalState.UNKNOWN or status.value is None:
            unknown.append(name)
    
    return sorted(unknown)


def get_missing_critical_fields(record: CustomerIntelligenceRecord) -> List[str]:
    """Get list of CRITICAL fields that are UNKNOWN."""
    missing = []
    statuses = get_field_statuses(record)
    
    for name in CRITICAL_FIELDS:
        status = statuses.get(name)
        if not status or status.state == SignalState.UNKNOWN or status.value is None:
            missing.append(name)
    
    return sorted(missing)


def get_next_missing_evidence(record: CustomerIntelligenceRecord) -> Optional[str]:
    """Get the single most important missing piece of evidence."""
    # Check critical fields first
    for name in ["contact_email", "company_name", "contract_count"]:
        ev = getattr(record, name, None)
        if not ev or ev.state == SignalState.UNKNOWN or ev.value is None:
            return name
    
    # Then important fields
    for name in ["website", "contract_value", "uei", "award_recency", "naics"]:
        ev = getattr(record, name, None)
        if not ev or ev.state == SignalState.UNKNOWN or ev.value is None:
            return name
    
    # Then enrichment fields
    for name in ENRICHMENT_FIELDS:
        ev = getattr(record, name, None)
        if not ev or ev.state == SignalState.UNKNOWN or ev.value is None:
            return name
    
    return None


# =============================================================================
# RECOMMENDATION ENGINE - Evidence-based decisions
# =============================================================================

def compute_recommendation(
    record: CustomerIntelligenceRecord,
    icp_match: Optional[Dict[str, Any]] = None,
) -> Tuple[Recommendation, str]:
    """
    Compute recommendation based on evidence.
    
    Rules:
    1. If completeness < 50% → ENRICH
    2. If any critical field unknown → ENRICH
    3. If evidence insufficient for ICP match → ENRICH
    4. Otherwise, base on ICP tier
    """
    if icp_match is None:
        icp_match = evaluate_icp_match(record)
    
    completeness = record.compute_intelligence_completeness()
    enrichment = compute_enrichment_score(record)
    missing_critical = get_missing_critical_fields(record)
    tier = icp_match.get("tier", ICPTier.NO_MATCH.value)
    
    # Rule 1: Low completeness requires enrichment
    if completeness < 50:
        return Recommendation.ENRICH, f"Intelligence completeness {completeness}% < 50% threshold"
    
    # Rule 2: Missing critical fields requires enrichment
    if missing_critical:
        return Recommendation.ENRICH, f"Missing critical fields: {', '.join(missing_critical)}"
    
    # Rule 3: Low enrichment score requires enrichment
    if enrichment < 40:
        return Recommendation.ENRICH, f"Enrichment score {enrichment}% < 40% threshold"
    
    # Rule 4: Too many unknowns in ICP criteria
    criteria_unknown = icp_match.get("criteria_unknown", [])
    if len(criteria_unknown) >= 3:
        return Recommendation.ENRICH, f"Too many unknown ICP criteria: {len(criteria_unknown)}"
    
    # Rule 5: No ICP match
    if tier == ICPTier.NO_MATCH.value:
        return Recommendation.IGNORE, "Does not match Ideal Customer Profile"
    
    # Rule 6: Evidence sufficient - recommend based on tier
    if tier == ICPTier.TIER_1.value and enrichment >= 60:
        return Recommendation.HIGH_PRIORITY, f"Tier 1 match with {enrichment}% enrichment"
    
    if tier == ICPTier.TIER_1.value:
        return Recommendation.CONTACT, f"Tier 1 match, consider enrichment to {enrichment}%"
    
    if tier == ICPTier.TIER_2.value and enrichment >= 50:
        return Recommendation.CONTACT, f"Tier 2 match with {enrichment}% enrichment"
    
    if tier == ICPTier.TIER_2.value:
        return Recommendation.ENRICH, f"Tier 2 match but enrichment {enrichment}% < 50%"
    
    if tier == ICPTier.TIER_3.value:
        return Recommendation.WATCH, "Tier 3 match - federal award recipient only"
    
    return Recommendation.WATCH, "Insufficient evidence for higher recommendation"


# =============================================================================
# PROSPECT RANKING - For the Top 100 report
# =============================================================================

@dataclass
class ProspectRanking:
    """A ranked prospect with full evidence trail."""
    rank: int
    record_id: str
    company_name: str
    tier: str
    completeness: int
    enrichment_score: int
    known_count: int
    unknown_count: int
    known_fields: List[str]
    unknown_fields: List[str]
    missing_critical: List[str]
    recommendation: Recommendation
    reasoning: str
    next_missing_evidence: Optional[str]
    contactability: int
    ability_to_pay: int
    
    # Evidence summary
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "record_id": self.record_id,
            "company": self.company_name,
            "tier": self.tier,
            "completeness": self.completeness,
            "enrichment_score": self.enrichment_score,
            "known_pct": round(100 * self.known_count / (self.known_count + self.unknown_count)) if (self.known_count + self.unknown_count) > 0 else 0,
            "unknown_pct": round(100 * self.unknown_count / (self.known_count + self.unknown_count)) if (self.known_count + self.unknown_count) > 0 else 0,
            "known_fields": self.known_fields,
            "unknown_fields": self.unknown_fields,
            "missing_critical": self.missing_critical,
            "recommendation": self.recommendation.value,
            "reasoning": self.reasoning,
            "next_missing_evidence": self.next_missing_evidence,
            "contactability": self.contactability,
            "ability_to_pay": self.ability_to_pay,
            "evidence_summary": self.evidence_summary,
        }


def rank_prospect(record: CustomerIntelligenceRecord, rank: int = 0) -> ProspectRanking:
    """Create a full ranking for a single prospect."""
    icp_match = evaluate_icp_match(record)
    recommendation, reasoning = compute_recommendation(record, icp_match)
    
    known = get_known_fields(record)
    unknown = get_unknown_fields(record)
    missing_critical = get_missing_critical_fields(record)
    
    # Build evidence summary
    evidence = {}
    for field_name in known:
        ev = getattr(record, field_name, None)
        if ev and isinstance(ev, EvidencedValue):
            evidence[field_name] = {
                "value": ev.value,
                "source": ev.source,
                "confidence": ev.confidence,
            }
    
    return ProspectRanking(
        rank=rank,
        record_id=record.record_id,
        company_name=record.company_name.value if record.company_name.value else "Unknown",
        tier=icp_match.get("tier", "NO_MATCH"),
        completeness=record.compute_intelligence_completeness(),
        enrichment_score=compute_enrichment_score(record),
        known_count=len(known),
        unknown_count=len(unknown),
        known_fields=known,
        unknown_fields=unknown,
        missing_critical=missing_critical,
        recommendation=recommendation,
        reasoning=reasoning,
        next_missing_evidence=get_next_missing_evidence(record),
        contactability=record.compute_contactability(),
        ability_to_pay=record.compute_ability_to_pay(),
        evidence_summary=evidence,
    )


def rank_all_prospects(limit: int = 100) -> List[ProspectRanking]:
    """
    Rank all prospects by evidence quality.
    
    Ranking criteria (in order):
    1. Recommendation (HIGH_PRIORITY > CONTACT > WATCH > ENRICH > IGNORE)
    2. ICP Tier (TIER_1 > TIER_2 > TIER_3 > NO_MATCH)
    3. Enrichment score (higher is better)
    4. Completeness (higher is better)
    """
    records = get_all_intelligence_records()
    
    # Create rankings
    rankings = [rank_prospect(r) for r in records]
    
    # Sort by evidence quality
    recommendation_order = {
        Recommendation.HIGH_PRIORITY: 0,
        Recommendation.CONTACT: 1,
        Recommendation.WATCH: 2,
        Recommendation.ENRICH: 3,
        Recommendation.IGNORE: 4,
    }
    
    tier_order = {
        ICPTier.TIER_1.value: 0,
        ICPTier.TIER_2.value: 1,
        ICPTier.TIER_3.value: 2,
        ICPTier.NO_MATCH.value: 3,
    }
    
    rankings.sort(key=lambda r: (
        recommendation_order.get(r.recommendation, 5),
        tier_order.get(r.tier, 4),
        -r.enrichment_score,
        -r.completeness,
    ))
    
    # Assign ranks
    for i, ranking in enumerate(rankings[:limit], 1):
        ranking.rank = i
    
    return rankings[:limit]


# =============================================================================
# ORGANISM 5-QUESTION TEST
# =============================================================================

def can_answer_five_questions(record: CustomerIntelligenceRecord) -> Dict[str, Any]:
    """
    Test if the organism can answer the 5 key questions about a prospect.
    
    Questions:
    1. Who is the best prospect? → Need ICP match
    2. Why? → Need criteria_met
    3. What evidence supports that? → Need known_fields with sources
    4. What evidence is missing? → Need unknown_fields
    5. What should happen next? → Need recommendation
    
    If ANY question cannot be answered, ranking is FORBIDDEN.
    """
    icp_match = evaluate_icp_match(record)
    recommendation, reasoning = compute_recommendation(record, icp_match)
    known = get_known_fields(record)
    unknown = get_unknown_fields(record)
    
    answers = {
        "can_rank": True,
        "questions": {},
    }
    
    # Q1: Who is the best prospect?
    company = record.company_name.value if record.company_name.value else None
    if company:
        answers["questions"]["who"] = {
            "answered": True,
            "answer": company,
        }
    else:
        answers["questions"]["who"] = {
            "answered": False,
            "answer": None,
            "reason": "Company name unknown",
        }
        answers["can_rank"] = False
    
    # Q2: Why?
    criteria_met = icp_match.get("criteria_met", [])
    tier = icp_match.get("tier", "NO_MATCH")
    if criteria_met:
        answers["questions"]["why"] = {
            "answered": True,
            "answer": f"ICP {tier}: {', '.join(criteria_met)}",
        }
    else:
        answers["questions"]["why"] = {
            "answered": True,
            "answer": f"ICP tier: {tier} (no specific criteria met yet)",
        }
    
    # Q3: What evidence supports that?
    if known:
        evidence_summary = []
        for field_name in known[:5]:  # Top 5
            ev = getattr(record, field_name, None)
            if ev and isinstance(ev, EvidencedValue):
                evidence_summary.append(f"{field_name}={ev.value} (source:{ev.source})")
        answers["questions"]["evidence"] = {
            "answered": True,
            "answer": evidence_summary,
            "total_known": len(known),
        }
    else:
        answers["questions"]["evidence"] = {
            "answered": False,
            "answer": None,
            "reason": "No evidence collected",
        }
        answers["can_rank"] = False
    
    # Q4: What evidence is missing?
    answers["questions"]["missing"] = {
        "answered": True,
        "answer": unknown,
        "total_unknown": len(unknown),
    }
    
    # Q5: What should happen next?
    answers["questions"]["next_action"] = {
        "answered": True,
        "answer": recommendation.value,
        "reasoning": reasoning,
    }
    
    # Final verdict
    answers["verdict"] = "RANKING_ALLOWED" if answers["can_rank"] else "RANKING_FORBIDDEN"
    
    return answers


def validate_ranking_allowed(record: CustomerIntelligenceRecord) -> Tuple[bool, str]:
    """Check if ranking is allowed for this record."""
    result = can_answer_five_questions(record)
    
    if result["can_rank"]:
        return True, "All 5 questions can be answered"
    
    failed_questions = [
        q for q, data in result["questions"].items()
        if not data.get("answered", False)
    ]
    
    return False, f"Cannot answer: {', '.join(failed_questions)}"


# =============================================================================
# ENRICHMENT PIPELINE STATE
# =============================================================================

def get_enrichment_state(record: CustomerIntelligenceRecord) -> EnrichmentState:
    """Determine current enrichment pipeline state."""
    completeness = record.compute_intelligence_completeness()
    enrichment = compute_enrichment_score(record)
    recommendation, _ = compute_recommendation(record)
    
    # Just discovered - minimal info
    if enrichment < 20:
        return EnrichmentState.DISCOVERED
    
    # Has some enrichment but not enough
    if enrichment < 50 or completeness < 50:
        return EnrichmentState.ENRICHING
    
    # Enriched but needs operator review
    if recommendation in (Recommendation.CONTACT, Recommendation.HIGH_PRIORITY):
        return EnrichmentState.OPERATOR_REVIEW
    
    # Enriched and qualified
    if recommendation != Recommendation.IGNORE:
        return EnrichmentState.QUALIFIED
    
    # Enriched but not a match
    return EnrichmentState.ENRICHED


# =============================================================================
# TOP PROSPECTS REPORT
# =============================================================================

def generate_top_prospects_report(limit: int = 100) -> Dict[str, Any]:
    """
    Generate the Top 100 Prospects report.
    
    For every company:
    - Rank
    - Company name
    - ICP Tier
    - Completeness
    - Known evidence
    - Unknown evidence
    - Recommendation
    - Reasoning
    """
    rankings = rank_all_prospects(limit=limit)
    
    # Summary statistics
    by_recommendation = {}
    by_tier = {}
    can_contact = 0
    need_enrichment = 0
    
    for r in rankings:
        # By recommendation
        rec = r.recommendation.value
        by_recommendation[rec] = by_recommendation.get(rec, 0) + 1
        
        # By tier
        by_tier[r.tier] = by_tier.get(r.tier, 0) + 1
        
        # Contact-ready vs need enrichment
        if r.recommendation in (Recommendation.CONTACT, Recommendation.HIGH_PRIORITY):
            can_contact += 1
        elif r.recommendation == Recommendation.ENRICH:
            need_enrichment += 1
    
    return {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_prospects": len(rankings),
        "summary": {
            "can_contact": can_contact,
            "need_enrichment": need_enrichment,
            "by_recommendation": by_recommendation,
            "by_tier": by_tier,
        },
        "prospects": [r.to_dict() for r in rankings],
        "columns": [
            "Rank",
            "Company",
            "Tier",
            "Completeness",
            "Enrichment Score",
            "Known %",
            "Unknown %",
            "Recommendation",
            "Next Missing Evidence",
        ],
    }


# =============================================================================
# COCKPIT VIEW DATA
# =============================================================================

def get_cockpit_view() -> Dict[str, Any]:
    """
    Get data for the Customer Intelligence Cockpit.
    
    Returns data structured for operator dashboard display.
    """
    rankings = rank_all_prospects(limit=100)
    
    # Group by recommendation
    high_priority = [r for r in rankings if r.recommendation == Recommendation.HIGH_PRIORITY]
    contact = [r for r in rankings if r.recommendation == Recommendation.CONTACT]
    watch = [r for r in rankings if r.recommendation == Recommendation.WATCH]
    enrich = [r for r in rankings if r.recommendation == Recommendation.ENRICH]
    ignore = [r for r in rankings if r.recommendation == Recommendation.IGNORE]
    
    # Calculate average completeness
    avg_completeness = sum(r.completeness for r in rankings) / len(rankings) if rankings else 0
    avg_enrichment = sum(r.enrichment_score for r in rankings) / len(rankings) if rankings else 0
    
    return {
        "ok": True,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": {
            "total_prospects": len(rankings),
            "high_priority": len(high_priority),
            "contact_ready": len(contact),
            "watching": len(watch),
            "need_enrichment": len(enrich),
            "ignored": len(ignore),
        },
        "averages": {
            "completeness": round(avg_completeness, 1),
            "enrichment": round(avg_enrichment, 1),
        },
        "top_prospects": [r.to_dict() for r in high_priority + contact][:20],
        "need_enrichment": [r.to_dict() for r in enrich][:20],
        "columns": [
            "Company",
            "ICP Tier",
            "Completeness",
            "Enrichment Score",
            "Known %",
            "Unknown %",
            "Recommendation",
            "Next Missing Evidence",
        ],
    }

"""PATCH 13A-20: Buying Likelihood Intelligence Engine.

Determines which companies are most likely to become customers.

NO OUTREACH. NO EMAILS. NO AUTO-SEND. NO MARKETING.
EVIDENCE ONLY.

Every score must be explainable.
Unknown remains UNKNOWN.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .ideal_customer_profile import (
    CustomerIntelligenceRecord,
    EvidencedValue,
    SignalState,
    get_all_intelligence_records,
    evaluate_icp_match,
)
from .decision_maker_intelligence import (
    compute_title_relevance_score,
    get_title_tier,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PHASE 1: BUYING SIGNAL INVENTORY
# =============================================================================

BUYING_SIGNALS = {
    # Contract Intelligence Signals
    "contract_value": {
        "description": "Total federal contract value",
        "weight": 15,
        "positive_threshold": 100000,
        "high_value_threshold": 1000000,
        "evidence_type": "financial",
    },
    "contract_count": {
        "description": "Number of federal contracts",
        "weight": 10,
        "positive_threshold": 1,
        "high_value_threshold": 5,
        "evidence_type": "activity",
    },
    "award_recency": {
        "description": "Days since most recent award",
        "weight": 12,
        "positive_threshold": 365,  # Within 1 year
        "high_value_threshold": 180,  # Within 6 months
        "evidence_type": "timing",
    },
    
    # Compliance Exposure Signals
    "dod_exposure": {
        "description": "Has DoD contract exposure",
        "weight": 15,
        "positive_threshold": True,
        "evidence_type": "compliance",
    },
    "cmmc_likelihood": {
        "description": "Likelihood of CMMC requirement",
        "weight": 10,
        "positive_threshold": 0.5,
        "high_value_threshold": 0.8,
        "evidence_type": "compliance",
    },
    "dfars_likelihood": {
        "description": "Likelihood of DFARS requirement",
        "weight": 10,
        "positive_threshold": 0.5,
        "high_value_threshold": 0.8,
        "evidence_type": "compliance",
    },
    
    # Industry Signals
    "manufacturing_exposure": {
        "description": "Manufacturing industry indicator",
        "weight": 5,
        "positive_threshold": True,
        "evidence_type": "industry",
    },
    "aerospace_exposure": {
        "description": "Aerospace industry indicator",
        "weight": 5,
        "positive_threshold": True,
        "evidence_type": "industry",
    },
    
    # Contactability Signals
    "decision_maker_present": {
        "description": "Decision maker identified",
        "weight": 12,
        "positive_threshold": True,
        "evidence_type": "contactability",
    },
    "contact_email_present": {
        "description": "Contact email available",
        "weight": 8,
        "positive_threshold": True,
        "evidence_type": "contactability",
    },
    "website_present": {
        "description": "Company website available",
        "weight": 3,
        "positive_threshold": True,
        "evidence_type": "discovery",
    },
    
    # Intelligence Completeness
    "intelligence_completeness": {
        "description": "Overall intelligence completeness",
        "weight": 5,
        "positive_threshold": 40,
        "high_value_threshold": 70,
        "evidence_type": "quality",
    },
}


def get_buying_signal_inventory() -> Dict[str, Any]:
    """
    PHASE 1: Return complete buying signal inventory.
    """
    return {
        "signals": BUYING_SIGNALS,
        "total_signals": len(BUYING_SIGNALS),
        "max_possible_score": sum(s["weight"] for s in BUYING_SIGNALS.values()),
        "signal_categories": {
            "financial": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "financial"],
            "activity": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "activity"],
            "timing": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "timing"],
            "compliance": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "compliance"],
            "industry": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "industry"],
            "contactability": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "contactability"],
            "discovery": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "discovery"],
            "quality": [k for k, v in BUYING_SIGNALS.items() if v["evidence_type"] == "quality"],
        },
    }


# =============================================================================
# PHASE 2: BUYING LIKELIHOOD MODEL
# =============================================================================

@dataclass
class SignalEvidence:
    """Evidence for a single signal."""
    signal_name: str
    value: Any
    state: str  # KNOWN, UNKNOWN
    weight: int
    points_earned: int
    is_positive: bool
    is_high_value: bool
    explanation: str


def evaluate_signal(
    record: CustomerIntelligenceRecord,
    signal_name: str,
    signal_config: Dict[str, Any],
) -> SignalEvidence:
    """Evaluate a single signal for a record."""
    
    # Get the field value based on signal name
    value = None
    state = SignalState.UNKNOWN
    
    if signal_name == "contract_value":
        if record.contract_value.state == SignalState.KNOWN:
            value = record.contract_value.value
            state = SignalState.KNOWN
    
    elif signal_name == "contract_count":
        if record.contract_count.state == SignalState.KNOWN:
            value = record.contract_count.value
            state = SignalState.KNOWN
    
    elif signal_name == "award_recency":
        if record.award_recency.state == SignalState.KNOWN:
            recency_val = record.award_recency.value
            if isinstance(recency_val, int):
                value = recency_val
            elif isinstance(recency_val, str) and recency_val:
                try:
                    award_date = datetime.strptime(recency_val[:10], "%Y-%m-%d")
                    value = (datetime.now() - award_date).days
                except (ValueError, TypeError):
                    pass
            if value is not None:
                state = SignalState.KNOWN
    
    elif signal_name == "dod_exposure":
        if record.dod_exposure.state == SignalState.KNOWN:
            value = record.dod_exposure.value
            state = SignalState.KNOWN
    
    elif signal_name == "cmmc_likelihood":
        if record.cmmc_likelihood.state == SignalState.KNOWN:
            value = record.cmmc_likelihood.value
            state = SignalState.KNOWN
    
    elif signal_name == "dfars_likelihood":
        if record.dfars_likelihood.state == SignalState.KNOWN:
            value = record.dfars_likelihood.value
            state = SignalState.KNOWN
    
    elif signal_name == "manufacturing_exposure":
        if record.manufacturing_exposure.state == SignalState.KNOWN:
            value = record.manufacturing_exposure.value
            state = SignalState.KNOWN
    
    elif signal_name == "aerospace_exposure":
        if record.aerospace_exposure.state == SignalState.KNOWN:
            value = record.aerospace_exposure.value
            state = SignalState.KNOWN
    
    elif signal_name == "decision_maker_present":
        dm_known = record.decision_maker_name.state == SignalState.KNOWN and record.decision_maker_name.value
        value = dm_known
        state = SignalState.KNOWN  # We always know if we have a DM or not
    
    elif signal_name == "contact_email_present":
        email_known = record.contact_email.state == SignalState.KNOWN and record.contact_email.value
        value = email_known
        state = SignalState.KNOWN
    
    elif signal_name == "website_present":
        website_known = record.website.state == SignalState.KNOWN and record.website.value
        value = website_known
        state = SignalState.KNOWN
    
    elif signal_name == "intelligence_completeness":
        value = record.compute_intelligence_completeness()
        state = SignalState.KNOWN
    
    # Compute points
    weight = signal_config["weight"]
    positive_threshold = signal_config["positive_threshold"]
    high_threshold = signal_config.get("high_value_threshold")
    
    is_positive = False
    is_high_value = False
    points_earned = 0
    explanation = ""
    
    if state == SignalState.UNKNOWN or value is None:
        explanation = f"{signal_name}: UNKNOWN"
    else:
        # Evaluate based on threshold type
        if isinstance(positive_threshold, bool):
            is_positive = bool(value) == positive_threshold
            if is_positive:
                points_earned = weight
                explanation = f"{signal_name}: YES"
            else:
                explanation = f"{signal_name}: NO"
        elif signal_name == "award_recency":
            # Lower is better for recency
            if value <= positive_threshold:
                is_positive = True
                points_earned = weight
                if high_threshold and value <= high_threshold:
                    is_high_value = True
                    points_earned = int(weight * 1.5)
                    explanation = f"{signal_name}: {value} days (very recent)"
                else:
                    explanation = f"{signal_name}: {value} days (recent)"
            else:
                explanation = f"{signal_name}: {value} days (not recent)"
        else:
            # Higher is better
            if value >= positive_threshold:
                is_positive = True
                points_earned = weight
                if high_threshold and value >= high_threshold:
                    is_high_value = True
                    points_earned = int(weight * 1.5)
                    if signal_name == "contract_value":
                        explanation = f"{signal_name}: ${value:,.0f} (high value)"
                    else:
                        explanation = f"{signal_name}: {value} (high value)"
                else:
                    if signal_name == "contract_value":
                        explanation = f"{signal_name}: ${value:,.0f}"
                    else:
                        explanation = f"{signal_name}: {value}"
            else:
                if signal_name == "contract_value":
                    explanation = f"{signal_name}: ${value:,.0f} (below threshold)"
                else:
                    explanation = f"{signal_name}: {value} (below threshold)"
    
    return SignalEvidence(
        signal_name=signal_name,
        value=value,
        state=state.value if isinstance(state, SignalState) else state,
        weight=weight,
        points_earned=points_earned,
        is_positive=is_positive,
        is_high_value=is_high_value,
        explanation=explanation,
    )


def compute_buying_likelihood_score(record: CustomerIntelligenceRecord) -> Tuple[int, List[SignalEvidence]]:
    """
    PHASE 2: Compute buying likelihood score with full evidence trail.
    
    Returns (score, evidence_list).
    No AI guessing. No synthetic urgency. Every score explainable.
    """
    evidence_list = []
    total_score = 0
    
    for signal_name, signal_config in BUYING_SIGNALS.items():
        evidence = evaluate_signal(record, signal_name, signal_config)
        evidence_list.append(evidence)
        total_score += evidence.points_earned
    
    return total_score, evidence_list


# =============================================================================
# PHASE 3: EXPLAINABILITY
# =============================================================================

@dataclass
class BuyingExplanation:
    """Full explanation for why a company is ranked."""
    why_this_company: str
    why_now: str
    supporting_evidence: List[str]
    missing_evidence: List[str]
    next_action: str
    confidence: float


def generate_explanation(
    record: CustomerIntelligenceRecord,
    score: int,
    evidence_list: List[SignalEvidence],
    tier: str,
) -> BuyingExplanation:
    """
    PHASE 3: Generate explainable reasoning for a company's ranking.
    
    Every statement cites known evidence.
    """
    company_name = record.company_name.value or "Unknown Company"
    
    # Collect supporting evidence
    supporting = []
    missing = []
    
    positive_signals = [e for e in evidence_list if e.is_positive]
    high_value_signals = [e for e in evidence_list if e.is_high_value]
    unknown_signals = [e for e in evidence_list if e.state == "UNKNOWN"]
    negative_signals = [e for e in evidence_list if not e.is_positive and e.state != "UNKNOWN"]
    
    for e in positive_signals:
        supporting.append(e.explanation)
    
    for e in unknown_signals:
        missing.append(e.signal_name)
    
    # Generate WHY_THIS_COMPANY
    why_company_parts = []
    
    if record.dod_exposure.state == SignalState.KNOWN and record.dod_exposure.value:
        why_company_parts.append("has DoD contract exposure")
    
    if record.contract_value.state == SignalState.KNOWN and record.contract_value.value:
        val = record.contract_value.value
        why_company_parts.append(f"${val:,.0f} in federal contracts")
    
    if record.manufacturing_exposure.state == SignalState.KNOWN and record.manufacturing_exposure.value:
        why_company_parts.append("manufacturing industry")
    
    if record.aerospace_exposure.state == SignalState.KNOWN and record.aerospace_exposure.value:
        why_company_parts.append("aerospace industry")
    
    dm_present = record.decision_maker_name.state == SignalState.KNOWN and record.decision_maker_name.value
    if dm_present:
        dm_name = record.decision_maker_name.value
        dm_title = record.decision_maker_title.value if record.decision_maker_title.state == SignalState.KNOWN else None
        if dm_title:
            why_company_parts.append(f"decision maker identified ({dm_title})")
        else:
            why_company_parts.append(f"decision maker identified ({dm_name})")
    
    if why_company_parts:
        why_this_company = f"{company_name} " + ", ".join(why_company_parts)
    else:
        why_this_company = f"{company_name} has limited evidence available"
    
    # Generate WHY_NOW
    why_now_parts = []
    
    # Check award recency
    recency_evidence = next((e for e in evidence_list if e.signal_name == "award_recency"), None)
    if recency_evidence and recency_evidence.is_positive:
        if recency_evidence.value and recency_evidence.value <= 180:
            why_now_parts.append("very recent federal award activity")
        elif recency_evidence.value and recency_evidence.value <= 365:
            why_now_parts.append("recent federal award activity")
    
    # Check compliance likelihood
    cmmc_ev = next((e for e in evidence_list if e.signal_name == "cmmc_likelihood"), None)
    if cmmc_ev and cmmc_ev.is_positive:
        why_now_parts.append("high CMMC compliance likelihood")
    
    dfars_ev = next((e for e in evidence_list if e.signal_name == "dfars_likelihood"), None)
    if dfars_ev and dfars_ev.is_positive:
        why_now_parts.append("high DFARS compliance likelihood")
    
    if why_now_parts:
        why_now = "Timing favorable: " + ", ".join(why_now_parts)
    else:
        why_now = "No specific timing urgency identified from evidence"
    
    # Generate NEXT_ACTION
    if tier == "BUY_NOW":
        if dm_present and record.contact_email.state == SignalState.KNOWN:
            next_action = "READY_FOR_CONTACT: Decision maker and contact info available"
        else:
            next_action = "ENRICH_CONTACT: High potential but needs contact info"
    elif tier == "HIGH_POTENTIAL":
        if not dm_present:
            next_action = "ENRICH_DECISION_MAKER: Identify who can buy"
        elif record.contact_email.state != SignalState.KNOWN:
            next_action = "ENRICH_CONTACT: Find contact email"
        else:
            next_action = "REVIEW_FOR_OUTREACH: Evidence supports contact"
    elif tier == "MEDIUM_POTENTIAL":
        missing_critical = [m for m in missing if m in ["contract_value", "dod_exposure", "decision_maker_present"]]
        if missing_critical:
            next_action = f"ENRICH: Missing {', '.join(missing_critical[:3])}"
        else:
            next_action = "ENRICH: Gather more evidence"
    elif tier == "LOW_POTENTIAL":
        next_action = "WATCH: Monitor for new activity"
    else:
        next_action = "INSUFFICIENT_EVIDENCE: Cannot recommend action"
    
    # Confidence based on evidence completeness
    known_count = sum(1 for e in evidence_list if e.state != "UNKNOWN")
    confidence = known_count / len(evidence_list) if evidence_list else 0.0
    
    return BuyingExplanation(
        why_this_company=why_this_company,
        why_now=why_now,
        supporting_evidence=supporting,
        missing_evidence=missing,
        next_action=next_action,
        confidence=confidence,
    )


# =============================================================================
# PHASE 4: BUYING READINESS TIERS
# =============================================================================

class BuyingTier(str, Enum):
    BUY_NOW = "BUY_NOW"
    HIGH_POTENTIAL = "HIGH_POTENTIAL"
    MEDIUM_POTENTIAL = "MEDIUM_POTENTIAL"
    LOW_POTENTIAL = "LOW_POTENTIAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def classify_buying_tier(
    score: int,
    evidence_list: List[SignalEvidence],
    record: CustomerIntelligenceRecord,
) -> BuyingTier:
    """
    PHASE 4: Classify company into buying readiness tier.
    
    Unknown remains unknown.
    Never force a company into BUY_NOW.
    """
    max_score = sum(s["weight"] for s in BUYING_SIGNALS.values())
    score_pct = (score / max_score * 100) if max_score > 0 else 0
    
    # Count known vs unknown
    known_signals = sum(1 for e in evidence_list if e.state != "UNKNOWN")
    total_signals = len(evidence_list)
    evidence_coverage = (known_signals / total_signals * 100) if total_signals > 0 else 0
    
    # Check critical signals
    has_contract_value = any(e.signal_name == "contract_value" and e.is_positive for e in evidence_list)
    has_dod = any(e.signal_name == "dod_exposure" and e.is_positive for e in evidence_list)
    has_decision_maker = any(e.signal_name == "decision_maker_present" and e.is_positive for e in evidence_list)
    has_email = any(e.signal_name == "contact_email_present" and e.is_positive for e in evidence_list)
    has_recent_activity = any(e.signal_name == "award_recency" and e.is_positive for e in evidence_list)
    
    # INSUFFICIENT_EVIDENCE: Less than 30% evidence coverage
    if evidence_coverage < 30:
        return BuyingTier.INSUFFICIENT_EVIDENCE
    
    # BUY_NOW: High score + critical signals + contactable
    if (
        score_pct >= 70
        and has_contract_value
        and has_dod
        and (has_decision_maker or has_email)
        and has_recent_activity
    ):
        return BuyingTier.BUY_NOW
    
    # HIGH_POTENTIAL: Good score + key signals
    if (
        score_pct >= 50
        and has_contract_value
        and (has_dod or has_recent_activity)
    ):
        return BuyingTier.HIGH_POTENTIAL
    
    # MEDIUM_POTENTIAL: Moderate evidence
    if score_pct >= 30 or (has_contract_value and evidence_coverage >= 50):
        return BuyingTier.MEDIUM_POTENTIAL
    
    # LOW_POTENTIAL: Some evidence but not compelling
    if evidence_coverage >= 30:
        return BuyingTier.LOW_POTENTIAL
    
    return BuyingTier.INSUFFICIENT_EVIDENCE


# =============================================================================
# PHASE 5: ORGANISM QUESTIONS
# =============================================================================

@dataclass
class OrganismAnswers:
    """Answers to the organism's 6 key questions."""
    most_likely_customer: Optional[str]
    why: str
    why_now: str
    supporting_evidence: List[str]
    missing_evidence: List[str]
    next_action: str
    has_sufficient_evidence: bool


def answer_organism_questions(
    top_prospect: Optional[Dict[str, Any]],
) -> OrganismAnswers:
    """
    PHASE 5: Answer the organism's 6 key questions.
    
    1. Which company is most likely to become a customer?
    2. Why?
    3. Why now?
    4. What evidence supports that?
    5. What evidence is still missing?
    6. What should happen next?
    """
    if not top_prospect:
        return OrganismAnswers(
            most_likely_customer=None,
            why="No prospects with sufficient evidence",
            why_now="N/A",
            supporting_evidence=[],
            missing_evidence=["All signals"],
            next_action="RUN_DISCOVERY: Need to discover companies first",
            has_sufficient_evidence=False,
        )
    
    tier = top_prospect.get("buying_tier", "INSUFFICIENT_EVIDENCE")
    
    if tier == "INSUFFICIENT_EVIDENCE":
        return OrganismAnswers(
            most_likely_customer=top_prospect.get("company"),
            why="Best available prospect but evidence is insufficient",
            why_now="Cannot determine timing without more evidence",
            supporting_evidence=top_prospect.get("supporting_evidence", []),
            missing_evidence=top_prospect.get("missing_evidence", []),
            next_action=top_prospect.get("next_action", "ENRICH: Gather more evidence"),
            has_sufficient_evidence=False,
        )
    
    return OrganismAnswers(
        most_likely_customer=top_prospect.get("company"),
        why=top_prospect.get("why_this_company", "Evidence supports high buying likelihood"),
        why_now=top_prospect.get("why_now", "No specific timing factors"),
        supporting_evidence=top_prospect.get("supporting_evidence", []),
        missing_evidence=top_prospect.get("missing_evidence", []),
        next_action=top_prospect.get("next_action", "REVIEW"),
        has_sufficient_evidence=tier in ["BUY_NOW", "HIGH_POTENTIAL"],
    )


# =============================================================================
# PHASE 6: TOP 20 BUYING LIKELIHOOD REPORT
# =============================================================================

@dataclass
class BuyingLikelihoodRanking:
    """Full ranking entry for a company."""
    rank: int
    record_id: str
    company: str
    buying_tier: str
    buying_score: int
    score_percentage: float
    why_this_company: str
    why_now: str
    supporting_evidence: List[str]
    missing_evidence: List[str]
    next_action: str
    confidence: float
    
    # Additional context
    contract_value: Optional[float]
    dod_exposure: bool
    decision_maker: Optional[str]
    contact_email: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "record_id": self.record_id,
            "company": self.company,
            "buying_tier": self.buying_tier,
            "buying_score": self.buying_score,
            "score_percentage": round(self.score_percentage, 1),
            "why_this_company": self.why_this_company,
            "why_now": self.why_now,
            "supporting_evidence": self.supporting_evidence,
            "missing_evidence": self.missing_evidence,
            "next_action": self.next_action,
            "confidence": round(self.confidence, 2),
            "contract_value": self.contract_value,
            "dod_exposure": self.dod_exposure,
            "decision_maker": self.decision_maker,
            "contact_email": self.contact_email,
        }


def generate_buying_likelihood_report(limit: int = 20) -> Dict[str, Any]:
    """
    PHASE 6: Generate top buying likelihood report.
    
    NO OUTREACH. NO EMAILS. EVIDENCE ONLY.
    """
    records = get_all_intelligence_records()
    max_score = sum(s["weight"] for s in BUYING_SIGNALS.values())
    
    rankings: List[BuyingLikelihoodRanking] = []
    
    tier_counts = {
        "BUY_NOW": 0,
        "HIGH_POTENTIAL": 0,
        "MEDIUM_POTENTIAL": 0,
        "LOW_POTENTIAL": 0,
        "INSUFFICIENT_EVIDENCE": 0,
    }
    
    for record in records:
        score, evidence_list = compute_buying_likelihood_score(record)
        tier = classify_buying_tier(score, evidence_list, record)
        explanation = generate_explanation(record, score, evidence_list, tier.value)
        
        tier_counts[tier.value] += 1
        
        # Extract context fields
        contract_value = record.contract_value.value if record.contract_value.state == SignalState.KNOWN else None
        dod_exposure = record.dod_exposure.value if record.dod_exposure.state == SignalState.KNOWN else False
        decision_maker = record.decision_maker_name.value if record.decision_maker_name.state == SignalState.KNOWN else None
        contact_email = record.contact_email.value if record.contact_email.state == SignalState.KNOWN else None
        
        ranking = BuyingLikelihoodRanking(
            rank=0,  # Will be set after sorting
            record_id=record.record_id,
            company=record.company_name.value or "Unknown",
            buying_tier=tier.value,
            buying_score=score,
            score_percentage=(score / max_score * 100) if max_score > 0 else 0,
            why_this_company=explanation.why_this_company,
            why_now=explanation.why_now,
            supporting_evidence=explanation.supporting_evidence,
            missing_evidence=explanation.missing_evidence,
            next_action=explanation.next_action,
            confidence=explanation.confidence,
            contract_value=contract_value,
            dod_exposure=dod_exposure,
            decision_maker=decision_maker,
            contact_email=contact_email,
        )
        rankings.append(ranking)
    
    # Sort by: tier priority, then score
    tier_priority = {
        "BUY_NOW": 0,
        "HIGH_POTENTIAL": 1,
        "MEDIUM_POTENTIAL": 2,
        "LOW_POTENTIAL": 3,
        "INSUFFICIENT_EVIDENCE": 4,
    }
    
    rankings.sort(key=lambda r: (tier_priority.get(r.buying_tier, 5), -r.buying_score))
    
    # Assign ranks
    for i, r in enumerate(rankings, 1):
        r.rank = i
    
    # Get top prospect for organism answers
    top_prospect = rankings[0].to_dict() if rankings else None
    organism_answers = answer_organism_questions(top_prospect)
    
    return {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_records": len(records),
        "max_possible_score": max_score,
        "tier_distribution": tier_counts,
        "top_prospects": [r.to_dict() for r in rankings[:limit]],
        "organism_answers": {
            "question_1": "Which company is most likely to become a customer?",
            "answer_1": organism_answers.most_likely_customer,
            "question_2": "Why?",
            "answer_2": organism_answers.why,
            "question_3": "Why now?",
            "answer_3": organism_answers.why_now,
            "question_4": "What evidence supports that?",
            "answer_4": organism_answers.supporting_evidence,
            "question_5": "What evidence is still missing?",
            "answer_5": organism_answers.missing_evidence,
            "question_6": "What should happen next?",
            "answer_6": organism_answers.next_action,
            "has_sufficient_evidence": organism_answers.has_sufficient_evidence,
        },
    }


# =============================================================================
# PHASE 7: ORGANISM VALIDATION
# =============================================================================

def validate_organism_buying_intelligence() -> Dict[str, Any]:
    """
    PHASE 7: Validate organism can answer buying questions with evidence.
    
    Returns validation report.
    """
    report = generate_buying_likelihood_report(limit=1)
    
    organism = report.get("organism_answers", {})
    tiers = report.get("tier_distribution", {})
    
    # Check if organism can answer
    can_answer = bool(organism.get("answer_1"))
    has_evidence = len(organism.get("answer_4", [])) > 0
    has_explanation = bool(organism.get("answer_2"))
    has_next_action = bool(organism.get("answer_6"))
    
    validation_passed = can_answer and has_explanation and has_next_action
    
    return {
        "ok": True,
        "validation_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "validation_passed": validation_passed,
        "checks": {
            "can_identify_prospect": can_answer,
            "has_supporting_evidence": has_evidence,
            "has_explanation": has_explanation,
            "has_next_action": has_next_action,
        },
        "current_best_prospect": organism.get("answer_1"),
        "highest_buying_tier": next(
            (t for t in ["BUY_NOW", "HIGH_POTENTIAL", "MEDIUM_POTENTIAL", "LOW_POTENTIAL", "INSUFFICIENT_EVIDENCE"]
             if tiers.get(t, 0) > 0),
            "NONE"
        ),
        "tier_distribution": tiers,
        "total_records": report.get("total_records", 0),
        "organism_answers": organism,
    }

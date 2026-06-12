"""PATCH 13A-21: Compliance Trigger Intelligence Engine.

Determines what specific compliance trigger is likely creating urgency for each company.

NO OUTREACH. NO EMAILS. NO AUTO-SEND. NO MARKETING.
EVIDENCE ONLY.

The organism must answer:
"What compliance event or obligation makes this company worth contacting?"
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
)
from .buying_likelihood import (
    BuyingTier,
    classify_buying_tier,
    compute_buying_likelihood_score,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PHASE 1: TRIGGER SIGNAL INVENTORY
# =============================================================================

TRIGGER_SIGNALS = {
    "dod_exposure": {
        "description": "DoD contract exposure indicates CMMC/DFARS requirements",
        "trigger_types": ["CMMC_PRESSURE", "DFARS_PRESSURE", "DOD_SUPPLIER_PRESSURE"],
        "weight": 25,
    },
    "cmmc_likelihood": {
        "description": "High CMMC likelihood from DoD contract analysis",
        "trigger_types": ["CMMC_PRESSURE"],
        "weight": 20,
    },
    "dfars_likelihood": {
        "description": "High DFARS likelihood from contract clauses",
        "trigger_types": ["DFARS_PRESSURE"],
        "weight": 20,
    },
    "award_recency": {
        "description": "Recent awards create immediate compliance pressure",
        "trigger_types": ["RECENT_AWARD_PRESSURE"],
        "weight": 15,
    },
    "agency_mix": {
        "description": "Agency mix indicates compliance burden type",
        "trigger_types": ["DOD_SUPPLIER_PRESSURE"],
        "weight": 10,
    },
    "contract_value": {
        "description": "High contract value increases compliance scrutiny",
        "trigger_types": ["DOCUMENTATION_BURDEN"],
        "weight": 10,
    },
    "contract_count": {
        "description": "Multiple contracts increase documentation burden",
        "trigger_types": ["DOCUMENTATION_BURDEN"],
        "weight": 8,
    },
    "manufacturing_exposure": {
        "description": "Manufacturing supply chain compliance requirements",
        "trigger_types": ["MANUFACTURING_SUPPLY_CHAIN_PRESSURE"],
        "weight": 12,
    },
    "aerospace_exposure": {
        "description": "Aerospace/defense industry compliance requirements",
        "trigger_types": ["AEROSPACE_DEFENSE_PRESSURE"],
        "weight": 12,
    },
    "naics": {
        "description": "NAICS code indicates industry compliance requirements",
        "trigger_types": ["MANUFACTURING_SUPPLY_CHAIN_PRESSURE", "AEROSPACE_DEFENSE_PRESSURE"],
        "weight": 8,
    },
}


def get_trigger_signal_inventory() -> Dict[str, Any]:
    """Return complete trigger signal inventory."""
    available = []
    missing = []
    
    for signal_name, config in TRIGGER_SIGNALS.items():
        available.append({
            "signal": signal_name,
            "description": config["description"],
            "trigger_types": config["trigger_types"],
            "weight": config["weight"],
        })
    
    return {
        "available_signals": available,
        "missing_signals": missing,
        "total_available": len(available),
        "max_possible_weight": sum(s["weight"] for s in TRIGGER_SIGNALS.values()),
    }


# =============================================================================
# PHASE 2: COMPLIANCE TRIGGER MODEL
# =============================================================================

class ComplianceTriggerType(str, Enum):
    """Evidence-backed compliance trigger categories."""
    CMMC_PRESSURE = "CMMC_PRESSURE"  # CMMC certification requirements
    DFARS_PRESSURE = "DFARS_PRESSURE"  # DFARS clause compliance
    DOD_SUPPLIER_PRESSURE = "DOD_SUPPLIER_PRESSURE"  # DoD supply chain requirements
    RECENT_AWARD_PRESSURE = "RECENT_AWARD_PRESSURE"  # New award compliance deadlines
    MANUFACTURING_SUPPLY_CHAIN_PRESSURE = "MANUFACTURING_SUPPLY_CHAIN_PRESSURE"  # Manufacturing compliance
    AEROSPACE_DEFENSE_PRESSURE = "AEROSPACE_DEFENSE_PRESSURE"  # Aerospace/defense standards
    DOCUMENTATION_BURDEN = "DOCUMENTATION_BURDEN"  # Multiple contracts documentation
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # Not enough data to determine


TRIGGER_REQUIREMENTS = {
    ComplianceTriggerType.CMMC_PRESSURE: {
        "required": ["dod_exposure", "cmmc_likelihood"],
        "any_of": [],
        "min_score": 35,
        "description": "CMMC certification required for DoD contracts",
        "conversation_topic": "CMMC Level 1/2 readiness and documentation requirements",
    },
    ComplianceTriggerType.DFARS_PRESSURE: {
        "required": ["dod_exposure", "dfars_likelihood"],
        "any_of": [],
        "min_score": 35,
        "description": "DFARS clause compliance required",
        "conversation_topic": "DFARS 7012/7019/7020 compliance documentation",
    },
    ComplianceTriggerType.DOD_SUPPLIER_PRESSURE: {
        "required": ["dod_exposure"],
        "any_of": ["agency_mix"],
        "min_score": 25,
        "description": "DoD supply chain compliance requirements",
        "conversation_topic": "DoD supplier compliance requirements and flow-down clauses",
    },
    ComplianceTriggerType.RECENT_AWARD_PRESSURE: {
        "required": ["award_recency"],
        "any_of": ["contract_value"],
        "min_score": 15,
        "description": "Recent award creates immediate compliance deadlines",
        "conversation_topic": "New contract compliance setup and documentation requirements",
    },
    ComplianceTriggerType.MANUFACTURING_SUPPLY_CHAIN_PRESSURE: {
        "required": ["manufacturing_exposure"],
        "any_of": ["naics"],
        "min_score": 12,
        "description": "Manufacturing supply chain compliance standards",
        "conversation_topic": "AS9100, ITAR, export control documentation",
    },
    ComplianceTriggerType.AEROSPACE_DEFENSE_PRESSURE: {
        "required": ["aerospace_exposure"],
        "any_of": ["naics"],
        "min_score": 12,
        "description": "Aerospace/defense industry compliance standards",
        "conversation_topic": "AS9100, NADCAP, quality management documentation",
    },
    ComplianceTriggerType.DOCUMENTATION_BURDEN: {
        "required": [],
        "any_of": ["contract_count", "contract_value"],
        "min_score": 10,
        "description": "Multiple contracts create documentation burden",
        "conversation_topic": "Compliance documentation organization and management",
    },
}


# =============================================================================
# PHASE 3: TRIGGER ASSESSMENT
# =============================================================================

@dataclass
class TriggerEvidence:
    """Evidence for a single trigger signal."""
    signal_name: str
    value: Any
    state: str
    weight: int
    is_present: bool
    explanation: str


@dataclass
class ComplianceTriggerResult:
    """Complete compliance trigger assessment for a company."""
    trigger_type: ComplianceTriggerType
    trigger_score: int
    trigger_confidence: float
    supporting_evidence: List[str]
    missing_evidence: List[str]
    recommended_conversation: str
    explanation: str


def evaluate_trigger_signal(
    record: CustomerIntelligenceRecord,
    signal_name: str,
) -> TriggerEvidence:
    """Evaluate a single trigger signal for a record."""
    config = TRIGGER_SIGNALS.get(signal_name, {})
    weight = config.get("weight", 0)
    
    value = None
    state = SignalState.UNKNOWN
    is_present = False
    explanation = ""
    
    if signal_name == "dod_exposure":
        if record.dod_exposure.state == SignalState.KNOWN:
            value = record.dod_exposure.value
            state = SignalState.KNOWN
            is_present = bool(value)
            explanation = "DoD contract exposure confirmed" if is_present else "No DoD exposure detected"
    
    elif signal_name == "cmmc_likelihood":
        if record.cmmc_likelihood.state == SignalState.KNOWN:
            value = record.cmmc_likelihood.value
            state = SignalState.KNOWN
            is_present = value is not None and value >= 0.5
            explanation = f"CMMC likelihood: {value:.0%}" if value else "CMMC likelihood unknown"
    
    elif signal_name == "dfars_likelihood":
        if record.dfars_likelihood.state == SignalState.KNOWN:
            value = record.dfars_likelihood.value
            state = SignalState.KNOWN
            is_present = value is not None and value >= 0.5
            explanation = f"DFARS likelihood: {value:.0%}" if value else "DFARS likelihood unknown"
    
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
                is_present = value <= 365
                explanation = f"Most recent award: {value} days ago"
    
    elif signal_name == "agency_mix":
        if record.agency_mix.state == SignalState.KNOWN:
            value = record.agency_mix.value
            state = SignalState.KNOWN
            is_present = bool(value)
            if isinstance(value, dict):
                dod_agencies = ["DOD", "ARMY", "NAVY", "AIR FORCE", "DEFENSE"]
                has_dod = any(k.upper() in str(v).upper() or k.upper() in dod_agencies 
                             for k, v in (value if isinstance(value, dict) else {}).items())
                is_present = has_dod
                explanation = f"Agency mix includes DoD" if has_dod else "Agency mix: non-DoD"
            else:
                explanation = f"Agency mix: {value}"
    
    elif signal_name == "contract_value":
        if record.contract_value.state == SignalState.KNOWN:
            value = record.contract_value.value
            state = SignalState.KNOWN
            is_present = value is not None and value >= 100000
            if value:
                explanation = f"Total contract value: ${value:,.0f}"
            else:
                explanation = "Contract value unknown"
    
    elif signal_name == "contract_count":
        if record.contract_count.state == SignalState.KNOWN:
            value = record.contract_count.value
            state = SignalState.KNOWN
            is_present = value is not None and value >= 2
            explanation = f"Contract count: {value}" if value else "Contract count unknown"
    
    elif signal_name == "manufacturing_exposure":
        if record.manufacturing_exposure.state == SignalState.KNOWN:
            value = record.manufacturing_exposure.value
            state = SignalState.KNOWN
            is_present = bool(value)
            explanation = "Manufacturing exposure confirmed" if is_present else "No manufacturing exposure"
    
    elif signal_name == "aerospace_exposure":
        if record.aerospace_exposure.state == SignalState.KNOWN:
            value = record.aerospace_exposure.value
            state = SignalState.KNOWN
            is_present = bool(value)
            explanation = "Aerospace exposure confirmed" if is_present else "No aerospace exposure"
    
    elif signal_name == "naics":
        if record.naics.state == SignalState.KNOWN:
            value = record.naics.value
            state = SignalState.KNOWN
            is_present = bool(value)
            explanation = f"NAICS: {value}" if value else "NAICS unknown"
    
    return TriggerEvidence(
        signal_name=signal_name,
        value=value,
        state=state.value if isinstance(state, SignalState) else str(state),
        weight=weight if is_present else 0,
        is_present=is_present,
        explanation=explanation,
    )


def compute_compliance_trigger(
    record: CustomerIntelligenceRecord,
) -> ComplianceTriggerResult:
    """
    Compute the most likely compliance trigger for a company.
    
    No synthetic pain. No fabricated urgency. Evidence only.
    """
    evidence_map: Dict[str, TriggerEvidence] = {}
    
    for signal_name in TRIGGER_SIGNALS:
        evidence_map[signal_name] = evaluate_trigger_signal(record, signal_name)
    
    best_trigger = ComplianceTriggerType.INSUFFICIENT_EVIDENCE
    best_score = 0
    best_confidence = 0.0
    supporting = []
    all_unknown = [s for s, ev in evidence_map.items() if not ev.is_present]
    missing = all_unknown[:5]
    conversation = "Gather more evidence before outreach"
    explanation = "Insufficient evidence to determine compliance trigger"
    
    for trigger_type, requirements in TRIGGER_REQUIREMENTS.items():
        if trigger_type == ComplianceTriggerType.INSUFFICIENT_EVIDENCE:
            continue
        
        required_met = []
        required_missing = []
        for req in requirements["required"]:
            if req in evidence_map and evidence_map[req].is_present:
                required_met.append(req)
            else:
                required_missing.append(req)
        
        any_of_met = []
        for any_req in requirements.get("any_of", []):
            if any_req in evidence_map and evidence_map[any_req].is_present:
                any_of_met.append(any_req)
        
        all_required_met = len(required_missing) == 0
        any_of_satisfied = len(requirements.get("any_of", [])) == 0 or len(any_of_met) > 0
        
        if all_required_met and any_of_satisfied:
            score = sum(evidence_map[s].weight for s in required_met)
            score += sum(evidence_map[s].weight for s in any_of_met)
            
            if score >= requirements["min_score"] and score > best_score:
                best_trigger = trigger_type
                best_score = score
                best_confidence = min(0.95, score / 100)
                supporting = [evidence_map[s].explanation for s in required_met + any_of_met 
                             if evidence_map[s].is_present]
                missing = [s for s in TRIGGER_SIGNALS if not evidence_map[s].is_present][:3]
                conversation = requirements["conversation_topic"]
                explanation = requirements["description"]
    
    return ComplianceTriggerResult(
        trigger_type=best_trigger,
        trigger_score=best_score,
        trigger_confidence=best_confidence,
        supporting_evidence=supporting,
        missing_evidence=missing,
        recommended_conversation=conversation,
        explanation=explanation,
    )


# =============================================================================
# PHASE 4: EXPLAINABILITY
# =============================================================================

@dataclass
class TriggerExplanation:
    """Human-readable explanation of compliance trigger."""
    what_trigger: str
    why: str
    why_now: str
    supporting_evidence: List[str]
    missing_evidence: List[str]
    what_to_discuss: str


def generate_trigger_explanation(
    record: CustomerIntelligenceRecord,
    trigger_result: ComplianceTriggerResult,
) -> TriggerExplanation:
    """Generate explainable trigger reasoning."""
    company_name = record.company_name.value or "Unknown Company"
    
    if trigger_result.trigger_type == ComplianceTriggerType.INSUFFICIENT_EVIDENCE:
        return TriggerExplanation(
            what_trigger="INSUFFICIENT_EVIDENCE",
            why=f"Not enough evidence to determine compliance trigger for {company_name}",
            why_now="Cannot determine timing without evidence",
            supporting_evidence=[],
            missing_evidence=trigger_result.missing_evidence,
            what_to_discuss="Need to gather more evidence before determining conversation topic",
        )
    
    why_statements = {
        ComplianceTriggerType.CMMC_PRESSURE: f"{company_name} has DoD contracts requiring CMMC certification",
        ComplianceTriggerType.DFARS_PRESSURE: f"{company_name} has contracts with DFARS clause requirements",
        ComplianceTriggerType.DOD_SUPPLIER_PRESSURE: f"{company_name} is a DoD supplier subject to flow-down requirements",
        ComplianceTriggerType.RECENT_AWARD_PRESSURE: f"{company_name} recently received a federal award with compliance deadlines",
        ComplianceTriggerType.MANUFACTURING_SUPPLY_CHAIN_PRESSURE: f"{company_name} is in manufacturing with supply chain compliance requirements",
        ComplianceTriggerType.AEROSPACE_DEFENSE_PRESSURE: f"{company_name} is in aerospace/defense with industry compliance standards",
        ComplianceTriggerType.DOCUMENTATION_BURDEN: f"{company_name} has multiple contracts creating documentation burden",
    }
    
    why_now_statements = {
        ComplianceTriggerType.CMMC_PRESSURE: "CMMC deadlines are approaching and DoD is increasing enforcement",
        ComplianceTriggerType.DFARS_PRESSURE: "DFARS compliance is required before contract performance can continue",
        ComplianceTriggerType.DOD_SUPPLIER_PRESSURE: "Prime contractors are flowing down requirements to suppliers",
        ComplianceTriggerType.RECENT_AWARD_PRESSURE: "New awards create immediate compliance setup requirements",
        ComplianceTriggerType.MANUFACTURING_SUPPLY_CHAIN_PRESSURE: "Supply chain compliance audits are increasing",
        ComplianceTriggerType.AEROSPACE_DEFENSE_PRESSURE: "Industry standards require current documentation",
        ComplianceTriggerType.DOCUMENTATION_BURDEN: "Multiple contracts require organized documentation",
    }
    
    return TriggerExplanation(
        what_trigger=trigger_result.trigger_type.value,
        why=why_statements.get(trigger_result.trigger_type, "Unknown trigger reason"),
        why_now=why_now_statements.get(trigger_result.trigger_type, "Unknown timing reason"),
        supporting_evidence=trigger_result.supporting_evidence,
        missing_evidence=trigger_result.missing_evidence,
        what_to_discuss=trigger_result.recommended_conversation,
    )


# =============================================================================
# PHASE 5: TOP TRIGGER REPORT
# =============================================================================

@dataclass
class TriggerRanking:
    """Ranked compliance trigger assessment."""
    rank: int
    company: str
    record_id: str
    trigger_type: str
    trigger_score: int
    trigger_confidence: float
    buying_tier: str
    contract_value: Optional[float]
    award_recency: Optional[int]
    evidence: List[str]
    missing_evidence: List[str]
    recommended_conversation: str


def generate_compliance_trigger_report(
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Generate top compliance trigger report.
    
    Returns companies ranked by trigger strength with full explainability.
    """
    records = get_all_intelligence_records()
    
    rankings: List[TriggerRanking] = []
    
    for record in records:
        trigger_result = compute_compliance_trigger(record)
        
        buying_score, _ = compute_buying_likelihood_score(record)
        buying_tier = classify_buying_tier(buying_score, [], record)
        
        contract_value = None
        if record.contract_value.state == SignalState.KNOWN:
            contract_value = record.contract_value.value
        
        award_recency = None
        if record.award_recency.state == SignalState.KNOWN:
            recency_val = record.award_recency.value
            if isinstance(recency_val, int):
                award_recency = recency_val
            elif isinstance(recency_val, str) and recency_val:
                try:
                    award_date = datetime.strptime(recency_val[:10], "%Y-%m-%d")
                    award_recency = (datetime.now() - award_date).days
                except (ValueError, TypeError):
                    pass
        
        rankings.append(TriggerRanking(
            rank=0,
            company=record.company_name.value or "Unknown",
            record_id=record.record_id,
            trigger_type=trigger_result.trigger_type.value,
            trigger_score=trigger_result.trigger_score,
            trigger_confidence=trigger_result.trigger_confidence,
            buying_tier=buying_tier.value,
            contract_value=contract_value,
            award_recency=award_recency,
            evidence=trigger_result.supporting_evidence,
            missing_evidence=trigger_result.missing_evidence,
            recommended_conversation=trigger_result.recommended_conversation,
        ))
    
    rankings.sort(key=lambda x: x.trigger_score, reverse=True)
    for i, r in enumerate(rankings[:limit]):
        r.rank = i + 1
    
    top_rankings = rankings[:limit]
    
    tier_distribution = {
        ComplianceTriggerType.CMMC_PRESSURE.value: 0,
        ComplianceTriggerType.DFARS_PRESSURE.value: 0,
        ComplianceTriggerType.DOD_SUPPLIER_PRESSURE.value: 0,
        ComplianceTriggerType.RECENT_AWARD_PRESSURE.value: 0,
        ComplianceTriggerType.MANUFACTURING_SUPPLY_CHAIN_PRESSURE.value: 0,
        ComplianceTriggerType.AEROSPACE_DEFENSE_PRESSURE.value: 0,
        ComplianceTriggerType.DOCUMENTATION_BURDEN.value: 0,
        ComplianceTriggerType.INSUFFICIENT_EVIDENCE.value: 0,
    }
    
    for r in rankings:
        if r.trigger_type in tier_distribution:
            tier_distribution[r.trigger_type] += 1
    
    return {
        "total_records": len(records),
        "trigger_distribution": tier_distribution,
        "top_trigger_companies": [
            {
                "rank": r.rank,
                "company": r.company,
                "record_id": r.record_id,
                "trigger_type": r.trigger_type,
                "trigger_score": r.trigger_score,
                "trigger_confidence": r.trigger_confidence,
                "buying_tier": r.buying_tier,
                "contract_value": r.contract_value,
                "award_recency": r.award_recency,
                "evidence": r.evidence,
                "missing_evidence": r.missing_evidence,
                "recommended_conversation": r.recommended_conversation,
            }
            for r in top_rankings
        ],
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# =============================================================================
# PHASE 6: VALIDATION ENDPOINT
# =============================================================================

def validate_compliance_trigger_intelligence() -> Dict[str, Any]:
    """
    Validate compliance trigger intelligence for all records.
    
    Returns validation status and best trigger company.
    """
    records = get_all_intelligence_records()
    
    if not records:
        return {
            "status": "NO_DATA",
            "best_trigger_company": None,
            "trigger_explanation": None,
            "supporting_evidence": [],
            "missing_evidence": [],
            "validation_passed": False,
            "reason": "No intelligence records available",
        }
    
    best_company = None
    best_trigger = None
    best_explanation = None
    best_score = 0
    
    for record in records:
        trigger_result = compute_compliance_trigger(record)
        
        if trigger_result.trigger_score > best_score:
            best_score = trigger_result.trigger_score
            best_company = record.company_name.value
            best_trigger = trigger_result
            best_explanation = generate_trigger_explanation(record, trigger_result)
    
    if not best_trigger or best_trigger.trigger_type == ComplianceTriggerType.INSUFFICIENT_EVIDENCE:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "best_trigger_company": best_company,
            "trigger_explanation": "No company has sufficient evidence for trigger assessment",
            "supporting_evidence": [],
            "missing_evidence": best_trigger.missing_evidence if best_trigger else [],
            "validation_passed": False,
            "reason": "Best trigger company still has insufficient evidence",
        }
    
    return {
        "status": "PASS",
        "best_trigger_company": best_company,
        "trigger_type": best_trigger.trigger_type.value,
        "trigger_score": best_trigger.trigger_score,
        "trigger_confidence": best_trigger.trigger_confidence,
        "trigger_explanation": {
            "what_trigger": best_explanation.what_trigger,
            "why": best_explanation.why,
            "why_now": best_explanation.why_now,
            "what_to_discuss": best_explanation.what_to_discuss,
        },
        "supporting_evidence": best_trigger.supporting_evidence,
        "missing_evidence": best_trigger.missing_evidence,
        "validation_passed": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# =============================================================================
# PHASE 7: ORGANISM METRICS
# =============================================================================

def compute_compliance_trigger_metrics() -> Dict[str, Any]:
    """
    Compute compliance trigger metrics for organism state.
    """
    records = get_all_intelligence_records()
    
    metrics = {
        "compliance_trigger_entities": 0,
        "cmmc_pressure_entities": 0,
        "dfars_pressure_entities": 0,
        "dod_supplier_pressure_entities": 0,
        "recent_award_pressure_entities": 0,
        "manufacturing_pressure_entities": 0,
        "aerospace_pressure_entities": 0,
        "documentation_burden_entities": 0,
        "insufficient_trigger_evidence_entities": 0,
    }
    
    for record in records:
        trigger_result = compute_compliance_trigger(record)
        
        if trigger_result.trigger_type != ComplianceTriggerType.INSUFFICIENT_EVIDENCE:
            metrics["compliance_trigger_entities"] += 1
        
        if trigger_result.trigger_type == ComplianceTriggerType.CMMC_PRESSURE:
            metrics["cmmc_pressure_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.DFARS_PRESSURE:
            metrics["dfars_pressure_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.DOD_SUPPLIER_PRESSURE:
            metrics["dod_supplier_pressure_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.RECENT_AWARD_PRESSURE:
            metrics["recent_award_pressure_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.MANUFACTURING_SUPPLY_CHAIN_PRESSURE:
            metrics["manufacturing_pressure_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.AEROSPACE_DEFENSE_PRESSURE:
            metrics["aerospace_pressure_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.DOCUMENTATION_BURDEN:
            metrics["documentation_burden_entities"] += 1
        elif trigger_result.trigger_type == ComplianceTriggerType.INSUFFICIENT_EVIDENCE:
            metrics["insufficient_trigger_evidence_entities"] += 1
    
    return metrics

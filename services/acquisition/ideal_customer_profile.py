"""PATCH 13A-12: Ideal Customer Profile (ICP) Definition.

The ICP defines who our ideal customer is based on observable evidence.
No assumptions. No fabricated signals. Only truth.

Tier 1: Highest priority - active DoD contractors with compliance burden
Tier 2: High priority - government contractors in relevant industries  
Tier 3: Standard priority - any federal award recipient
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ICPTier(str, Enum):
    TIER_1 = "TIER_1"  # Highest priority
    TIER_2 = "TIER_2"  # High priority
    TIER_3 = "TIER_3"  # Standard priority
    NO_MATCH = "NO_MATCH"  # Does not match ICP


class SignalState(str, Enum):
    """Signal state - UNKNOWN must never be interpreted as absence."""
    KNOWN = "KNOWN"      # We have evidence
    UNKNOWN = "UNKNOWN"  # We do not yet possess evidence


@dataclass
class EvidencedValue:
    """A value with its source and confidence.
    
    Every intelligence field must have:
    - value: The actual data
    - source: Where it came from
    - confidence: How certain we are (0.0-1.0)
    - state: KNOWN or UNKNOWN
    """
    value: Any
    source: str
    confidence: float
    state: SignalState = SignalState.KNOWN
    observed_utc: str = ""
    
    def __post_init__(self):
        if not self.observed_utc:
            self.observed_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "state": self.state.value,
            "observed_utc": self.observed_utc,
        }
    
    @classmethod
    def unknown(cls, field_name: str = "") -> "EvidencedValue":
        """Create an UNKNOWN value - we don't have evidence yet."""
        return cls(
            value=None,
            source="none",
            confidence=0.0,
            state=SignalState.UNKNOWN,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidencedValue":
        return cls(
            value=data.get("value"),
            source=data.get("source", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
            state=SignalState(data.get("state", "UNKNOWN")),
            observed_utc=data.get("observed_utc", ""),
        )


# =============================================================================
# IDEAL CUSTOMER PROFILE DEFINITION v1
# =============================================================================

ICP_V1 = {
    "version": "1.0",
    "created_utc": "2026-06-11T00:00:00Z",
    "description": "Ideal Customer Profile for compliance paperwork services",
    
    "tier_1": {
        "name": "Highest Priority",
        "description": "Active federal contractors with demonstrated compliance burden",
        "criteria": [
            {"field": "is_active_federal_contractor", "required": True},
            {"field": "dod_exposure", "required": True},
            {"field": "company_size", "values": ["small", "medium"], "required": True},
            {"field": "recent_award_activity", "required": True},
            {"field": "no_internal_compliance_department", "preferred": True},
            {"field": "evidence_of_compliance_burden", "preferred": True},
            {"field": "evidence_of_growth", "preferred": True},
        ],
        "minimum_required_criteria": 4,
    },
    
    "tier_2": {
        "name": "High Priority",
        "description": "Government contractors in relevant industries",
        "criteria": [
            {"field": "is_government_contractor", "required": True},
            {"field": "industry", "values": ["manufacturing", "aerospace", "defense", "technology"], "required": True},
        ],
        "minimum_required_criteria": 2,
    },
    
    "tier_3": {
        "name": "Standard Priority",
        "description": "Any federal award recipient",
        "criteria": [
            {"field": "is_federal_award_recipient", "required": True},
        ],
        "minimum_required_criteria": 1,
    },
}


def get_icp_definition() -> Dict[str, Any]:
    """Return the current ICP definition."""
    return ICP_V1.copy()


def evaluate_icp_match(intelligence: "CustomerIntelligenceRecord") -> Dict[str, Any]:
    """
    Evaluate how well a customer matches the ICP.
    
    Returns tier match and detailed breakdown.
    """
    result = {
        "tier": ICPTier.NO_MATCH.value,
        "tier_name": "No Match",
        "match_score": 0,
        "criteria_met": [],
        "criteria_missing": [],
        "criteria_unknown": [],
        "recommendation": "IGNORE",
    }
    
    # Check Tier 1 criteria
    tier_1_met = []
    tier_1_missing = []
    tier_1_unknown = []
    
    # Is active federal contractor
    if intelligence.contract_count.state == SignalState.UNKNOWN:
        tier_1_unknown.append("is_active_federal_contractor")
    elif intelligence.contract_count.value and intelligence.contract_count.value > 0:
        tier_1_met.append("is_active_federal_contractor")
    else:
        tier_1_missing.append("is_active_federal_contractor")
    
    # DoD exposure
    if intelligence.dod_exposure.state == SignalState.UNKNOWN:
        tier_1_unknown.append("dod_exposure")
    elif intelligence.dod_exposure.value:
        tier_1_met.append("dod_exposure")
    else:
        tier_1_missing.append("dod_exposure")
    
    # Company size (small/medium)
    if intelligence.company_size.state == SignalState.UNKNOWN:
        tier_1_unknown.append("company_size")
    elif intelligence.company_size.value in ("small", "medium"):
        tier_1_met.append("company_size")
    else:
        tier_1_missing.append("company_size")
    
    # Recent award activity
    if intelligence.award_recency.state == SignalState.UNKNOWN:
        tier_1_unknown.append("recent_award_activity")
    else:
        # award_recency can be int (days) or str (date like "2024-06-15")
        recency_val = intelligence.award_recency.value
        is_recent = False
        if isinstance(recency_val, int):
            is_recent = recency_val <= 365
        elif isinstance(recency_val, str) and recency_val:
            try:
                from datetime import datetime, timezone
                award_date = datetime.strptime(recency_val[:10], "%Y-%m-%d")
                days_ago = (datetime.now() - award_date).days
                is_recent = days_ago <= 365
            except (ValueError, TypeError):
                pass
        
        if is_recent:
            tier_1_met.append("recent_award_activity")
        else:
            tier_1_missing.append("recent_award_activity")
    
    # Check if Tier 1 match
    if len(tier_1_met) >= 4:
        result["tier"] = ICPTier.TIER_1.value
        result["tier_name"] = "Highest Priority"
        result["match_score"] = 90 + min(10, len(tier_1_met) - 4)
        result["criteria_met"] = tier_1_met
        result["criteria_missing"] = tier_1_missing
        result["criteria_unknown"] = tier_1_unknown
        result["recommendation"] = "HIGH PRIORITY"
        return result
    
    # Check Tier 2 criteria
    tier_2_met = []
    tier_2_missing = []
    tier_2_unknown = []
    
    # Is government contractor
    if intelligence.contract_count.state == SignalState.UNKNOWN:
        tier_2_unknown.append("is_government_contractor")
    elif intelligence.contract_count.value and intelligence.contract_count.value > 0:
        tier_2_met.append("is_government_contractor")
    else:
        tier_2_missing.append("is_government_contractor")
    
    # Industry match
    relevant_industries = {"manufacturing", "aerospace", "defense", "technology"}
    if intelligence.industry.state == SignalState.UNKNOWN:
        tier_2_unknown.append("industry")
    elif intelligence.industry.value and intelligence.industry.value.lower() in relevant_industries:
        tier_2_met.append("industry")
    else:
        # Check exposure fields
        exposures = [
            intelligence.manufacturing_exposure,
            intelligence.aerospace_exposure,
        ]
        if any(e.state == SignalState.KNOWN and e.value for e in exposures):
            tier_2_met.append("industry")
        else:
            tier_2_missing.append("industry")
    
    # Check if Tier 2 match
    if len(tier_2_met) >= 2:
        result["tier"] = ICPTier.TIER_2.value
        result["tier_name"] = "High Priority"
        result["match_score"] = 70 + min(20, len(tier_2_met) * 10)
        result["criteria_met"] = tier_1_met + tier_2_met
        result["criteria_missing"] = tier_1_missing + tier_2_missing
        result["criteria_unknown"] = tier_1_unknown + tier_2_unknown
        result["recommendation"] = "CONTACT"
        return result
    
    # Check Tier 3 criteria
    if intelligence.contract_count.state == SignalState.KNOWN and intelligence.contract_count.value:
        result["tier"] = ICPTier.TIER_3.value
        result["tier_name"] = "Standard Priority"
        result["match_score"] = 50
        result["criteria_met"] = ["is_federal_award_recipient"]
        result["criteria_missing"] = tier_1_missing + tier_2_missing
        result["criteria_unknown"] = tier_1_unknown + tier_2_unknown
        result["recommendation"] = "WATCH"
        return result
    
    # Check if too much unknown
    total_unknown = len(tier_1_unknown) + len(tier_2_unknown)
    if total_unknown >= 3:
        result["recommendation"] = "ENRICH"
        result["criteria_unknown"] = tier_1_unknown + tier_2_unknown
    
    return result


# =============================================================================
# CUSTOMER INTELLIGENCE RECORD
# =============================================================================

@dataclass
class CustomerIntelligenceRecord:
    """
    Complete intelligence record for a potential customer.
    
    Every field contains:
    - value: The actual data
    - source: Where it came from (USASpending, SAM.gov, manual, etc.)
    - confidence: How certain we are (0.0-1.0)
    - state: KNOWN or UNKNOWN
    
    UNKNOWN means "we do not yet possess evidence" - NOT absence.
    """
    
    # Identity
    company_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("company_name"))
    uei: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("uei"))
    
    # Classification
    naics: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("naics"))
    industry: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("industry"))
    company_size: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("company_size"))
    
    # Contract Intelligence
    contract_count: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contract_count"))
    contract_value: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contract_value"))
    award_recency: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("award_recency"))
    agency_mix: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("agency_mix"))
    
    # Compliance Exposure
    dod_exposure: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("dod_exposure"))
    manufacturing_exposure: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("manufacturing_exposure"))
    aerospace_exposure: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("aerospace_exposure"))
    cmmc_likelihood: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("cmmc_likelihood"))
    dfars_likelihood: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("dfars_likelihood"))
    
    # Contactability
    contact_email: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contact_email"))
    contact_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contact_name"))
    contact_phone: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contact_phone"))
    contact_title: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contact_title"))
    contact_source_url: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contact_source_url"))
    leadership_page_url: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("leadership_page_url"))
    website: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("website"))
    location: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("location"))
    
    # PATCH 13A-19: Decision Maker Intelligence
    decision_maker_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("decision_maker_name"))
    decision_maker_title: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("decision_maker_title"))
    decision_maker_source: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("decision_maker_source"))
    owner_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("owner_name"))
    president_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("president_name"))
    ceo_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("ceo_name"))
    founder_name: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("founder_name"))
    contracts_manager: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contracts_manager"))
    compliance_manager: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("compliance_manager"))
    quality_manager: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("quality_manager"))
    operations_manager: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("operations_manager"))
    leadership_count: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("leadership_count"))
    organization_type: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("organization_type"))
    
    # Derived Scores (computed from evidence)
    contactability_score: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("contactability_score"))
    ability_to_pay_score: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("ability_to_pay_score"))
    urgency_score: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("urgency_score"))
    confidence_score: EvidencedValue = field(default_factory=lambda: EvidencedValue.unknown("confidence_score"))
    
    # Metadata
    record_id: str = ""
    created_utc: str = ""
    updated_utc: str = ""
    source_lead_id: str = ""
    
    def __post_init__(self):
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not self.updated_utc:
            self.updated_utc = self.created_utc
    
    def compute_intelligence_completeness(self) -> int:
        """
        Compute intelligence completeness (0-100).
        
        Based on how many fields have KNOWN state with actual values.
        """
        fields = [
            # Identity (20 points)
            (self.company_name, 10),
            (self.uei, 10),
            # Classification (15 points)
            (self.naics, 5),
            (self.industry, 5),
            (self.company_size, 5),
            # Contract Intelligence (25 points)
            (self.contract_count, 5),
            (self.contract_value, 10),
            (self.award_recency, 5),
            (self.agency_mix, 5),
            # Compliance Exposure (20 points)
            (self.dod_exposure, 5),
            (self.manufacturing_exposure, 3),
            (self.aerospace_exposure, 3),
            (self.cmmc_likelihood, 5),
            (self.dfars_likelihood, 4),
            # Contactability (20 points)
            (self.contact_email, 8),
            (self.contact_name, 4),
            (self.website, 4),
            (self.location, 4),
        ]
        
        total = 0
        for evidenced_value, points in fields:
            if evidenced_value.state == SignalState.KNOWN and evidenced_value.value is not None:
                total += points
        
        return min(100, total)
    
    def compute_contactability(self) -> int:
        """Compute contactability score (0-100)."""
        score = 0
        
        if self.contact_email.state == SignalState.KNOWN and self.contact_email.value:
            email = str(self.contact_email.value).lower()
            if "@" in email:
                score += 40
                # Business email bonus
                if not any(x in email for x in ["gmail", "yahoo", "hotmail", "outlook"]):
                    score += 20
        
        if self.contact_name.state == SignalState.KNOWN and self.contact_name.value:
            score += 15
        
        if self.website.state == SignalState.KNOWN and self.website.value:
            score += 15
        
        if self.location.state == SignalState.KNOWN and self.location.value:
            score += 10
        
        return min(100, score)
    
    def compute_ability_to_pay(self) -> int:
        """Compute ability to pay score (0-100) based on contract evidence."""
        if self.contract_value.state == SignalState.UNKNOWN:
            return 0  # Unknown, not zero - return 0 to indicate unknown
        
        value = self.contract_value.value or 0
        
        if value >= 10_000_000:
            return 95
        elif value >= 1_000_000:
            return 80
        elif value >= 500_000:
            return 65
        elif value >= 100_000:
            return 50
        elif value > 0:
            return 35
        return 0
    
    def get_icp_match(self) -> Dict[str, Any]:
        """Evaluate ICP match for this record."""
        return evaluate_icp_match(self)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "company_name": self.company_name.to_dict(),
            "uei": self.uei.to_dict(),
            "naics": self.naics.to_dict(),
            "industry": self.industry.to_dict(),
            "company_size": self.company_size.to_dict(),
            "contract_count": self.contract_count.to_dict(),
            "contract_value": self.contract_value.to_dict(),
            "award_recency": self.award_recency.to_dict(),
            "agency_mix": self.agency_mix.to_dict(),
            "dod_exposure": self.dod_exposure.to_dict(),
            "manufacturing_exposure": self.manufacturing_exposure.to_dict(),
            "aerospace_exposure": self.aerospace_exposure.to_dict(),
            "cmmc_likelihood": self.cmmc_likelihood.to_dict(),
            "dfars_likelihood": self.dfars_likelihood.to_dict(),
            "contact_email": self.contact_email.to_dict(),
            "contact_name": self.contact_name.to_dict(),
            "contact_phone": self.contact_phone.to_dict(),
            "contact_title": self.contact_title.to_dict(),
            "contact_source_url": self.contact_source_url.to_dict(),
            "leadership_page_url": self.leadership_page_url.to_dict(),
            "website": self.website.to_dict(),
            "location": self.location.to_dict(),
            # PATCH 13A-19: Decision Maker fields
            "decision_maker_name": self.decision_maker_name.to_dict(),
            "decision_maker_title": self.decision_maker_title.to_dict(),
            "decision_maker_source": self.decision_maker_source.to_dict(),
            "owner_name": self.owner_name.to_dict(),
            "president_name": self.president_name.to_dict(),
            "ceo_name": self.ceo_name.to_dict(),
            "founder_name": self.founder_name.to_dict(),
            "contracts_manager": self.contracts_manager.to_dict(),
            "compliance_manager": self.compliance_manager.to_dict(),
            "quality_manager": self.quality_manager.to_dict(),
            "operations_manager": self.operations_manager.to_dict(),
            "leadership_count": self.leadership_count.to_dict(),
            "organization_type": self.organization_type.to_dict(),
            # Derived scores
            "contactability_score": self.contactability_score.to_dict(),
            "ability_to_pay_score": self.ability_to_pay_score.to_dict(),
            "urgency_score": self.urgency_score.to_dict(),
            "confidence_score": self.confidence_score.to_dict(),
            "record_id": self.record_id,
            "created_utc": self.created_utc,
            "updated_utc": self.updated_utc,
            "source_lead_id": self.source_lead_id,
            "intelligence_completeness": self.compute_intelligence_completeness(),
            "icp_match": self.get_icp_match(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomerIntelligenceRecord":
        """Create from dictionary."""
        def get_ev(key: str) -> EvidencedValue:
            v = data.get(key)
            if isinstance(v, dict):
                return EvidencedValue.from_dict(v)
            return EvidencedValue.unknown(key)
        
        return cls(
            company_name=get_ev("company_name"),
            uei=get_ev("uei"),
            naics=get_ev("naics"),
            industry=get_ev("industry"),
            company_size=get_ev("company_size"),
            contract_count=get_ev("contract_count"),
            contract_value=get_ev("contract_value"),
            award_recency=get_ev("award_recency"),
            agency_mix=get_ev("agency_mix"),
            dod_exposure=get_ev("dod_exposure"),
            manufacturing_exposure=get_ev("manufacturing_exposure"),
            aerospace_exposure=get_ev("aerospace_exposure"),
            cmmc_likelihood=get_ev("cmmc_likelihood"),
            dfars_likelihood=get_ev("dfars_likelihood"),
            contact_email=get_ev("contact_email"),
            contact_name=get_ev("contact_name"),
            contact_phone=get_ev("contact_phone"),
            contact_title=get_ev("contact_title"),
            contact_source_url=get_ev("contact_source_url"),
            leadership_page_url=get_ev("leadership_page_url"),
            website=get_ev("website"),
            location=get_ev("location"),
            # PATCH 13A-19: Decision Maker fields
            decision_maker_name=get_ev("decision_maker_name"),
            decision_maker_title=get_ev("decision_maker_title"),
            decision_maker_source=get_ev("decision_maker_source"),
            owner_name=get_ev("owner_name"),
            president_name=get_ev("president_name"),
            ceo_name=get_ev("ceo_name"),
            founder_name=get_ev("founder_name"),
            contracts_manager=get_ev("contracts_manager"),
            compliance_manager=get_ev("compliance_manager"),
            quality_manager=get_ev("quality_manager"),
            operations_manager=get_ev("operations_manager"),
            leadership_count=get_ev("leadership_count"),
            organization_type=get_ev("organization_type"),
            # Derived scores
            contactability_score=get_ev("contactability_score"),
            ability_to_pay_score=get_ev("ability_to_pay_score"),
            urgency_score=get_ev("urgency_score"),
            confidence_score=get_ev("confidence_score"),
            record_id=data.get("record_id", ""),
            created_utc=data.get("created_utc", ""),
            updated_utc=data.get("updated_utc", ""),
            source_lead_id=data.get("source_lead_id", ""),
        )


def create_intelligence_from_discovery(
    company_name: str,
    uei: str = "",
    location: str = "",
    source: str = "usaspending_public_api",
    lead_id: str = "",
    website: str = "",
    contact_email: str = "",
    industry: str = "",
    notes: str = "",
    contract_value: Optional[float] = None,
    naics: str = "",
) -> CustomerIntelligenceRecord:
    """
    Create a minimal intelligence record from discovery data.
    
    Most fields will be UNKNOWN - this is honest, not a failure.
    """
    record = CustomerIntelligenceRecord()
    record.source_lead_id = lead_id
    
    # Set what we know
    if company_name:
        record.company_name = EvidencedValue(
            value=company_name,
            source=source,
            confidence=0.95,
            state=SignalState.KNOWN,
        )
    
    if uei:
        record.uei = EvidencedValue(
            value=uei,
            source=source,
            confidence=0.99,  # UEI is definitive
            state=SignalState.KNOWN,
        )
    
    if location:
        record.location = EvidencedValue(
            value=location,
            source=source,
            confidence=0.80,
            state=SignalState.KNOWN,
        )
    
    if website:
        record.website = EvidencedValue(
            value=website,
            source=source,
            confidence=0.90,
            state=SignalState.KNOWN,
        )
    
    if contact_email:
        record.contact_email = EvidencedValue(
            value=contact_email,
            source=source,
            confidence=0.85,
            state=SignalState.KNOWN,
        )
    
    if industry:
        record.industry = EvidencedValue(
            value=industry,
            source=source,
            confidence=0.75,
            state=SignalState.KNOWN,
        )
    
    if naics:
        record.naics = EvidencedValue(
            value=naics,
            source=source,
            confidence=0.95,
            state=SignalState.KNOWN,
        )
    
    # Contract count is at least 1 since they're in USASpending
    record.contract_count = EvidencedValue(
        value=1,  # Minimum - they have at least one award
        source=source,
        confidence=0.50,  # Low confidence on exact count
        state=SignalState.KNOWN,
    )
    
    if contract_value is not None:
        record.contract_value = EvidencedValue(
            value=contract_value,
            source=source,
            confidence=0.90,
            state=SignalState.KNOWN,
        )
    
    # Check for DoD exposure from notes or industry
    notes_lower = (notes or "").lower()
    industry_lower = (industry or "").lower()
    if any(kw in notes_lower or kw in industry_lower for kw in ["dod", "defense", "military", "army", "navy", "air force"]):
        record.dod_exposure = EvidencedValue(
            value=True,
            source=source,
            confidence=0.70,
            state=SignalState.KNOWN,
        )
    
    # Update computed scores
    record.contactability_score = EvidencedValue(
        value=record.compute_contactability(),
        source="computed",
        confidence=0.90,
        state=SignalState.KNOWN,
    )
    
    return record


# =============================================================================
# STORAGE
# =============================================================================

def _intelligence_dir() -> Path:
    from ..config import DATA
    d = DATA / "acquisition" / "intelligence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_intelligence_record(record: CustomerIntelligenceRecord) -> None:
    """Save intelligence record to disk."""
    if not record.record_id:
        import uuid
        # Use timestamp + uuid suffix to ensure uniqueness even within same second
        ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        suffix = uuid.uuid4().hex[:6]
        record.record_id = f"INT-{ts}-{suffix}"
    
    record.updated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    path = _intelligence_dir() / f"{record.record_id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")


def load_intelligence_record(record_id: str) -> Optional[CustomerIntelligenceRecord]:
    """Load intelligence record from disk."""
    path = _intelligence_dir() / f"{record_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CustomerIntelligenceRecord.from_dict(data)
    except Exception:
        return None


def list_intelligence_records() -> List[str]:
    """List all intelligence record IDs."""
    d = _intelligence_dir()
    return [p.stem for p in d.glob("INT-*.json")]


def get_all_intelligence_records() -> List[CustomerIntelligenceRecord]:
    """Load all intelligence records."""
    records = []
    for record_id in list_intelligence_records():
        record = load_intelligence_record(record_id)
        if record:
            records.append(record)
    return records


def get_intelligence_summary() -> Dict[str, Any]:
    """Get summary statistics for all intelligence records."""
    records = get_all_intelligence_records()
    
    summary = {
        "total_records": len(records),
        "by_icp_tier": {
            "TIER_1": 0,
            "TIER_2": 0,
            "TIER_3": 0,
            "NO_MATCH": 0,
        },
        "by_recommendation": {
            "HIGH PRIORITY": 0,
            "CONTACT": 0,
            "WATCH": 0,
            "ENRICH": 0,
            "IGNORE": 0,
        },
        "intelligence_completeness": {
            "0-20": 0,
            "21-40": 0,
            "41-60": 0,
            "61-80": 0,
            "81-100": 0,
        },
        "contactable": 0,
        "average_completeness": 0,
        # PATCH 13A-18: Contact intelligence metrics
        "contact_metrics": {
            "contactable_entities": 0,
            "decision_maker_entities": 0,
            "email_known_entities": 0,
            "phone_known_entities": 0,
            "leadership_known_entities": 0,
            "contact_ready_entities": 0,
        },
        # PATCH 13A-19: Decision maker intelligence metrics
        "decision_maker_metrics": {
            "decision_maker_entities": 0,
            "leadership_entities": 0,
            "procurement_relevant_entities": 0,
            "decision_maker_ready_entities": 0,
        },
    }
    
    total_completeness = 0
    
    for record in records:
        # ICP tier
        icp = record.get_icp_match()
        tier = icp.get("tier", "NO_MATCH")
        summary["by_icp_tier"][tier] = summary["by_icp_tier"].get(tier, 0) + 1
        
        # Recommendation
        rec = icp.get("recommendation", "IGNORE")
        summary["by_recommendation"][rec] = summary["by_recommendation"].get(rec, 0) + 1
        
        # Completeness
        completeness = record.compute_intelligence_completeness()
        total_completeness += completeness
        
        if completeness <= 20:
            summary["intelligence_completeness"]["0-20"] += 1
        elif completeness <= 40:
            summary["intelligence_completeness"]["21-40"] += 1
        elif completeness <= 60:
            summary["intelligence_completeness"]["41-60"] += 1
        elif completeness <= 80:
            summary["intelligence_completeness"]["61-80"] += 1
        else:
            summary["intelligence_completeness"]["81-100"] += 1
        
        # Contactable
        if record.compute_contactability() >= 40:
            summary["contactable"] += 1
        
        # PATCH 13A-18: Contact metrics
        email_known = record.contact_email.state == SignalState.KNOWN and record.contact_email.value
        phone_known = record.contact_phone.state == SignalState.KNOWN and record.contact_phone.value
        name_known = record.contact_name.state == SignalState.KNOWN and record.contact_name.value
        title_known = record.contact_title.state == SignalState.KNOWN and record.contact_title.value
        leadership_known = record.leadership_page_url.state == SignalState.KNOWN and record.leadership_page_url.value
        
        if email_known:
            summary["contact_metrics"]["email_known_entities"] += 1
        
        if phone_known:
            summary["contact_metrics"]["phone_known_entities"] += 1
        
        if email_known and (name_known or title_known):
            summary["contact_metrics"]["contactable_entities"] += 1
            
            # CONTACT_READY: high confidence
            if record.contact_email.confidence >= 0.70:
                summary["contact_metrics"]["contact_ready_entities"] += 1
        
        if name_known and title_known:
            summary["contact_metrics"]["decision_maker_entities"] += 1
        
        if leadership_known:
            summary["contact_metrics"]["leadership_known_entities"] += 1
        
        # PATCH 13A-19: Decision maker metrics
        dm_name_known = record.decision_maker_name.state == SignalState.KNOWN and record.decision_maker_name.value
        dm_title_known = record.decision_maker_title.state == SignalState.KNOWN and record.decision_maker_title.value
        leadership_count_known = record.leadership_count.state == SignalState.KNOWN and record.leadership_count.value
        
        if dm_name_known:
            summary["decision_maker_metrics"]["decision_maker_entities"] += 1
        
        if leadership_count_known:
            summary["decision_maker_metrics"]["leadership_entities"] += 1
        
        # Procurement relevance
        if dm_title_known:
            title_lower = (record.decision_maker_title.value or "").lower()
            has_tier_1 = any(t in title_lower for t in ["president", "owner", "ceo", "founder", "managing member"])
            has_tier_2 = any(t in title_lower for t in ["contracts manager", "compliance manager", "quality manager", "operations manager"])
            
            if has_tier_1 or has_tier_2:
                summary["decision_maker_metrics"]["procurement_relevant_entities"] += 1
        
        # DECISION_MAKER_READY
        if dm_name_known and dm_title_known and email_known:
            dm_confidence = record.decision_maker_name.confidence
            email_confidence = record.contact_email.confidence
            avg_confidence = (dm_confidence + email_confidence) / 2
            if avg_confidence >= 0.70:
                summary["decision_maker_metrics"]["decision_maker_ready_entities"] += 1
    
    if records:
        summary["average_completeness"] = round(total_completeness / len(records), 1)
    
    return summary


def find_intelligence_by_company(company_name: str) -> Optional[CustomerIntelligenceRecord]:
    """Find an existing intelligence record by company name (case-insensitive)."""
    if not company_name:
        return None
    
    normalized = company_name.strip().lower()
    for record in get_all_intelligence_records():
        if record.company_name.value and record.company_name.value.strip().lower() == normalized:
            return record
    return None


def find_intelligence_by_lead_id(lead_id: str) -> Optional[CustomerIntelligenceRecord]:
    """Find an existing intelligence record by source lead ID."""
    if not lead_id:
        return None
    
    for record in get_all_intelligence_records():
        if record.source_lead_id == lead_id:
            return record
    return None


def create_or_update_intelligence(
    company_name: str,
    uei: str = "",
    location: str = "",
    source: str = "usaspending_public_api",
    lead_id: str = "",
    website: str = "",
    contact_email: str = "",
    industry: str = "",
    notes: str = "",
    contract_value: Optional[float] = None,
    naics: str = "",
) -> tuple[CustomerIntelligenceRecord, bool]:
    """
    Create or update an intelligence record.
    
    Returns (record, is_new) tuple.
    Deduplicates by company name (case-insensitive).
    """
    # Check for existing record by lead_id first, then by company name
    existing = find_intelligence_by_lead_id(lead_id) if lead_id else None
    if not existing:
        existing = find_intelligence_by_company(company_name)
    
    if existing:
        # Update existing record with any new information
        if website and existing.website.state == SignalState.UNKNOWN:
            existing.website = EvidencedValue(
                value=website,
                source=source,
                confidence=0.90,
                state=SignalState.KNOWN,
            )
        if contact_email and existing.contact_email.state == SignalState.UNKNOWN:
            existing.contact_email = EvidencedValue(
                value=contact_email,
                source=source,
                confidence=0.85,
                state=SignalState.KNOWN,
            )
        if location and existing.location.state == SignalState.UNKNOWN:
            existing.location = EvidencedValue(
                value=location,
                source=source,
                confidence=0.80,
                state=SignalState.KNOWN,
            )
        if industry and existing.industry.state == SignalState.UNKNOWN:
            existing.industry = EvidencedValue(
                value=industry,
                source=source,
                confidence=0.75,
                state=SignalState.KNOWN,
            )
        if uei and existing.uei.state == SignalState.UNKNOWN:
            existing.uei = EvidencedValue(
                value=uei,
                source=source,
                confidence=0.99,
                state=SignalState.KNOWN,
            )
        if naics and existing.naics.state == SignalState.UNKNOWN:
            existing.naics = EvidencedValue(
                value=naics,
                source=source,
                confidence=0.95,
                state=SignalState.KNOWN,
            )
        
        # Update contactability
        existing.contactability_score = EvidencedValue(
            value=existing.compute_contactability(),
            source="computed",
            confidence=0.90,
            state=SignalState.KNOWN,
        )
        
        save_intelligence_record(existing)
        return existing, False
    
    # Create new record
    record = create_intelligence_from_discovery(
        company_name=company_name,
        uei=uei,
        location=location,
        source=source,
        lead_id=lead_id,
        website=website,
        contact_email=contact_email,
        industry=industry,
        notes=notes,
        contract_value=contract_value,
        naics=naics,
    )
    save_intelligence_record(record)
    return record, True

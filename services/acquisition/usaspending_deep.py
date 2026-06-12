"""PATCH 13A-17: USASpending Deep Enrichment Engine.

Increase Customer Intelligence completeness from ~25% to ~55% using public federal data only.

NO OUTREACH. NO EMAIL DISCOVERY. NO CONTACT SCRAPING. NO MARKETING. NO AUTO-SEND.
Evidence only.

USASpending API Endpoints Used:
- /api/v2/autocomplete/recipient/ - Get UEI by company name
- /api/v2/search/spending_by_award/ - Get award details
- /api/v2/recipient/{hash}/ - Get recipient profile (when available)
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .ideal_customer_profile import (
    CustomerIntelligenceRecord,
    EvidencedValue,
    SignalState,
    save_intelligence_record,
    load_intelligence_record,
    get_all_intelligence_records,
    evaluate_icp_match,
)
from .enrichment import (
    compute_enrichment_score,
    compute_recommendation,
    Recommendation,
)

logger = logging.getLogger(__name__)

USER_AGENT = "KeepYourContracts-DeepEnrichment/1.0 (+https://compliance.keepyourcontracts.com; lawful-evidence-collection)"

# USASpending API endpoints
USASPENDING_BASE = "https://api.usaspending.gov"
USASPENDING_AUTOCOMPLETE = f"{USASPENDING_BASE}/api/v2/autocomplete/recipient/"
USASPENDING_AWARD_SEARCH = f"{USASPENDING_BASE}/api/v2/search/spending_by_award/"
USASPENDING_RECIPIENT_PROFILE = f"{USASPENDING_BASE}/api/v2/recipient/"

# DoD agency identifiers
DOD_AGENCIES = {
    "department of defense",
    "dept of defense", 
    "dod",
    "army",
    "navy",
    "air force",
    "marine corps",
    "defense logistics agency",
    "defense contract management agency",
    "defense information systems agency",
    "missile defense agency",
    "defense threat reduction agency",
}

# Manufacturing NAICS codes (31-33)
MANUFACTURING_NAICS_PREFIXES = ["31", "32", "33"]

# Aerospace NAICS codes
AEROSPACE_NAICS_CODES = ["336411", "336412", "336413", "336414", "336415", "336419", "3364"]

# Defense-related NAICS codes
DEFENSE_NAICS_CODES = ["336411", "336992", "332994", "332993", "336414"]


# =============================================================================
# API REQUEST HELPER
# =============================================================================

def _api_request(
    url: str,
    payload: Optional[dict] = None,
    method: str = "POST",
    timeout: int = 30,
) -> Optional[dict]:
    """Make a request to USASpending API."""
    try:
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method=method,
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning("USASpending API request failed: %s - %s", url, e)
        return None


# =============================================================================
# PHASE 2: UEI ACQUISITION ENGINE
# =============================================================================

@dataclass
class UEIResult:
    """Result of UEI acquisition."""
    uei: Optional[str] = None
    recipient_name: str = ""
    recipient_id: str = ""
    location: str = ""
    confidence: float = 0.0
    source: str = "USASpending Autocomplete"
    
    def is_found(self) -> bool:
        return self.uei is not None and len(self.uei) > 0


def acquire_uei(company_name: str) -> UEIResult:
    """
    Acquire UEI for a company using USASpending autocomplete.
    
    The autocomplete endpoint returns recipient matches with UEI.
    We match based on name similarity.
    """
    if not company_name or len(company_name) < 3:
        return UEIResult()
    
    payload = {
        "search_text": company_name[:80],
        "limit": 10,
    }
    
    result = _api_request(USASPENDING_AUTOCOMPLETE, payload)
    if not result:
        return UEIResult()
    
    recipients = result.get("results", [])
    if not recipients:
        return UEIResult()
    
    # Find best match
    company_lower = company_name.lower().strip()
    best_match = None
    best_score = 0.0
    
    for r in recipients:
        r_name = (r.get("recipient_name") or r.get("name") or "").strip()
        r_lower = r_name.lower()
        
        # Exact match
        if r_lower == company_lower:
            best_match = r
            best_score = 1.0
            break
        
        # Contains match
        if company_lower in r_lower or r_lower in company_lower:
            score = len(company_lower) / max(len(r_lower), len(company_lower))
            if score > best_score:
                best_match = r
                best_score = score
    
    # Take first result if no good match
    if not best_match and recipients:
        best_match = recipients[0]
        best_score = 0.5
    
    if not best_match:
        return UEIResult()
    
    uei = best_match.get("uei") or best_match.get("recipient_unique_id") or ""
    
    return UEIResult(
        uei=uei if uei else None,
        recipient_name=best_match.get("recipient_name", ""),
        recipient_id=best_match.get("recipient_id", ""),
        location=best_match.get("location", ""),
        confidence=best_score,
        source="USASpending Autocomplete",
    )


# =============================================================================
# PHASE 3 & 4: AWARD DETAIL ENRICHMENT
# =============================================================================

@dataclass
class AwardProfile:
    """Aggregated award profile for a recipient."""
    # Counts
    contract_count: int = 0
    grant_count: int = 0
    total_award_count: int = 0
    
    # Values
    total_contract_value: float = 0.0
    total_grant_value: float = 0.0
    largest_contract_value: float = 0.0
    average_contract_value: float = 0.0
    
    # Dates
    most_recent_award_date: Optional[str] = None
    oldest_award_date: Optional[str] = None
    
    # Agency distribution
    agencies: List[str] = field(default_factory=list)
    dod_award_count: int = 0
    dod_award_value: float = 0.0
    dod_percentage: float = 0.0
    
    # NAICS
    naics_codes: List[str] = field(default_factory=list)
    primary_naics: Optional[str] = None
    
    # Location
    locations: List[str] = field(default_factory=list)
    primary_location: Optional[str] = None
    
    # Success flag
    success: bool = False
    error: Optional[str] = None


def get_award_profile_by_uei(uei: str) -> AwardProfile:
    """
    Get comprehensive award profile using UEI.
    
    Queries USASpending award search with UEI filter for accurate results.
    """
    if not uei:
        return AwardProfile(error="No UEI provided")
    
    # Query awards by UEI
    payload = {
        "filters": {
            "recipient_id": [uei],
            "time_period": [
                {"start_date": "2018-01-01", "end_date": datetime.now().strftime("%Y-%m-%d")}
            ],
            "award_type_codes": ["A", "B", "C", "D"],  # Contracts only
        },
        "fields": [
            "Award ID",
            "Recipient Name", 
            "Recipient UEI",
            "Award Amount",
            "Awarding Agency",
            "Awarding Sub Agency",
            "Award Type",
            "Start Date",
            "End Date",
            "NAICS Code",
            "NAICS Description",
            "Place of Performance City",
            "Place of Performance State Code",
            "Description",
        ],
        "page": 1,
        "limit": 500,
        "sort": "Award Amount",
        "order": "desc",
    }
    
    result = _api_request(USASPENDING_AWARD_SEARCH, payload)
    if not result:
        # Fallback: try recipient_search_text
        return get_award_profile_by_name_fallback(uei)
    
    awards = result.get("results", [])
    
    if not awards:
        # Fallback to name-based search
        return get_award_profile_by_name_fallback(uei)
    
    return _aggregate_awards(awards)


def get_award_profile_by_name_fallback(company_name: str) -> AwardProfile:
    """Fallback: search by company name when UEI search returns no results."""
    if not company_name:
        return AwardProfile(error="No company name provided")
    
    payload = {
        "filters": {
            "recipient_search_text": [company_name],
            "time_period": [
                {"start_date": "2018-01-01", "end_date": datetime.now().strftime("%Y-%m-%d")}
            ],
            "award_type_codes": ["A", "B", "C", "D"],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Awarding Sub Agency",
            "Award Type",
            "Start Date",
            "NAICS Code",
            "NAICS Description",
            "Place of Performance City",
            "Place of Performance State Code",
        ],
        "page": 1,
        "limit": 200,
        "sort": "Award Amount",
        "order": "desc",
    }
    
    result = _api_request(USASPENDING_AWARD_SEARCH, payload)
    if not result:
        return AwardProfile(error="API request failed")
    
    awards = result.get("results", [])
    if not awards:
        return AwardProfile(success=True)  # No awards found is valid
    
    return _aggregate_awards(awards)


def _aggregate_awards(awards: List[Dict[str, Any]]) -> AwardProfile:
    """Aggregate award data into a profile."""
    profile = AwardProfile(success=True)
    
    agencies: Dict[str, int] = {}
    naics_counts: Dict[str, int] = {}
    locations: Dict[str, int] = {}
    dates: List[str] = []
    
    for award in awards:
        # Count
        profile.total_award_count += 1
        profile.contract_count += 1
        
        # Value
        amount = award.get("Award Amount")
        if amount and isinstance(amount, (int, float)):
            amount = float(amount)
            profile.total_contract_value += amount
            if amount > profile.largest_contract_value:
                profile.largest_contract_value = amount
        
        # Agency
        agency = award.get("Awarding Agency") or ""
        sub_agency = award.get("Awarding Sub Agency") or ""
        full_agency = agency or sub_agency
        if full_agency:
            agencies[full_agency] = agencies.get(full_agency, 0) + 1
            
            # Check DoD
            agency_lower = full_agency.lower()
            if any(dod in agency_lower for dod in DOD_AGENCIES):
                profile.dod_award_count += 1
                if amount:
                    profile.dod_award_value += amount
        
        # NAICS
        naics = award.get("NAICS Code")
        if naics:
            naics_str = str(naics)
            naics_counts[naics_str] = naics_counts.get(naics_str, 0) + 1
        
        # Date
        start_date = award.get("Start Date")
        if start_date:
            dates.append(start_date)
        
        # Location
        city = award.get("Place of Performance City") or ""
        state = award.get("Place of Performance State Code") or ""
        if city or state:
            loc = f"{city}, {state}".strip(", ")
            locations[loc] = locations.get(loc, 0) + 1
    
    # Calculate averages and percentages
    if profile.contract_count > 0:
        profile.average_contract_value = profile.total_contract_value / profile.contract_count
    
    if profile.total_contract_value > 0:
        profile.dod_percentage = (profile.dod_award_value / profile.total_contract_value) * 100
    
    # Sort and extract top agencies
    sorted_agencies = sorted(agencies.items(), key=lambda x: x[1], reverse=True)
    profile.agencies = [a[0] for a in sorted_agencies[:10]]
    
    # Primary NAICS
    if naics_counts:
        sorted_naics = sorted(naics_counts.items(), key=lambda x: x[1], reverse=True)
        profile.naics_codes = [n[0] for n in sorted_naics[:5]]
        profile.primary_naics = sorted_naics[0][0]
    
    # Primary location
    if locations:
        sorted_locs = sorted(locations.items(), key=lambda x: x[1], reverse=True)
        profile.locations = [l[0] for l in sorted_locs[:5]]
        profile.primary_location = sorted_locs[0][0]
    
    # Dates
    if dates:
        profile.most_recent_award_date = max(dates)
        profile.oldest_award_date = min(dates)
    
    return profile


# =============================================================================
# PHASE 5: NAICS INTELLIGENCE
# =============================================================================

@dataclass
class NAICSIntelligence:
    """Industry intelligence derived from NAICS codes."""
    primary_naics: Optional[str] = None
    naics_codes: List[str] = field(default_factory=list)
    is_manufacturing: bool = False
    is_aerospace: bool = False
    is_defense: bool = False
    manufacturing_confidence: float = 0.0
    aerospace_confidence: float = 0.0
    defense_confidence: float = 0.0


def analyze_naics(naics_codes: List[str], company_name: str = "") -> NAICSIntelligence:
    """
    Analyze NAICS codes to determine industry exposure.
    
    Evidence-based only. Never fabricates.
    """
    intel = NAICSIntelligence(naics_codes=naics_codes)
    
    if not naics_codes:
        # Try to infer from company name
        name_lower = company_name.lower()
        
        if any(kw in name_lower for kw in ["manufacturing", "machining", "fabricat", "metal", "precision"]):
            intel.is_manufacturing = True
            intel.manufacturing_confidence = 0.6
        
        if any(kw in name_lower for kw in ["aerospace", "aviation", "aircraft", "flight"]):
            intel.is_aerospace = True
            intel.aerospace_confidence = 0.6
        
        if any(kw in name_lower for kw in ["defense", "defence", "military", "tactical"]):
            intel.is_defense = True
            intel.defense_confidence = 0.6
        
        return intel
    
    intel.primary_naics = naics_codes[0] if naics_codes else None
    
    # Check manufacturing (31-33 sector)
    for naics in naics_codes:
        if any(naics.startswith(prefix) for prefix in MANUFACTURING_NAICS_PREFIXES):
            intel.is_manufacturing = True
            intel.manufacturing_confidence = 0.95
            break
    
    # Check aerospace
    for naics in naics_codes:
        if any(naics.startswith(aero) for aero in AEROSPACE_NAICS_CODES):
            intel.is_aerospace = True
            intel.aerospace_confidence = 0.95
            break
    
    # Check defense
    for naics in naics_codes:
        if naics in DEFENSE_NAICS_CODES:
            intel.is_defense = True
            intel.defense_confidence = 0.90
            break
    
    return intel


# =============================================================================
# PHASE 6: COMPLIANCE EXPOSURE MODEL
# =============================================================================

@dataclass
class ComplianceExposure:
    """Compliance exposure assessment based on evidence."""
    cmmc_likelihood: float = 0.0
    cmmc_confidence: float = 0.0
    cmmc_evidence: List[str] = field(default_factory=list)
    
    dfars_likelihood: float = 0.0
    dfars_confidence: float = 0.0
    dfars_evidence: List[str] = field(default_factory=list)


def assess_compliance_exposure(
    dod_percentage: float,
    dod_award_count: int,
    is_manufacturing: bool,
    is_defense: bool,
    naics_codes: List[str],
) -> ComplianceExposure:
    """
    Assess CMMC and DFARS likelihood based on evidence.
    
    Never hallucinate. Unknown remains UNKNOWN.
    Evidence-backed scoring only.
    """
    exposure = ComplianceExposure()
    
    # CMMC likelihood factors
    if dod_percentage > 0:
        exposure.cmmc_likelihood += 0.4
        exposure.cmmc_evidence.append(f"DoD exposure: {dod_percentage:.1f}%")
    
    if dod_award_count >= 3:
        exposure.cmmc_likelihood += 0.2
        exposure.cmmc_evidence.append(f"Multiple DoD contracts: {dod_award_count}")
    
    if is_manufacturing:
        exposure.cmmc_likelihood += 0.15
        exposure.cmmc_evidence.append("Manufacturing industry (CUI likely)")
    
    if is_defense:
        exposure.cmmc_likelihood += 0.15
        exposure.cmmc_evidence.append("Defense industry classification")
    
    # Cap at 0.95 - never claim certainty
    exposure.cmmc_likelihood = min(0.95, exposure.cmmc_likelihood)
    exposure.cmmc_confidence = 0.7 if exposure.cmmc_evidence else 0.0
    
    # DFARS likelihood (similar to CMMC but slightly different weighting)
    if dod_percentage > 0:
        exposure.dfars_likelihood += 0.45
        exposure.dfars_evidence.append(f"DoD contract recipient: {dod_percentage:.1f}%")
    
    if dod_award_count >= 1:
        exposure.dfars_likelihood += 0.25
        exposure.dfars_evidence.append(f"DoD award count: {dod_award_count}")
    
    if is_manufacturing and dod_percentage > 0:
        exposure.dfars_likelihood += 0.15
        exposure.dfars_evidence.append("Manufacturing + DoD = DFARS likely")
    
    exposure.dfars_likelihood = min(0.95, exposure.dfars_likelihood)
    exposure.dfars_confidence = 0.7 if exposure.dfars_evidence else 0.0
    
    return exposure


# =============================================================================
# DEEP ENRICHMENT ENGINE
# =============================================================================

@dataclass
class DeepEnrichmentResult:
    """Result of deep enrichment for a single record."""
    record_id: str
    company_name: str
    success: bool = True
    
    # UEI acquisition
    uei_acquired: bool = False
    uei: Optional[str] = None
    
    # Fields enriched
    fields_before: int = 0
    fields_after: int = 0
    fields_added: List[str] = field(default_factory=list)
    
    # Metrics
    completeness_before: int = 0
    completeness_after: int = 0
    enrichment_before: int = 0
    enrichment_after: int = 0
    tier_before: str = ""
    tier_after: str = ""
    recommendation_before: str = ""
    recommendation_after: str = ""
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "company_name": self.company_name,
            "success": self.success,
            "uei_acquired": self.uei_acquired,
            "uei": self.uei,
            "fields_added": self.fields_added,
            "fields_added_count": len(self.fields_added),
            "before": {
                "completeness": self.completeness_before,
                "enrichment": self.enrichment_before,
                "tier": self.tier_before,
                "recommendation": self.recommendation_before,
            },
            "after": {
                "completeness": self.completeness_after,
                "enrichment": self.enrichment_after,
                "tier": self.tier_after,
                "recommendation": self.recommendation_after,
            },
            "delta": {
                "completeness": self.completeness_after - self.completeness_before,
                "enrichment": self.enrichment_after - self.enrichment_before,
                "tier_changed": self.tier_before != self.tier_after,
                "recommendation_changed": self.recommendation_before != self.recommendation_after,
            },
            "errors": self.errors,
        }


def deep_enrich_record(
    record: CustomerIntelligenceRecord,
    pause_seconds: float = 0.5,
) -> DeepEnrichmentResult:
    """
    Perform deep enrichment on a single record using USASpending data.
    
    NO OUTREACH. NO EMAILS. NO CONTACTS. EVIDENCE ONLY.
    """
    result = DeepEnrichmentResult(
        record_id=record.record_id,
        company_name=record.company_name.value or "Unknown",
    )
    
    company_name = record.company_name.value
    if not company_name:
        result.success = False
        result.errors.append("No company name")
        return result
    
    # Capture before state
    icp_before = evaluate_icp_match(record)
    rec_before, _ = compute_recommendation(record, icp_before)
    result.completeness_before = record.compute_intelligence_completeness()
    result.enrichment_before = compute_enrichment_score(record)
    result.tier_before = icp_before.get("tier", "NO_MATCH")
    result.recommendation_before = rec_before.value
    
    # PHASE 2: UEI Acquisition
    uei_result = acquire_uei(company_name)
    time.sleep(pause_seconds)
    
    if uei_result.is_found():
        result.uei_acquired = True
        result.uei = uei_result.uei
        
        if record.uei.state == SignalState.UNKNOWN:
            record.uei = EvidencedValue(
                value=uei_result.uei,
                source=uei_result.source,
                confidence=uei_result.confidence,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("uei")
        
        # Also capture location if available
        if uei_result.location and record.location.state == SignalState.UNKNOWN:
            record.location = EvidencedValue(
                value=uei_result.location,
                source=uei_result.source,
                confidence=uei_result.confidence * 0.9,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("location")
    
    # PHASE 3 & 4: Award Profile Enrichment
    award_profile: Optional[AwardProfile] = None
    
    if result.uei:
        award_profile = get_award_profile_by_uei(result.uei)
        time.sleep(pause_seconds)
    
    if not award_profile or not award_profile.success or award_profile.contract_count == 0:
        # Fallback to name search
        award_profile = get_award_profile_by_name_fallback(company_name)
        time.sleep(pause_seconds)
    
    if award_profile and award_profile.success:
        # Contract count
        if award_profile.contract_count > 0:
            record.contract_count = EvidencedValue(
                value=award_profile.contract_count,
                source="USASpending Award Search",
                confidence=0.95,
                state=SignalState.KNOWN,
            )
            if "contract_count" not in result.fields_added:
                result.fields_added.append("contract_count")
        
        # Contract value
        if award_profile.total_contract_value > 0:
            record.contract_value = EvidencedValue(
                value=award_profile.total_contract_value,
                source="USASpending Award Search",
                confidence=0.95,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("contract_value")
        
        # Award recency
        if award_profile.most_recent_award_date:
            record.award_recency = EvidencedValue(
                value=award_profile.most_recent_award_date,
                source="USASpending Award Search",
                confidence=0.95,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("award_recency")
        
        # NAICS
        if award_profile.primary_naics and record.naics.state == SignalState.UNKNOWN:
            record.naics = EvidencedValue(
                value=award_profile.primary_naics,
                source="USASpending Award Search",
                confidence=0.90,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("naics")
        
        # Agency mix
        if award_profile.agencies:
            record.agency_mix = EvidencedValue(
                value=award_profile.agencies,
                source="USASpending Award Search",
                confidence=0.95,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("agency_mix")
        
        # DoD exposure
        if award_profile.dod_award_count > 0:
            record.dod_exposure = EvidencedValue(
                value=True,
                source="USASpending Award Search",
                confidence=0.95,
                state=SignalState.KNOWN,
            )
            if "dod_exposure" not in result.fields_added:
                result.fields_added.append("dod_exposure")
        
        # Location from awards
        if award_profile.primary_location and record.location.state == SignalState.UNKNOWN:
            record.location = EvidencedValue(
                value=award_profile.primary_location,
                source="USASpending Award Search",
                confidence=0.85,
                state=SignalState.KNOWN,
            )
            if "location" not in result.fields_added:
                result.fields_added.append("location")
        
        # PHASE 5: NAICS Intelligence
        naics_intel = analyze_naics(
            award_profile.naics_codes,
            company_name,
        )
        
        if naics_intel.is_manufacturing and record.manufacturing_exposure.state == SignalState.UNKNOWN:
            record.manufacturing_exposure = EvidencedValue(
                value=True,
                source="NAICS Analysis",
                confidence=naics_intel.manufacturing_confidence,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("manufacturing_exposure")
        
        if naics_intel.is_aerospace and record.aerospace_exposure.state == SignalState.UNKNOWN:
            record.aerospace_exposure = EvidencedValue(
                value=True,
                source="NAICS Analysis",
                confidence=naics_intel.aerospace_confidence,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("aerospace_exposure")
        
        # PHASE 6: Compliance Exposure
        compliance = assess_compliance_exposure(
            dod_percentage=award_profile.dod_percentage,
            dod_award_count=award_profile.dod_award_count,
            is_manufacturing=naics_intel.is_manufacturing,
            is_defense=naics_intel.is_defense or award_profile.dod_award_count > 0,
            naics_codes=award_profile.naics_codes,
        )
        
        if compliance.cmmc_likelihood > 0 and record.cmmc_likelihood.state == SignalState.UNKNOWN:
            record.cmmc_likelihood = EvidencedValue(
                value=compliance.cmmc_likelihood,
                source="Compliance Analysis",
                confidence=compliance.cmmc_confidence,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("cmmc_likelihood")
        
        if compliance.dfars_likelihood > 0 and record.dfars_likelihood.state == SignalState.UNKNOWN:
            record.dfars_likelihood = EvidencedValue(
                value=compliance.dfars_likelihood,
                source="Compliance Analysis",
                confidence=compliance.dfars_confidence,
                state=SignalState.KNOWN,
            )
            result.fields_added.append("dfars_likelihood")
    
    # Update computed scores
    record.contactability_score = EvidencedValue(
        value=record.compute_contactability(),
        source="computed",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    record.ability_to_pay_score = EvidencedValue(
        value=record.compute_ability_to_pay(),
        source="computed",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    # Save
    save_intelligence_record(record)
    
    # Capture after state
    icp_after = evaluate_icp_match(record)
    rec_after, _ = compute_recommendation(record, icp_after)
    result.completeness_after = record.compute_intelligence_completeness()
    result.enrichment_after = compute_enrichment_score(record)
    result.tier_after = icp_after.get("tier", "NO_MATCH")
    result.recommendation_after = rec_after.value
    
    return result


def deep_enrich_all_records(
    limit: int = 100,
    pause_between_records: float = 1.0,
) -> Dict[str, Any]:
    """
    Deep enrich all intelligence records.
    
    Returns comprehensive before/after report.
    """
    records = get_all_intelligence_records()
    
    # Capture before state
    before_completeness = []
    before_tiers = {"TIER_1": 0, "TIER_2": 0, "TIER_3": 0, "NO_MATCH": 0}
    
    for r in records:
        before_completeness.append(r.compute_intelligence_completeness())
        icp = evaluate_icp_match(r)
        tier = icp.get("tier", "NO_MATCH")
        before_tiers[tier] = before_tiers.get(tier, 0) + 1
    
    avg_completeness_before = sum(before_completeness) / len(before_completeness) if before_completeness else 0
    
    # Run enrichment
    results: List[DeepEnrichmentResult] = []
    
    for record in records[:limit]:
        result = deep_enrich_record(record, pause_seconds=0.5)
        results.append(result)
        
        if pause_between_records > 0:
            time.sleep(pause_between_records)
    
    # Reload and capture after state
    records_after = get_all_intelligence_records()
    after_completeness = []
    after_tiers = {"TIER_1": 0, "TIER_2": 0, "TIER_3": 0, "NO_MATCH": 0}
    
    for r in records_after:
        after_completeness.append(r.compute_intelligence_completeness())
        icp = evaluate_icp_match(r)
        tier = icp.get("tier", "NO_MATCH")
        after_tiers[tier] = after_tiers.get(tier, 0) + 1
    
    avg_completeness_after = sum(after_completeness) / len(after_completeness) if after_completeness else 0
    
    # Summary statistics
    ueis_acquired = sum(1 for r in results if r.uei_acquired)
    tier_changes = sum(1 for r in results if r.tier_before != r.tier_after)
    recommendation_changes = sum(1 for r in results if r.recommendation_before != r.recommendation_after)
    total_fields_added = sum(len(r.fields_added) for r in results)
    
    return {
        "ok": True,
        "enriched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records_processed": len(results),
        "summary": {
            "ueis_acquired": ueis_acquired,
            "total_fields_added": total_fields_added,
            "tier_changes": tier_changes,
            "recommendation_changes": recommendation_changes,
        },
        "before": {
            "average_completeness": round(avg_completeness_before, 1),
            "tier_distribution": before_tiers,
        },
        "after": {
            "average_completeness": round(avg_completeness_after, 1),
            "tier_distribution": after_tiers,
        },
        "delta": {
            "completeness": round(avg_completeness_after - avg_completeness_before, 1),
        },
        "results": [r.to_dict() for r in results],
    }


def generate_deep_enrichment_report(limit: int = 20) -> Dict[str, Any]:
    """Generate a detailed before/after report for top companies."""
    report = deep_enrich_all_records(limit=limit)
    
    # Add top 20 comparison
    results = report.get("results", [])
    
    top_20 = []
    for r in results[:20]:
        top_20.append({
            "company": r["company_name"],
            "uei_acquired": r["uei_acquired"],
            "before_completeness": r["before"]["completeness"],
            "after_completeness": r["after"]["completeness"],
            "completeness_delta": r["delta"]["completeness"],
            "before_tier": r["before"]["tier"],
            "after_tier": r["after"]["tier"],
            "tier_changed": r["delta"]["tier_changed"],
            "before_recommendation": r["before"]["recommendation"],
            "after_recommendation": r["after"]["recommendation"],
            "fields_added": r["fields_added"],
        })
    
    report["top_20_comparison"] = top_20
    
    return report

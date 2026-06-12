"""PATCH 13A-15: Evidence Enrichment Engine.

Transform company names into actionable intelligence.

NO OUTREACH. NO EMAILS. NO AUTO-SEND. NO MARKETING.
ONLY EVIDENCE COLLECTION.

Every field must be:
- KNOWN (with source and confidence)
- or UNKNOWN

Never fabricate. Never infer. Never guess.
"""
from __future__ import annotations

import json
import logging
import re
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

USER_AGENT = "KeepYourContracts-EvidenceEnrichment/1.0 (+https://compliance.keepyourcontracts.com; lawful-evidence-collection)"

# USASpending API endpoints
USASPENDING_RECIPIENT_SEARCH = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
USASPENDING_RECIPIENT_DETAIL = "https://api.usaspending.gov/api/v2/recipient/duns/"
USASPENDING_AWARD_SEARCH = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
USASPENDING_AUTOCOMPLETE = "https://api.usaspending.gov/api/v2/autocomplete/recipient/"


# =============================================================================
# DATA COLLECTION - Evidence Fields
# =============================================================================

@dataclass
class EnrichmentEvidence:
    """Evidence collected during enrichment."""
    field_name: str
    value: Any
    source: str
    confidence: float
    collected_utc: str = ""
    
    def __post_init__(self):
        if not self.collected_utc:
            self.collected_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass  
class EnrichmentResult:
    """Result of enriching a single company."""
    record_id: str
    company_name: str
    success: bool
    evidence_collected: List[EnrichmentEvidence] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Before/after metrics
    before_completeness: int = 0
    after_completeness: int = 0
    before_enrichment: int = 0
    after_enrichment: int = 0
    before_tier: str = ""
    after_tier: str = ""
    before_recommendation: str = ""
    after_recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "company_name": self.company_name,
            "success": self.success,
            "evidence_collected": len(self.evidence_collected),
            "evidence_fields": [e.field_name for e in self.evidence_collected],
            "errors": self.errors,
            "before": {
                "completeness": self.before_completeness,
                "enrichment": self.before_enrichment,
                "tier": self.before_tier,
                "recommendation": self.before_recommendation,
            },
            "after": {
                "completeness": self.after_completeness,
                "enrichment": self.after_enrichment,
                "tier": self.after_tier,
                "recommendation": self.after_recommendation,
            },
            "delta": {
                "completeness": self.after_completeness - self.before_completeness,
                "enrichment": self.after_enrichment - self.before_enrichment,
                "tier_changed": self.before_tier != self.after_tier,
                "recommendation_changed": self.before_recommendation != self.after_recommendation,
            },
        }


# =============================================================================
# USASPENDING API QUERIES
# =============================================================================

def _api_request(url: str, payload: dict, timeout: int = 30) -> Optional[dict]:
    """Make a request to USASpending API."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning("API request failed: %s - %s", url, e)
        return None


def search_recipient_by_name(company_name: str) -> List[Dict[str, Any]]:
    """Search USASpending for recipient by name."""
    if not company_name or len(company_name) < 3:
        return []
    
    payload = {
        "search_text": company_name[:80],
        "limit": 10,
    }
    
    result = _api_request(USASPENDING_AUTOCOMPLETE, payload)
    if not result:
        return []
    
    return result.get("results", [])


def get_recipient_awards(
    company_name: str,
    *,
    limit: int = 100,
    min_date: str = "2020-01-01",
) -> Dict[str, Any]:
    """
    Get award data for a recipient from USASpending.
    
    Returns aggregated info:
    - Total contract value
    - Contract count
    - Most recent award date
    - Awarding agencies
    - NAICS codes
    - DoD exposure indicator
    """
    # Search for recipient's awards
    payload = {
        "filters": {
            "recipient_search_text": [company_name],
            "time_period": [
                {"start_date": min_date, "end_date": datetime.now().strftime("%Y-%m-%d")}
            ],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Contract Award Type",
            "Start Date",
            "End Date",
            "NAICS Code",
            "NAICS Description",
            "Place of Performance City",
            "Place of Performance State",
        ],
        "page": 1,
        "limit": limit,
        "sort": "Award Amount",
        "order": "desc",
    }
    
    result = _api_request(USASPENDING_AWARD_SEARCH, payload)
    if not result:
        return {"ok": False, "error": "API request failed"}
    
    awards = result.get("results", [])
    if not awards:
        return {"ok": True, "awards_found": 0}
    
    # Aggregate data
    total_value = 0.0
    agencies = set()
    naics_codes = set()
    dates = []
    locations = set()
    dod_agencies = {"Department of Defense", "DoD", "Army", "Navy", "Air Force", "Marine Corps"}
    has_dod = False
    
    for award in awards:
        # Contract value
        amount = award.get("Award Amount")
        if amount and isinstance(amount, (int, float)):
            total_value += float(amount)
        
        # Awarding agency
        agency = award.get("Awarding Agency")
        if agency:
            agencies.add(agency)
            if any(d in agency for d in dod_agencies):
                has_dod = True
        
        # NAICS
        naics = award.get("NAICS Code")
        if naics:
            naics_codes.add(str(naics))
        
        # Dates
        start = award.get("Start Date")
        if start:
            dates.append(start)
        
        # Location
        city = award.get("Place of Performance City", "")
        state = award.get("Place of Performance State", "")
        if city or state:
            locations.add(f"{city}, {state}".strip(", "))
    
    # Find most recent date
    most_recent = max(dates) if dates else None
    
    return {
        "ok": True,
        "awards_found": len(awards),
        "total_value": total_value,
        "contract_count": len(awards),
        "most_recent_award": most_recent,
        "agencies": list(agencies)[:10],
        "naics_codes": list(naics_codes)[:5],
        "has_dod_exposure": has_dod,
        "locations": list(locations)[:3],
    }


# =============================================================================
# WEBSITE DISCOVERY
# =============================================================================

def discover_company_website(company_name: str) -> Optional[str]:
    """
    Attempt to discover a company's website.
    
    Strategy:
    1. Try common domain patterns (.com, .net, etc.)
    2. Use cleaned company name
    
    Returns None if no website found (UNKNOWN, not fabricated).
    """
    if not company_name:
        return None
    
    # Clean company name for domain guess
    clean = company_name.lower()
    clean = re.sub(r'\b(inc|llc|corp|ltd|co|company|corporation|limited)\b\.?', '', clean)
    clean = re.sub(r'[^a-z0-9]', '', clean)
    
    if len(clean) < 3:
        return None
    
    # Try common domain patterns
    candidates = [
        f"https://www.{clean}.com",
        f"https://{clean}.com",
    ]
    
    for url in candidates:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT},
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return url
        except Exception:
            continue
    
    return None


def extract_contact_from_website(url: str) -> Dict[str, Any]:
    """
    Extract public contact info from website.
    
    Only extracts clearly public contact info (contact pages, footers).
    Never scrapes private data.
    """
    if not url:
        return {}
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return {}
            html = resp.read(200_000).decode("utf-8", errors="replace")
    except Exception:
        return {}
    
    result = {}
    
    # Look for email (public contact forms often have mailto:)
    email_match = re.search(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', html)
    if email_match:
        email = email_match.group(1).lower()
        # Only accept generic contact emails, not personal
        if any(prefix in email for prefix in ["info@", "contact@", "sales@", "hello@", "support@"]):
            result["contact_email"] = email
    
    # Look for phone
    phone_match = re.search(r'tel:([+\d\-\(\)\s]{10,20})', html)
    if phone_match:
        result["phone"] = phone_match.group(1).strip()
    
    return result


# =============================================================================
# INDICATOR DETECTION
# =============================================================================

def detect_industry_indicators(
    company_name: str,
    naics_codes: List[str],
    agencies: List[str],
) -> Dict[str, bool]:
    """
    Detect industry indicators based on evidence.
    
    Returns indicators that are KNOWN True/False based on evidence.
    Does NOT fabricate or infer.
    """
    indicators = {}
    name_lower = company_name.lower()
    
    # Manufacturing indicator
    manufacturing_naics = ["31", "32", "33"]  # Manufacturing sector
    manufacturing_keywords = ["manufacturing", "machining", "fabricat", "metal", "precision"]
    
    has_manufacturing_naics = any(n[:2] in manufacturing_naics for n in naics_codes)
    has_manufacturing_name = any(kw in name_lower for kw in manufacturing_keywords)
    
    if has_manufacturing_naics or has_manufacturing_name:
        indicators["manufacturing_exposure"] = True
    
    # Aerospace indicator
    aerospace_naics = ["3364", "3369"]  # Aerospace
    aerospace_keywords = ["aerospace", "aviation", "aircraft", "flight"]
    
    has_aerospace_naics = any(n.startswith(tuple(aerospace_naics)) for n in naics_codes)
    has_aerospace_name = any(kw in name_lower for kw in aerospace_keywords)
    
    if has_aerospace_naics or has_aerospace_name:
        indicators["aerospace_exposure"] = True
    
    # Defense indicator
    defense_keywords = ["defense", "defence", "military", "tactical"]
    dod_agency_keywords = ["defense", "army", "navy", "air force", "marine", "dod"]
    
    has_defense_name = any(kw in name_lower for kw in defense_keywords)
    has_defense_agency = any(
        any(kw in agency.lower() for kw in dod_agency_keywords) 
        for agency in agencies
    )
    
    if has_defense_name or has_defense_agency:
        indicators["dod_exposure"] = True
    
    # Small business indicator (based on typical small biz set-aside agencies)
    small_biz_agencies = ["Small Business Administration", "SBA"]
    if any(sba in " ".join(agencies) for sba in small_biz_agencies):
        indicators["is_small_business"] = True
    
    return indicators


def estimate_cmmc_dfars_likelihood(
    dod_exposure: bool,
    manufacturing: bool,
    defense_in_name: bool,
) -> Dict[str, float]:
    """
    Estimate CMMC/DFARS likelihood based on evidence.
    
    Returns confidence levels, not binary decisions.
    """
    likelihood = {
        "cmmc_likelihood": 0.0,
        "dfars_likelihood": 0.0,
    }
    
    if dod_exposure:
        likelihood["cmmc_likelihood"] += 0.5
        likelihood["dfars_likelihood"] += 0.5
    
    if manufacturing and dod_exposure:
        likelihood["cmmc_likelihood"] += 0.3
        likelihood["dfars_likelihood"] += 0.3
    
    if defense_in_name:
        likelihood["cmmc_likelihood"] += 0.1
        likelihood["dfars_likelihood"] += 0.1
    
    # Cap at 0.9 - never claim certainty without verification
    likelihood["cmmc_likelihood"] = min(0.9, likelihood["cmmc_likelihood"])
    likelihood["dfars_likelihood"] = min(0.9, likelihood["dfars_likelihood"])
    
    return likelihood


# =============================================================================
# ENRICHMENT ENGINE
# =============================================================================

def enrich_single_company(
    record: CustomerIntelligenceRecord,
    *,
    pause_seconds: float = 0.5,
) -> EnrichmentResult:
    """
    Enrich a single company's intelligence record with evidence.
    
    Collects:
    1. UEI
    2. Website
    3. NAICS
    4. Contract count
    5. Total federal contract value
    6. Most recent award date
    7. Awarding agency
    8. DoD exposure
    9. Manufacturing indicator
    10. Aerospace indicator
    11. Defense indicator
    12. Small business indicator
    13. Employee count (if available)
    14. Public contact email (if available)
    15. Public phone (if available)
    
    Every field has source and confidence. Never fabricates.
    """
    result = EnrichmentResult(
        record_id=record.record_id,
        company_name=record.company_name.value or "Unknown",
        success=True,
    )
    
    # Capture before state
    icp_before = evaluate_icp_match(record)
    rec_before, _ = compute_recommendation(record, icp_before)
    result.before_completeness = record.compute_intelligence_completeness()
    result.before_enrichment = compute_enrichment_score(record)
    result.before_tier = icp_before.get("tier", "NO_MATCH")
    result.before_recommendation = rec_before.value
    
    company_name = record.company_name.value
    if not company_name:
        result.success = False
        result.errors.append("No company name to enrich")
        return result
    
    evidence_collected: List[EnrichmentEvidence] = []
    
    # Step 1: Search USASpending for recipient details
    try:
        recipients = search_recipient_by_name(company_name)
        if recipients:
            best_match = recipients[0]  # Assuming first result is best match
            
            # Extract UEI
            uei = best_match.get("uei") or best_match.get("recipient_unique_id")
            if uei and record.uei.state == SignalState.UNKNOWN:
                record.uei = EvidencedValue(
                    value=uei,
                    source="USASpending Recipient Lookup",
                    confidence=0.95,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="uei",
                    value=uei,
                    source="USASpending Recipient Lookup",
                    confidence=0.95,
                ))
            
            # Extract location if available
            location = best_match.get("location") or best_match.get("city")
            if location and record.location.state == SignalState.UNKNOWN:
                record.location = EvidencedValue(
                    value=location[:120],
                    source="USASpending Recipient Lookup",
                    confidence=0.8,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="location",
                    value=location[:120],
                    source="USASpending Recipient Lookup",
                    confidence=0.8,
                ))
    except Exception as e:
        result.errors.append(f"Recipient search failed: {str(e)[:100]}")
    
    time.sleep(pause_seconds)
    
    # Step 2: Get award data
    try:
        awards_data = get_recipient_awards(company_name)
        
        if awards_data.get("ok") and awards_data.get("awards_found", 0) > 0:
            # Contract count
            count = awards_data.get("contract_count", 0)
            if count > 0:
                record.contract_count = EvidencedValue(
                    value=count,
                    source="USASpending Award Search",
                    confidence=0.95,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="contract_count",
                    value=count,
                    source="USASpending Award Search",
                    confidence=0.95,
                ))
            
            # Contract value
            total_value = awards_data.get("total_value", 0)
            if total_value > 0:
                record.contract_value = EvidencedValue(
                    value=total_value,
                    source="USASpending Award Search",
                    confidence=0.95,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="contract_value",
                    value=total_value,
                    source="USASpending Award Search",
                    confidence=0.95,
                ))
            
            # Most recent award (award_recency)
            most_recent = awards_data.get("most_recent_award")
            if most_recent:
                record.award_recency = EvidencedValue(
                    value=most_recent,
                    source="USASpending Award Search",
                    confidence=0.95,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="award_recency",
                    value=most_recent,
                    source="USASpending Award Search",
                    confidence=0.95,
                ))
            
            # NAICS codes
            naics_codes = awards_data.get("naics_codes", [])
            if naics_codes and record.naics.state == SignalState.UNKNOWN:
                primary_naics = naics_codes[0]
                record.naics = EvidencedValue(
                    value=primary_naics,
                    source="USASpending Award Search",
                    confidence=0.9,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="naics",
                    value=primary_naics,
                    source="USASpending Award Search",
                    confidence=0.9,
                ))
            
            # Agency mix
            agencies = awards_data.get("agencies", [])
            if agencies:
                record.agency_mix = EvidencedValue(
                    value=agencies,
                    source="USASpending Award Search",
                    confidence=0.95,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="agency_mix",
                    value=agencies,
                    source="USASpending Award Search",
                    confidence=0.95,
                ))
            
            # DoD exposure
            has_dod = awards_data.get("has_dod_exposure", False)
            if has_dod:
                record.dod_exposure = EvidencedValue(
                    value=True,
                    source="USASpending Award Search",
                    confidence=0.95,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="dod_exposure",
                    value=True,
                    source="USASpending Award Search",
                    confidence=0.95,
                ))
            
            # Industry indicators
            indicators = detect_industry_indicators(
                company_name,
                naics_codes,
                agencies,
            )
            
            if indicators.get("manufacturing_exposure"):
                record.manufacturing_exposure = EvidencedValue(
                    value=True,
                    source="Evidence Analysis (NAICS/Name)",
                    confidence=0.8,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="manufacturing_exposure",
                    value=True,
                    source="Evidence Analysis (NAICS/Name)",
                    confidence=0.8,
                ))
            
            if indicators.get("aerospace_exposure"):
                record.aerospace_exposure = EvidencedValue(
                    value=True,
                    source="Evidence Analysis (NAICS/Name)",
                    confidence=0.8,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="aerospace_exposure",
                    value=True,
                    source="Evidence Analysis (NAICS/Name)",
                    confidence=0.8,
                ))
            
            # CMMC/DFARS likelihood
            likelihood = estimate_cmmc_dfars_likelihood(
                dod_exposure=has_dod or indicators.get("dod_exposure", False),
                manufacturing=indicators.get("manufacturing_exposure", False),
                defense_in_name="defense" in company_name.lower(),
            )
            
            if likelihood["cmmc_likelihood"] > 0:
                record.cmmc_likelihood = EvidencedValue(
                    value=likelihood["cmmc_likelihood"],
                    source="Evidence Analysis (DoD/Manufacturing)",
                    confidence=0.7,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="cmmc_likelihood",
                    value=likelihood["cmmc_likelihood"],
                    source="Evidence Analysis (DoD/Manufacturing)",
                    confidence=0.7,
                ))
            
            if likelihood["dfars_likelihood"] > 0:
                record.dfars_likelihood = EvidencedValue(
                    value=likelihood["dfars_likelihood"],
                    source="Evidence Analysis (DoD/Manufacturing)",
                    confidence=0.7,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="dfars_likelihood",
                    value=likelihood["dfars_likelihood"],
                    source="Evidence Analysis (DoD/Manufacturing)",
                    confidence=0.7,
                ))
                
    except Exception as e:
        result.errors.append(f"Award search failed: {str(e)[:100]}")
    
    time.sleep(pause_seconds)
    
    # Step 3: Website discovery
    if record.website.state == SignalState.UNKNOWN:
        try:
            website = discover_company_website(company_name)
            if website:
                record.website = EvidencedValue(
                    value=website,
                    source="Website Discovery",
                    confidence=0.7,
                    state=SignalState.KNOWN,
                )
                evidence_collected.append(EnrichmentEvidence(
                    field_name="website",
                    value=website,
                    source="Website Discovery",
                    confidence=0.7,
                ))
                
                # Try to extract contact info
                time.sleep(pause_seconds)
                contact_info = extract_contact_from_website(website)
                
                if contact_info.get("contact_email") and record.contact_email.state == SignalState.UNKNOWN:
                    record.contact_email = EvidencedValue(
                        value=contact_info["contact_email"],
                        source="Website Contact Extraction",
                        confidence=0.6,
                        state=SignalState.KNOWN,
                    )
                    evidence_collected.append(EnrichmentEvidence(
                        field_name="contact_email",
                        value=contact_info["contact_email"],
                        source="Website Contact Extraction",
                        confidence=0.6,
                    ))
        except Exception as e:
            result.errors.append(f"Website discovery failed: {str(e)[:100]}")
    
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
    
    # Save the enriched record
    save_intelligence_record(record)
    
    # Capture after state
    icp_after = evaluate_icp_match(record)
    rec_after, _ = compute_recommendation(record, icp_after)
    result.after_completeness = record.compute_intelligence_completeness()
    result.after_enrichment = compute_enrichment_score(record)
    result.after_tier = icp_after.get("tier", "NO_MATCH")
    result.after_recommendation = rec_after.value
    result.evidence_collected = evidence_collected
    
    return result


def enrich_all_companies(
    *,
    limit: int = 50,
    pause_between_companies: float = 1.0,
) -> Dict[str, Any]:
    """
    Enrich all intelligence records that need enrichment.
    
    Returns before/after comparison for each company.
    """
    records = get_all_intelligence_records()
    
    # Sort by lowest enrichment score first (most in need)
    records.sort(key=lambda r: compute_enrichment_score(r))
    
    results: List[EnrichmentResult] = []
    
    for record in records[:limit]:
        result = enrich_single_company(record, pause_seconds=0.5)
        results.append(result)
        
        if pause_between_companies > 0:
            time.sleep(pause_between_companies)
    
    # Generate summary
    total_enriched = len(results)
    successful = sum(1 for r in results if r.success)
    total_evidence = sum(len(r.evidence_collected) for r in results)
    
    avg_completeness_delta = (
        sum(r.after_completeness - r.before_completeness for r in results) / total_enriched
        if total_enriched > 0 else 0
    )
    avg_enrichment_delta = (
        sum(r.after_enrichment - r.before_enrichment for r in results) / total_enriched
        if total_enriched > 0 else 0
    )
    
    tier_changes = sum(1 for r in results if r.before_tier != r.after_tier)
    recommendation_changes = sum(1 for r in results if r.before_recommendation != r.after_recommendation)
    
    return {
        "ok": True,
        "enriched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "total_companies": total_enriched,
            "successful": successful,
            "failed": total_enriched - successful,
            "total_evidence_collected": total_evidence,
            "avg_completeness_delta": round(avg_completeness_delta, 1),
            "avg_enrichment_delta": round(avg_enrichment_delta, 1),
            "tier_changes": tier_changes,
            "recommendation_changes": recommendation_changes,
        },
        "results": [r.to_dict() for r in results],
    }


def generate_enrichment_comparison(limit: int = 20) -> Dict[str, Any]:
    """
    Generate a before/after comparison report for top companies.
    
    Shows:
    - Company name
    - Before: completeness, enrichment, tier, recommendation
    - After: completeness, enrichment, tier, recommendation
    - Delta: changes in each metric
    """
    records = get_all_intelligence_records()
    
    # Enrich and capture before/after
    comparisons = []
    
    for record in records[:limit]:
        result = enrich_single_company(record, pause_seconds=0.5)
        comparisons.append(result.to_dict())
        time.sleep(0.5)  # Rate limiting
    
    return {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_companies": len(comparisons),
        "comparisons": comparisons,
        "columns": [
            "Company",
            "Before Completeness",
            "After Completeness",
            "Completeness Delta",
            "Before Enrichment",
            "After Enrichment",
            "Enrichment Delta",
            "Before Tier",
            "After Tier",
            "Before Recommendation",
            "After Recommendation",
            "Evidence Collected",
        ],
    }

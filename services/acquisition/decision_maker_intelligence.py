"""PATCH 13A-19: Decision Maker Intelligence Engine.

Identifies WHO can buy - not just whether a company exists.

NO OUTREACH. NO EMAILS. NO MARKETING.
EVIDENCE COLLECTION ONLY.

The organism must answer: Who specifically should we contact?
And provide evidence supporting that answer.
"""
from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

from .ideal_customer_profile import (
    CustomerIntelligenceRecord,
    EvidencedValue,
    SignalState,
    save_intelligence_record,
    get_all_intelligence_records,
    evaluate_icp_match,
)

logger = logging.getLogger(__name__)

USER_AGENT = "KeepYourContracts-DecisionMaker/1.0 (+https://compliance.keepyourcontracts.com; lawful-public-research)"


# =============================================================================
# PROCUREMENT RELEVANCE SCORING
# =============================================================================

# Highest Priority (score 100) - Can sign contracts
TIER_1_TITLES = {
    "president", "owner", "ceo", "chief executive officer",
    "founder", "co-founder", "managing member", "managing partner",
    "principal", "proprietor", "chairman", "chairwoman",
}

# Second Priority (score 75) - Influence purchasing decisions
TIER_2_TITLES = {
    "contracts manager", "contract manager", "contracts director",
    "compliance manager", "compliance director", "compliance officer",
    "quality manager", "quality director", "qa manager", "qc manager",
    "operations manager", "operations director", "coo",
    "chief operations officer", "vp operations", "vp of operations",
    "procurement manager", "purchasing manager", "supply chain manager",
}

# Third Priority (score 50) - General contacts
TIER_3_TITLES = {
    "general manager", "office manager", "administrative manager",
    "administrator", "executive assistant", "office administrator",
    "general contact", "contact", "receptionist",
}


def compute_title_relevance_score(title: str) -> int:
    """
    Compute procurement relevance score for a title.
    
    Returns:
    - 100: Highest priority (can sign contracts)
    - 75: Second priority (influence purchasing)
    - 50: Third priority (general contact)
    - 25: Unknown/other title
    - 0: No title
    """
    if not title:
        return 0
    
    title_lower = title.lower().strip()
    
    # Check tier 1
    for t in TIER_1_TITLES:
        if t in title_lower:
            return 100
    
    # Check tier 2
    for t in TIER_2_TITLES:
        if t in title_lower:
            return 75
    
    # Check tier 3
    for t in TIER_3_TITLES:
        if t in title_lower:
            return 50
    
    # Unknown but has a title
    return 25


def get_title_tier(title: str) -> str:
    """Get the tier name for a title."""
    score = compute_title_relevance_score(title)
    if score >= 100:
        return "TIER_1"
    elif score >= 75:
        return "TIER_2"
    elif score >= 50:
        return "TIER_3"
    elif score > 0:
        return "OTHER"
    return "NONE"


# =============================================================================
# LEADERSHIP PAGE PARSING
# =============================================================================

class LeadershipPageParser(HTMLParser):
    """Extract leadership information from HTML."""
    
    def __init__(self):
        super().__init__()
        self.leaders: List[Dict[str, str]] = []
        self._current_tag = ""
        self._text_buffer = []
        self._in_leadership_section = False
        self._potential_names: List[str] = []
        self._potential_titles: List[str] = []
    
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        self._current_tag = tag
        attrs_dict = dict(attrs)
        
        # Track leadership sections
        class_attr = (attrs_dict.get("class", "") + " " + attrs_dict.get("id", "")).lower()
        if any(kw in class_attr for kw in ["leadership", "team", "executive", "management", "staff", "about"]):
            self._in_leadership_section = True
    
    def handle_endtag(self, tag: str):
        if tag in ("div", "section", "article"):
            self._in_leadership_section = False
        self._current_tag = ""
    
    def handle_data(self, data: str):
        text = data.strip()
        if not text:
            return
        
        # Look for title patterns
        title_patterns = [
            r'\b(president|owner|ceo|founder|managing\s+member)\b',
            r'\b(contracts?\s+manager|compliance\s+(manager|director|officer))\b',
            r'\b(quality\s+(manager|director)|operations\s+(manager|director))\b',
            r'\b(chief\s+executive|chief\s+operations|chief\s+compliance)\b',
        ]
        
        text_lower = text.lower()
        
        for pattern in title_patterns:
            if re.search(pattern, text_lower, re.I):
                self._potential_titles.append(text)
        
        # Look for name patterns (capitalized words that look like names)
        if self._in_leadership_section or self._current_tag in ("h1", "h2", "h3", "h4", "strong", "b"):
            name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$'
            if re.match(name_pattern, text) and len(text) > 5 and len(text) < 50:
                self._potential_names.append(text)


def _fetch_page(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a web page respecting robots.txt."""
    try:
        # Check robots.txt
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                robots = resp.read().decode("utf-8", errors="replace").lower()
                if "disallow: /" in robots and "allow:" not in robots:
                    return None
        except Exception:
            pass
        
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read(500_000).decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None


# =============================================================================
# DECISION MAKER EXTRACTION
# =============================================================================

@dataclass
class ExtractedDecisionMaker:
    """Extracted decision maker information."""
    name: Optional[str] = None
    title: Optional[str] = None
    relevance_score: int = 0
    tier: str = "NONE"
    source_url: str = ""
    confidence: float = 0.0
    
    def is_valid(self) -> bool:
        return bool(self.name and self.title)


# Title keywords to search for in page content
TITLE_KEYWORDS = [
    ("president", "president"),
    ("owner", "owner"),
    ("ceo", "ceo"),
    ("chief executive", "ceo"),
    ("founder", "founder"),
    ("managing member", "managing_member"),
    ("contracts manager", "contracts_manager"),
    ("contract manager", "contracts_manager"),
    ("compliance manager", "compliance_manager"),
    ("compliance officer", "compliance_manager"),
    ("quality manager", "quality_manager"),
    ("quality director", "quality_manager"),
    ("operations manager", "operations_manager"),
]


def extract_decision_makers_from_page(url: str) -> List[ExtractedDecisionMaker]:
    """
    Extract decision maker information from a page.
    
    Returns list of potential decision makers found.
    """
    results = []
    
    html = _fetch_page(url)
    if not html:
        return results
    
    html_lower = html.lower()
    
    # Look for patterns like "Name, Title" or "Title: Name"
    for keyword, field_name in TITLE_KEYWORDS:
        if keyword not in html_lower:
            continue
        
        # Pattern 1: "Name, Title" or "Name - Title"
        pattern1 = rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)[,\-–]\s*({keyword}[^<\n]*)'
        matches1 = re.findall(pattern1, html, re.I)
        
        for name, title in matches1:
            name = name.strip()
            title = title.strip()[:100]
            if len(name) > 3 and len(name) < 50:
                dm = ExtractedDecisionMaker(
                    name=name,
                    title=title,
                    relevance_score=compute_title_relevance_score(title),
                    tier=get_title_tier(title),
                    source_url=url,
                    confidence=0.75,
                )
                results.append(dm)
        
        # Pattern 2: "Title: Name" or "Title - Name"
        pattern2 = rf'({keyword}[^:–\-<\n]*)[:–\-]\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)'
        matches2 = re.findall(pattern2, html, re.I)
        
        for title, name in matches2:
            name = name.strip()
            title = title.strip()[:100]
            if len(name) > 3 and len(name) < 50:
                dm = ExtractedDecisionMaker(
                    name=name,
                    title=title,
                    relevance_score=compute_title_relevance_score(title),
                    tier=get_title_tier(title),
                    source_url=url,
                    confidence=0.70,
                )
                results.append(dm)
    
    # Deduplicate by name
    seen_names = set()
    unique_results = []
    for dm in results:
        name_lower = dm.name.lower() if dm.name else ""
        if name_lower and name_lower not in seen_names:
            seen_names.add(name_lower)
            unique_results.append(dm)
    
    # Sort by relevance score
    unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
    
    return unique_results


def discover_decision_makers(website: str) -> Dict[str, Any]:
    """
    Discover decision makers from a company website.
    
    Checks homepage, about page, leadership page, and contact page.
    Returns comprehensive decision maker evidence.
    """
    result = {
        "decision_makers": [],
        "best_decision_maker": None,
        "leadership_count": 0,
        "organization_type": None,
        "sources_checked": [],
    }
    
    if not website:
        return result
    
    # Normalize
    if not website.startswith("http"):
        website = "https://" + website
    
    parsed = urllib.parse.urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    # Pages to check
    pages_to_check = [
        (base + "/about", "about"),
        (base + "/about-us", "about"),
        (base + "/about/team", "leadership"),
        (base + "/about/leadership", "leadership"),
        (base + "/team", "leadership"),
        (base + "/leadership", "leadership"),
        (base + "/our-team", "leadership"),
        (base + "/management", "leadership"),
        (base + "/company", "about"),
        (website, "homepage"),
    ]
    
    all_decision_makers: List[ExtractedDecisionMaker] = []
    
    for url, page_type in pages_to_check:
        result["sources_checked"].append(url)
        
        dms = extract_decision_makers_from_page(url)
        all_decision_makers.extend(dms)
        
        # Rate limit
        time.sleep(0.3)
        
        # Stop if we found enough
        if len(all_decision_makers) >= 5:
            break
    
    # Deduplicate across all sources
    seen_names = set()
    unique_dms = []
    for dm in all_decision_makers:
        name_lower = dm.name.lower() if dm.name else ""
        if name_lower and name_lower not in seen_names:
            seen_names.add(name_lower)
            unique_dms.append(dm)
    
    # Sort by relevance
    unique_dms.sort(key=lambda x: x.relevance_score, reverse=True)
    
    result["decision_makers"] = [
        {
            "name": dm.name,
            "title": dm.title,
            "relevance_score": dm.relevance_score,
            "tier": dm.tier,
            "source_url": dm.source_url,
            "confidence": dm.confidence,
        }
        for dm in unique_dms[:10]
    ]
    
    result["leadership_count"] = len(unique_dms)
    
    if unique_dms:
        result["best_decision_maker"] = result["decision_makers"][0]
    
    # Determine organization type from clues
    all_text = " ".join([dm.title or "" for dm in unique_dms]).lower()
    if "llc" in all_text or "managing member" in all_text:
        result["organization_type"] = "LLC"
    elif "inc" in all_text or "ceo" in all_text or "president" in all_text:
        result["organization_type"] = "Corporation"
    elif "sole" in all_text or "owner" in all_text:
        result["organization_type"] = "Sole Proprietorship"
    
    return result


# =============================================================================
# DECISION MAKER ENRICHMENT
# =============================================================================

@dataclass
class DecisionMakerEnrichmentResult:
    """Result of decision maker enrichment."""
    record_id: str
    company_name: str
    success: bool = True
    
    # Discovery results
    decision_makers_found: int = 0
    best_decision_maker_name: Optional[str] = None
    best_decision_maker_title: Optional[str] = None
    relevance_score: int = 0
    tier: str = "NONE"
    source_url: Optional[str] = None
    confidence: float = 0.0
    
    # Before/after
    had_decision_maker_before: bool = False
    
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "company_name": self.company_name,
            "success": self.success,
            "decision_makers_found": self.decision_makers_found,
            "best_decision_maker": {
                "name": self.best_decision_maker_name,
                "title": self.best_decision_maker_title,
                "relevance_score": self.relevance_score,
                "tier": self.tier,
            } if self.best_decision_maker_name else None,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "errors": self.errors,
        }


def enrich_decision_maker_intelligence(
    record: CustomerIntelligenceRecord,
    pause_seconds: float = 0.5,
) -> DecisionMakerEnrichmentResult:
    """
    Enrich a record with decision maker intelligence.
    
    NO OUTREACH. NO EMAILS. EVIDENCE ONLY.
    """
    result = DecisionMakerEnrichmentResult(
        record_id=record.record_id,
        company_name=record.company_name.value or "Unknown",
    )
    
    result.had_decision_maker_before = record.decision_maker_name.state == SignalState.KNOWN
    
    # Need website to discover
    website = record.website.value if record.website.state == SignalState.KNOWN else None
    
    if not website:
        result.errors.append("No website to discover decision makers from")
        return result
    
    # Discover decision makers
    try:
        discovery = discover_decision_makers(website)
    except Exception as e:
        result.success = False
        result.errors.append(f"Discovery failed: {str(e)[:100]}")
        return result
    
    result.decision_makers_found = discovery.get("leadership_count", 0)
    
    best_dm = discovery.get("best_decision_maker")
    if best_dm:
        result.best_decision_maker_name = best_dm.get("name")
        result.best_decision_maker_title = best_dm.get("title")
        result.relevance_score = best_dm.get("relevance_score", 0)
        result.tier = best_dm.get("tier", "NONE")
        result.source_url = best_dm.get("source_url")
        result.confidence = best_dm.get("confidence", 0.0)
        
        # Update record
        if record.decision_maker_name.state == SignalState.UNKNOWN:
            record.decision_maker_name = EvidencedValue(
                value=best_dm.get("name"),
                source=f"Website Discovery: {best_dm.get('source_url', website)}",
                confidence=best_dm.get("confidence", 0.7),
                state=SignalState.KNOWN,
            )
        
        if record.decision_maker_title.state == SignalState.UNKNOWN:
            record.decision_maker_title = EvidencedValue(
                value=best_dm.get("title"),
                source=f"Website Discovery: {best_dm.get('source_url', website)}",
                confidence=best_dm.get("confidence", 0.7),
                state=SignalState.KNOWN,
            )
        
        if record.decision_maker_source.state == SignalState.UNKNOWN:
            record.decision_maker_source = EvidencedValue(
                value=best_dm.get("source_url"),
                source="Website Discovery",
                confidence=0.9,
                state=SignalState.KNOWN,
            )
        
        # Populate specific role fields based on title
        title_lower = (best_dm.get("title") or "").lower()
        
        if "president" in title_lower and record.president_name.state == SignalState.UNKNOWN:
            record.president_name = EvidencedValue(
                value=best_dm.get("name"),
                source=f"Website Discovery: {best_dm.get('source_url', website)}",
                confidence=best_dm.get("confidence", 0.7),
                state=SignalState.KNOWN,
            )
        
        if "owner" in title_lower and record.owner_name.state == SignalState.UNKNOWN:
            record.owner_name = EvidencedValue(
                value=best_dm.get("name"),
                source=f"Website Discovery: {best_dm.get('source_url', website)}",
                confidence=best_dm.get("confidence", 0.7),
                state=SignalState.KNOWN,
            )
        
        if ("ceo" in title_lower or "chief executive" in title_lower) and record.ceo_name.state == SignalState.UNKNOWN:
            record.ceo_name = EvidencedValue(
                value=best_dm.get("name"),
                source=f"Website Discovery: {best_dm.get('source_url', website)}",
                confidence=best_dm.get("confidence", 0.7),
                state=SignalState.KNOWN,
            )
        
        if "founder" in title_lower and record.founder_name.state == SignalState.UNKNOWN:
            record.founder_name = EvidencedValue(
                value=best_dm.get("name"),
                source=f"Website Discovery: {best_dm.get('source_url', website)}",
                confidence=best_dm.get("confidence", 0.7),
                state=SignalState.KNOWN,
            )
    
    # Update leadership count
    if discovery.get("leadership_count"):
        record.leadership_count = EvidencedValue(
            value=discovery["leadership_count"],
            source="Website Discovery",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
    
    # Update organization type
    if discovery.get("organization_type") and record.organization_type.state == SignalState.UNKNOWN:
        record.organization_type = EvidencedValue(
            value=discovery["organization_type"],
            source="Website Discovery",
            confidence=0.6,
            state=SignalState.KNOWN,
        )
    
    # Save
    save_intelligence_record(record)
    
    return result


def enrich_all_decision_maker_intelligence(
    limit: int = 50,
    only_with_website: bool = True,
    pause_between_records: float = 1.0,
) -> Dict[str, Any]:
    """
    Enrich all records with decision maker intelligence.
    
    NO OUTREACH. NO EMAILS. EVIDENCE ONLY.
    """
    records = get_all_intelligence_records()
    
    if only_with_website:
        records = [r for r in records if r.website.state == SignalState.KNOWN and r.website.value]
    
    # Prioritize records without decision maker info
    records.sort(
        key=lambda r: (
            r.decision_maker_name.state == SignalState.UNKNOWN,
            r.website.confidence if r.website.state == SignalState.KNOWN else 0,
        ),
        reverse=True,
    )
    
    results: List[DecisionMakerEnrichmentResult] = []
    
    for record in records[:limit]:
        result = enrich_decision_maker_intelligence(record, pause_seconds=0.5)
        results.append(result)
        
        if pause_between_records > 0:
            time.sleep(pause_between_records)
    
    # Summary
    dm_found = sum(1 for r in results if r.decision_makers_found > 0)
    tier_1_found = sum(1 for r in results if r.tier == "TIER_1")
    tier_2_found = sum(1 for r in results if r.tier == "TIER_2")
    
    return {
        "ok": True,
        "enriched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records_processed": len(results),
        "summary": {
            "decision_makers_found": dm_found,
            "tier_1_found": tier_1_found,
            "tier_2_found": tier_2_found,
        },
        "results": [r.to_dict() for r in results],
    }


# =============================================================================
# DECISION MAKER METRICS
# =============================================================================

def compute_decision_maker_metrics(
    records: Optional[List[CustomerIntelligenceRecord]] = None,
) -> Dict[str, int]:
    """
    Compute decision maker intelligence metrics.
    """
    if records is None:
        records = get_all_intelligence_records()
    
    metrics = {
        "decision_maker_entities": 0,
        "leadership_entities": 0,
        "procurement_relevant_entities": 0,
        "decision_maker_ready_entities": 0,
        "tier_1_decision_makers": 0,
        "tier_2_decision_makers": 0,
        "tier_3_decision_makers": 0,
    }
    
    for r in records:
        dm_name_known = r.decision_maker_name.state == SignalState.KNOWN and r.decision_maker_name.value
        dm_title_known = r.decision_maker_title.state == SignalState.KNOWN and r.decision_maker_title.value
        email_known = r.contact_email.state == SignalState.KNOWN and r.contact_email.value
        leadership_known = r.leadership_count.state == SignalState.KNOWN and r.leadership_count.value
        
        if dm_name_known:
            metrics["decision_maker_entities"] += 1
        
        if leadership_known:
            metrics["leadership_entities"] += 1
        
        # Compute relevance score
        if dm_title_known:
            title = r.decision_maker_title.value
            score = compute_title_relevance_score(title)
            tier = get_title_tier(title)
            
            if score >= 50:
                metrics["procurement_relevant_entities"] += 1
            
            if tier == "TIER_1":
                metrics["tier_1_decision_makers"] += 1
            elif tier == "TIER_2":
                metrics["tier_2_decision_makers"] += 1
            elif tier == "TIER_3":
                metrics["tier_3_decision_makers"] += 1
        
        # DECISION_MAKER_READY: dm_name + dm_title + email + high confidence
        if dm_name_known and dm_title_known and email_known:
            dm_confidence = r.decision_maker_name.confidence
            email_confidence = r.contact_email.confidence
            avg_confidence = (dm_confidence + email_confidence) / 2
            
            if avg_confidence >= 0.70:
                metrics["decision_maker_ready_entities"] += 1
    
    return metrics


# =============================================================================
# DECISION MAKER RECOMMENDATION
# =============================================================================

class DecisionMakerRecommendation(str):
    DECISION_MAKER_READY = "DECISION_MAKER_READY"
    CONTACT_READY = "CONTACT_READY"
    CONTACTABLE = "CONTACTABLE"
    ENRICH = "ENRICH"
    WATCH = "WATCH"
    IGNORE = "IGNORE"


def compute_decision_maker_recommendation(
    record: CustomerIntelligenceRecord,
    icp_match: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Compute recommendation based on decision maker intelligence.
    
    DECISION_MAKER_READY requires:
    - decision_maker_name = KNOWN
    - decision_maker_title = KNOWN
    - contact_email = KNOWN
    - confidence >= 0.70
    """
    if icp_match is None:
        icp_match = evaluate_icp_match(record)
    
    dm_name_known = record.decision_maker_name.state == SignalState.KNOWN and record.decision_maker_name.value
    dm_title_known = record.decision_maker_title.state == SignalState.KNOWN and record.decision_maker_title.value
    email_known = record.contact_email.state == SignalState.KNOWN and record.contact_email.value
    
    dm_confidence = record.decision_maker_name.confidence if dm_name_known else 0.0
    email_confidence = record.contact_email.confidence if email_known else 0.0
    
    # DECISION_MAKER_READY
    if dm_name_known and dm_title_known and email_known:
        avg_confidence = (dm_confidence + email_confidence) / 2
        if avg_confidence >= 0.70:
            title = record.decision_maker_title.value
            tier = get_title_tier(title)
            return (
                DecisionMakerRecommendation.DECISION_MAKER_READY,
                f"Decision maker {tier}: {title} with verified email ({avg_confidence:.0%} confidence)",
            )
        else:
            return (
                DecisionMakerRecommendation.CONTACT_READY,
                f"Decision maker identified but lower confidence ({avg_confidence:.0%})",
            )
    
    # Has email but no decision maker
    if email_known:
        if email_confidence >= 0.70:
            return (
                DecisionMakerRecommendation.CONTACTABLE,
                "Email verified, decision maker not yet identified",
            )
        else:
            return (
                DecisionMakerRecommendation.CONTACTABLE,
                f"Email found, lower confidence ({email_confidence:.0%})",
            )
    
    # Has website to enrich
    website_known = record.website.state == SignalState.KNOWN and record.website.value
    if website_known:
        return (
            DecisionMakerRecommendation.ENRICH,
            "Has website, contact and decision maker not yet discovered",
        )
    
    # Fall back to ICP
    tier = icp_match.get("tier", "NO_MATCH")
    if tier in ["TIER_1", "TIER_2"]:
        return (
            DecisionMakerRecommendation.WATCH,
            f"{tier} prospect without contact info",
        )
    elif tier == "TIER_3":
        return (
            DecisionMakerRecommendation.WATCH,
            "Standard prospect, needs enrichment",
        )
    
    return (
        DecisionMakerRecommendation.IGNORE,
        "Does not match ICP criteria",
    )


# =============================================================================
# TOP PROCUREMENT RELEVANT REPORT
# =============================================================================

def generate_procurement_relevant_report(limit: int = 20) -> Dict[str, Any]:
    """
    Generate report of companies ranked by procurement relevance.
    
    Shows who specifically we should contact with supporting evidence.
    """
    records = get_all_intelligence_records()
    
    ranked = []
    
    for record in records:
        icp_match = evaluate_icp_match(record)
        recommendation, reasoning = compute_decision_maker_recommendation(record, icp_match)
        
        dm_name = record.decision_maker_name.value if record.decision_maker_name.state == SignalState.KNOWN else None
        dm_title = record.decision_maker_title.value if record.decision_maker_title.state == SignalState.KNOWN else None
        email = record.contact_email.value if record.contact_email.state == SignalState.KNOWN else None
        website = record.website.value if record.website.state == SignalState.KNOWN else None
        contract_value = record.contract_value.value if record.contract_value.state == SignalState.KNOWN else None
        dod_exposure = record.dod_exposure.value if record.dod_exposure.state == SignalState.KNOWN else None
        
        # Compute procurement relevance score for ranking
        score = 0
        
        if recommendation == DecisionMakerRecommendation.DECISION_MAKER_READY:
            score += 1000
        elif recommendation == DecisionMakerRecommendation.CONTACT_READY:
            score += 800
        elif recommendation == DecisionMakerRecommendation.CONTACTABLE:
            score += 500
        
        # Title relevance
        if dm_title:
            score += compute_title_relevance_score(dm_title) * 5
        
        # Email adds value
        if email:
            score += 200
        
        # ICP tier
        tier_scores = {"TIER_1": 300, "TIER_2": 200, "TIER_3": 100}
        score += tier_scores.get(icp_match.get("tier", "NO_MATCH"), 0)
        
        # Contract value adds credibility
        if contract_value and contract_value > 0:
            score += min(100, contract_value / 10000)
        
        # DoD exposure is valuable
        if dod_exposure:
            score += 150
        
        # Determine missing evidence
        missing = []
        if not dm_name:
            missing.append("decision_maker_name")
        if not dm_title:
            missing.append("decision_maker_title")
        if not email:
            missing.append("contact_email")
        if not website:
            missing.append("website")
        
        ranked.append({
            "record_id": record.record_id,
            "company": record.company_name.value,
            "decision_maker": dm_name,
            "title": dm_title,
            "title_tier": get_title_tier(dm_title) if dm_title else "NONE",
            "contact_email": email,
            "website": website,
            "contract_value": contract_value,
            "dod_exposure": dod_exposure,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "missing_evidence": missing,
            "score": score,
        })
    
    # Sort by score
    ranked.sort(key=lambda x: x["score"], reverse=True)
    
    # Get metrics
    metrics = compute_decision_maker_metrics(records)
    
    return {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_records": len(records),
        "metrics": metrics,
        "top_procurement_relevant": ranked[:limit],
        "organism_answer": {
            "question": "Who specifically should we contact?",
            "answer": ranked[0] if ranked else None,
            "evidence": {
                "decision_maker": ranked[0].get("decision_maker") if ranked else None,
                "title": ranked[0].get("title") if ranked else None,
                "email": ranked[0].get("contact_email") if ranked else None,
                "recommendation": ranked[0].get("recommendation") if ranked else None,
            } if ranked else None,
        },
    }

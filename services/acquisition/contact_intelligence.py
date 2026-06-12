"""PATCH 13A-18: Contact Intelligence Engine.

Collects contact evidence from public sources.

NO OUTREACH. NO EMAILS. NO AUTO-CONTACT.
ONLY EVIDENCE COLLECTION.

Source Priority:
1. Company website
2. Contact page
3. Leadership page
4. About page
5. Public business registry
6. SAM.gov if available

NEVER:
- fabricate emails
- infer names
- invent phone numbers
- create synthetic confidence
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
from .enrichment import compute_enrichment_score, Recommendation

logger = logging.getLogger(__name__)

USER_AGENT = "KeepYourContracts-ContactDiscovery/1.0 (+https://compliance.keepyourcontracts.com; lawful-public-research)"


# =============================================================================
# HTML PARSING HELPERS
# =============================================================================

class ContactPageParser(HTMLParser):
    """Extract contact information from HTML."""
    
    def __init__(self):
        super().__init__()
        self.emails: List[str] = []
        self.phones: List[str] = []
        self.names: List[Tuple[str, str]] = []  # (name, title)
        self.links: Dict[str, str] = {}  # href -> text
        self._current_tag = ""
        self._current_attrs = {}
        self._text_buffer = []
        self._in_leadership = False
        self._in_about = False
    
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        self._current_tag = tag
        self._current_attrs = dict(attrs)
        
        # Check for mailto links
        if tag == "a":
            href = self._current_attrs.get("href", "")
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if email and "@" in email:
                    self.emails.append(email)
            elif href.startswith("tel:"):
                phone = href.replace("tel:", "").strip()
                if phone:
                    self.phones.append(phone)
        
        # Track sections
        class_attr = self._current_attrs.get("class", "")
        id_attr = self._current_attrs.get("id", "")
        
        if any(kw in (class_attr + id_attr).lower() for kw in ["leadership", "team", "executive", "management"]):
            self._in_leadership = True
        if any(kw in (class_attr + id_attr).lower() for kw in ["about", "contact"]):
            self._in_about = True
    
    def handle_endtag(self, tag: str):
        self._current_tag = ""
    
    def handle_data(self, data: str):
        text = data.strip()
        if not text:
            return
        
        # Look for email patterns in text
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        for email in re.findall(email_pattern, text):
            if email not in self.emails:
                self.emails.append(email)
        
        # Look for phone patterns
        phone_patterns = [
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',  # 123-456-7890
        ]
        for pattern in phone_patterns:
            for phone in re.findall(pattern, text):
                clean_phone = re.sub(r'[^\d]', '', phone)
                if len(clean_phone) >= 10 and clean_phone not in [re.sub(r'[^\d]', '', p) for p in self.phones]:
                    self.phones.append(phone)


def _fetch_page(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a web page respecting robots.txt."""
    try:
        # Check robots.txt first
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        try:
            req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                robots = resp.read().decode("utf-8", errors="replace").lower()
                if "disallow: /" in robots and "allow:" not in robots:
                    logger.info("robots.txt disallows: %s", url)
                    return None
        except Exception:
            pass  # If can't fetch robots.txt, proceed
        
        # Fetch the page
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read(500_000).decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
        return None


def _normalize_url(base_url: str, href: str) -> str:
    """Normalize a relative URL to absolute."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        parsed = urllib.parse.urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    return urllib.parse.urljoin(base_url, href)


# =============================================================================
# CONTACT PAGE DISCOVERY
# =============================================================================

CONTACT_PAGE_PATHS = [
    "/contact",
    "/contact-us",
    "/contact.html",
    "/contactus",
    "/about/contact",
    "/company/contact",
]

LEADERSHIP_PAGE_PATHS = [
    "/about",
    "/about-us",
    "/about/team",
    "/about/leadership",
    "/team",
    "/leadership",
    "/our-team",
    "/management",
    "/company/about",
    "/company/leadership",
]


def discover_contact_pages(website: str) -> Dict[str, Optional[str]]:
    """
    Discover contact and leadership pages from a website.
    
    Returns dict with discovered URLs.
    """
    result = {
        "contact_page": None,
        "leadership_page": None,
        "about_page": None,
    }
    
    if not website:
        return result
    
    # Normalize website URL
    if not website.startswith("http"):
        website = "https://" + website
    
    parsed = urllib.parse.urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    # Try contact pages
    for path in CONTACT_PAGE_PATHS:
        url = base + path
        html = _fetch_page(url)
        if html and len(html) > 500:
            result["contact_page"] = url
            break
    
    # Try leadership/about pages
    for path in LEADERSHIP_PAGE_PATHS:
        url = base + path
        html = _fetch_page(url)
        if html and len(html) > 500:
            if "leadership" in path or "team" in path or "management" in path:
                result["leadership_page"] = url
            else:
                result["about_page"] = url
            if result["leadership_page"]:
                break
    
    return result


# =============================================================================
# CONTACT EXTRACTION
# =============================================================================

@dataclass
class ExtractedContact:
    """Extracted contact information from a page."""
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    source_url: str = ""
    confidence: float = 0.0
    
    def is_valid(self) -> bool:
        return bool(self.email or self.phone)


def extract_contacts_from_page(url: str) -> ExtractedContact:
    """
    Extract contact information from a single page.
    
    Returns the best contact found.
    """
    result = ExtractedContact(source_url=url)
    
    html = _fetch_page(url)
    if not html:
        return result
    
    parser = ContactPageParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    
    # Get best email (prefer info@, contact@, sales@)
    if parser.emails:
        priority_prefixes = ["info@", "contact@", "sales@", "hello@", "inquiries@"]
        
        for prefix in priority_prefixes:
            for email in parser.emails:
                if email.lower().startswith(prefix):
                    result.email = email
                    result.confidence = 0.85
                    break
            if result.email:
                break
        
        if not result.email:
            result.email = parser.emails[0]
            result.confidence = 0.70
    
    # Get phone
    if parser.phones:
        result.phone = parser.phones[0]
        if not result.confidence:
            result.confidence = 0.65
    
    return result


def extract_contacts_from_website(website: str) -> Dict[str, Any]:
    """
    Extract all contact information from a company website.
    
    Checks homepage, contact page, and leadership page.
    Returns comprehensive contact evidence.
    """
    result = {
        "email": None,
        "phone": None,
        "name": None,
        "title": None,
        "source_url": None,
        "contact_page_url": None,
        "leadership_page_url": None,
        "confidence": 0.0,
        "sources_checked": [],
    }
    
    if not website:
        return result
    
    # Normalize website URL
    if not website.startswith("http"):
        website = "https://" + website
    
    # Discover pages
    pages = discover_contact_pages(website)
    result["contact_page_url"] = pages.get("contact_page")
    result["leadership_page_url"] = pages.get("leadership_page")
    
    # URLs to check in priority order
    urls_to_check = []
    
    # Contact page first (highest priority)
    if pages.get("contact_page"):
        urls_to_check.append(("contact_page", pages["contact_page"]))
    
    # Homepage
    urls_to_check.append(("homepage", website))
    
    # About/Leadership page
    if pages.get("leadership_page"):
        urls_to_check.append(("leadership_page", pages["leadership_page"]))
    if pages.get("about_page"):
        urls_to_check.append(("about_page", pages["about_page"]))
    
    # Extract from each page
    for source_type, url in urls_to_check:
        result["sources_checked"].append(url)
        
        contact = extract_contacts_from_page(url)
        
        # Take best email found
        if contact.email and not result["email"]:
            result["email"] = contact.email
            result["source_url"] = url
            result["confidence"] = max(result["confidence"], contact.confidence)
        
        # Take best phone found
        if contact.phone and not result["phone"]:
            result["phone"] = contact.phone
            if not result["source_url"]:
                result["source_url"] = url
            result["confidence"] = max(result["confidence"], contact.confidence)
        
        # Rate limit
        time.sleep(0.5)
    
    return result


# =============================================================================
# CONTACT INTELLIGENCE ENRICHMENT
# =============================================================================

@dataclass
class ContactEnrichmentResult:
    """Result of contact intelligence enrichment."""
    record_id: str
    company_name: str
    success: bool = True
    
    # Before state
    had_email_before: bool = False
    had_phone_before: bool = False
    had_contact_name_before: bool = False
    
    # After state
    email_found: bool = False
    phone_found: bool = False
    contact_name_found: bool = False
    
    # Contact data
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    source_url: Optional[str] = None
    contact_page_url: Optional[str] = None
    leadership_page_url: Optional[str] = None
    confidence: float = 0.0
    
    # Metrics
    contactability_before: int = 0
    contactability_after: int = 0
    
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "company_name": self.company_name,
            "success": self.success,
            "contact_found": self.email_found or self.phone_found,
            "email": self.email,
            "phone": self.phone,
            "contact_name": self.contact_name,
            "contact_title": self.contact_title,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "contactability_delta": self.contactability_after - self.contactability_before,
            "errors": self.errors,
        }


def enrich_contact_intelligence(
    record: CustomerIntelligenceRecord,
    pause_seconds: float = 0.5,
) -> ContactEnrichmentResult:
    """
    Enrich a single record with contact intelligence.
    
    NO OUTREACH. NO EMAILS. ONLY EVIDENCE COLLECTION.
    """
    result = ContactEnrichmentResult(
        record_id=record.record_id,
        company_name=record.company_name.value or "Unknown",
    )
    
    # Capture before state
    result.had_email_before = record.contact_email.state == SignalState.KNOWN
    result.had_phone_before = record.contact_phone.state == SignalState.KNOWN
    result.had_contact_name_before = record.contact_name.state == SignalState.KNOWN
    result.contactability_before = record.compute_contactability()
    
    # Check if website is known
    website = record.website.value if record.website.state == SignalState.KNOWN else None
    
    if not website:
        result.success = True
        result.errors.append("No website to discover contacts from")
        return result
    
    # Extract contacts
    try:
        contacts = extract_contacts_from_website(website)
    except Exception as e:
        result.success = False
        result.errors.append(f"Contact extraction failed: {str(e)[:100]}")
        return result
    
    # Update record with discovered contact info
    if contacts.get("email") and record.contact_email.state == SignalState.UNKNOWN:
        record.contact_email = EvidencedValue(
            value=contacts["email"],
            source=f"Website Contact Discovery: {contacts.get('source_url', website)}",
            confidence=contacts.get("confidence", 0.7),
            state=SignalState.KNOWN,
        )
        result.email_found = True
        result.email = contacts["email"]
    
    if contacts.get("phone") and record.contact_phone.state == SignalState.UNKNOWN:
        record.contact_phone = EvidencedValue(
            value=contacts["phone"],
            source=f"Website Contact Discovery: {contacts.get('source_url', website)}",
            confidence=contacts.get("confidence", 0.65),
            state=SignalState.KNOWN,
        )
        result.phone_found = True
        result.phone = contacts["phone"]
    
    if contacts.get("contact_page_url") and record.contact_source_url.state == SignalState.UNKNOWN:
        record.contact_source_url = EvidencedValue(
            value=contacts["contact_page_url"],
            source="Website Discovery",
            confidence=0.9,
            state=SignalState.KNOWN,
        )
        result.contact_page_url = contacts["contact_page_url"]
    
    if contacts.get("leadership_page_url") and record.leadership_page_url.state == SignalState.UNKNOWN:
        record.leadership_page_url = EvidencedValue(
            value=contacts["leadership_page_url"],
            source="Website Discovery",
            confidence=0.9,
            state=SignalState.KNOWN,
        )
        result.leadership_page_url = contacts["leadership_page_url"]
    
    result.source_url = contacts.get("source_url")
    result.confidence = contacts.get("confidence", 0.0)
    
    # Recompute contactability
    record.contactability_score = EvidencedValue(
        value=record.compute_contactability(),
        source="computed",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    # Save
    save_intelligence_record(record)
    
    result.contactability_after = record.compute_contactability()
    
    return result


def enrich_all_contact_intelligence(
    limit: int = 50,
    only_with_website: bool = True,
    pause_between_records: float = 1.0,
) -> Dict[str, Any]:
    """
    Enrich all records with contact intelligence.
    
    NO OUTREACH. NO EMAILS. ONLY EVIDENCE COLLECTION.
    """
    records = get_all_intelligence_records()
    
    # Filter to records with websites if requested
    if only_with_website:
        records = [r for r in records if r.website.state == SignalState.KNOWN and r.website.value]
    
    # Also prioritize records without existing contact info
    records.sort(
        key=lambda r: (
            r.contact_email.state == SignalState.UNKNOWN,  # Unknown first
            r.website.confidence if r.website.state == SignalState.KNOWN else 0,
        ),
        reverse=True,
    )
    
    results: List[ContactEnrichmentResult] = []
    
    for record in records[:limit]:
        result = enrich_contact_intelligence(record, pause_seconds=0.5)
        results.append(result)
        
        if pause_between_records > 0:
            time.sleep(pause_between_records)
    
    # Summary statistics
    contacts_found = sum(1 for r in results if r.email_found or r.phone_found)
    emails_found = sum(1 for r in results if r.email_found)
    phones_found = sum(1 for r in results if r.phone_found)
    
    return {
        "ok": True,
        "enriched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records_processed": len(results),
        "summary": {
            "contacts_found": contacts_found,
            "emails_found": emails_found,
            "phones_found": phones_found,
        },
        "results": [r.to_dict() for r in results],
    }


# =============================================================================
# CONTACT METRICS
# =============================================================================

def compute_contact_metrics(records: Optional[List[CustomerIntelligenceRecord]] = None) -> Dict[str, int]:
    """
    Compute contact intelligence metrics.
    
    Returns:
    - contactable_entities: Records with email AND (name OR title)
    - decision_maker_entities: Records with name AND title
    - email_known_entities: Records with known email
    - phone_known_entities: Records with known phone
    - leadership_known_entities: Records with leadership page
    """
    if records is None:
        records = get_all_intelligence_records()
    
    metrics = {
        "contactable_entities": 0,
        "decision_maker_entities": 0,
        "email_known_entities": 0,
        "phone_known_entities": 0,
        "leadership_known_entities": 0,
        "contact_ready_entities": 0,
    }
    
    for r in records:
        email_known = r.contact_email.state == SignalState.KNOWN and r.contact_email.value
        phone_known = r.contact_phone.state == SignalState.KNOWN and r.contact_phone.value
        name_known = r.contact_name.state == SignalState.KNOWN and r.contact_name.value
        title_known = r.contact_title.state == SignalState.KNOWN and r.contact_title.value
        leadership_known = r.leadership_page_url.state == SignalState.KNOWN and r.leadership_page_url.value
        
        if email_known:
            metrics["email_known_entities"] += 1
        
        if phone_known:
            metrics["phone_known_entities"] += 1
        
        if email_known and (name_known or title_known):
            metrics["contactable_entities"] += 1
        
        if name_known and title_known:
            metrics["decision_maker_entities"] += 1
        
        if leadership_known:
            metrics["leadership_known_entities"] += 1
        
        # CONTACT_READY: email known AND (name OR title) AND confidence >= 0.70
        if email_known and (name_known or title_known):
            confidence = r.contact_email.confidence
            if confidence >= 0.70:
                metrics["contact_ready_entities"] += 1
    
    return metrics


# =============================================================================
# CONTACT RECOMMENDATIONS
# =============================================================================

class ContactRecommendation(str):
    CONTACT_READY = "CONTACT_READY"
    CONTACTABLE = "CONTACTABLE"
    ENRICH = "ENRICH"
    WATCH = "WATCH"
    IGNORE = "IGNORE"


def compute_contact_recommendation(
    record: CustomerIntelligenceRecord,
    icp_match: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Compute contact recommendation based on contact intelligence.
    
    CONTACT_READY requires:
    - contact_email = KNOWN
    - contact_name OR contact_title = KNOWN
    - confidence >= 0.70
    
    Returns (recommendation, reasoning)
    """
    if icp_match is None:
        icp_match = evaluate_icp_match(record)
    
    email_known = record.contact_email.state == SignalState.KNOWN and record.contact_email.value
    phone_known = record.contact_phone.state == SignalState.KNOWN and record.contact_phone.value
    name_known = record.contact_name.state == SignalState.KNOWN and record.contact_name.value
    title_known = record.contact_title.state == SignalState.KNOWN and record.contact_title.value
    
    email_confidence = record.contact_email.confidence if email_known else 0.0
    
    # CONTACT_READY: email + (name or title) + high confidence
    if email_known and (name_known or title_known) and email_confidence >= 0.70:
        return ContactRecommendation.CONTACT_READY, "Email and contact identity verified with high confidence"
    
    # CONTACTABLE: email known
    if email_known:
        if email_confidence >= 0.70:
            return ContactRecommendation.CONTACTABLE, "Email verified, missing contact name/title"
        else:
            return ContactRecommendation.CONTACTABLE, f"Email found but lower confidence ({email_confidence:.0%})"
    
    # Check if we have a website to enrich from
    website_known = record.website.state == SignalState.KNOWN and record.website.value
    
    if website_known:
        return ContactRecommendation.ENRICH, "Has website, contact not yet discovered"
    
    # Fall back to ICP-based recommendation
    tier = icp_match.get("tier", "NO_MATCH")
    
    if tier in ["TIER_1", "TIER_2"]:
        return ContactRecommendation.WATCH, f"{tier} prospect without contact info or website"
    elif tier == "TIER_3":
        return ContactRecommendation.WATCH, "Standard prospect, needs enrichment"
    else:
        return ContactRecommendation.IGNORE, "Does not match ICP"


# =============================================================================
# TOP CONTACTABLE REPORT
# =============================================================================

def generate_top_contactable_report(limit: int = 20) -> Dict[str, Any]:
    """
    Generate report of top contactable companies.
    
    Ranks by:
    1. CONTACT_READY status
    2. Email confidence
    3. ICP tier
    """
    records = get_all_intelligence_records()
    
    # Score and rank
    ranked = []
    
    for record in records:
        icp_match = evaluate_icp_match(record)
        recommendation, reasoning = compute_contact_recommendation(record, icp_match)
        
        email_known = record.contact_email.state == SignalState.KNOWN and record.contact_email.value
        phone_known = record.contact_phone.state == SignalState.KNOWN and record.contact_phone.value
        name_known = record.contact_name.state == SignalState.KNOWN and record.contact_name.value
        title_known = record.contact_title.state == SignalState.KNOWN and record.contact_title.value
        
        # Score for sorting
        score = 0
        
        if recommendation == ContactRecommendation.CONTACT_READY:
            score += 1000
        elif recommendation == ContactRecommendation.CONTACTABLE:
            score += 500
        
        if email_known:
            score += 200 + (record.contact_email.confidence * 100)
        
        if phone_known:
            score += 50
        
        if name_known or title_known:
            score += 100
        
        tier_scores = {"TIER_1": 300, "TIER_2": 200, "TIER_3": 100, "NO_MATCH": 0}
        score += tier_scores.get(icp_match.get("tier", "NO_MATCH"), 0)
        
        ranked.append({
            "record_id": record.record_id,
            "company": record.company_name.value,
            "tier": icp_match.get("tier"),
            "contact_name": record.contact_name.value if name_known else None,
            "contact_title": record.contact_title.value if title_known else None,
            "contact_email": record.contact_email.value if email_known else None,
            "contact_phone": record.contact_phone.value if phone_known else None,
            "source_url": record.contact_source_url.value if record.contact_source_url.state == SignalState.KNOWN else None,
            "confidence": record.contact_email.confidence if email_known else 0.0,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "contactability_score": record.compute_contactability(),
            "score": score,
        })
    
    # Sort by score
    ranked.sort(key=lambda x: x["score"], reverse=True)
    
    # Get metrics
    metrics = compute_contact_metrics(records)
    
    return {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_records": len(records),
        "metrics": metrics,
        "top_contactable": ranked[:limit],
    }

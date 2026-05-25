"""Lawful public discovery — no LinkedIn scraping, no login bypass, no spam."""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from .intelligence_paths import MOCK_DOMAIN_BLOCKLIST, is_mock_domain
from .models import normalize_segment

logger = logging.getLogger(__name__)

USER_AGENT = "KeepYourContracts-LeadDiscovery/1.0 (+https://compliance.keepyourcontracts.com; lawful-public-research)"

USASPENDING_AUTOCOMPLETE = "https://api.usaspending.gov/api/v2/autocomplete/recipient/"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        t = data.strip()
        if t:
            self._chunks.append(t)

    def text(self) -> str:
        return " ".join(self._chunks)


def robots_allows_fetch(url: str, timeout: int = 8) -> bool:
    """Best-effort robots.txt check; default allow if unreachable."""
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace").lower()
        if "disallow: /" in body and "allow:" not in body:
            return False
        return True
    except Exception:
        return True


def discover_usaspending_recipients(search_text: str, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Public USASpending.gov API — federal award recipients (lawful, no key required for autocomplete).
    """
    if not search_text or len(search_text) < 2:
        return []
    payload = json.dumps({"search_text": search_text[:80], "limit": min(limit, 50)}).encode("utf-8")
    req = urllib.request.Request(
        USASPENDING_AUTOCOMPLETE,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning("USASpending discovery failed: %s", e)
        return []
    results = []
    for item in data.get("results") or []:
        name = (item.get("recipient_name") or item.get("name") or "").strip()
        if not name or len(name) < 3:
            continue
        uei = item.get("uei") or item.get("recipient_unique_id") or ""
        results.append(
            {
                "company_name": name,
                "website": "",
                "contact_name": "",
                "contact_title": "",
                "contact_email": "",
                "linkedin_url": "",
                "industry": "Government contractor",
                "segment": "government-subcontractor",
                "source": "usaspending_public_api",
                "source_url": f"https://www.usaspending.gov/search/?hash={urllib.parse.quote(name)}",
                "location": (item.get("location") or item.get("city") or "")[:120],
                "notes": f"UEI:{uei} public award recipient; search:{search_text}",
            }
        )
    return results[:limit]


def discover_public_website(url: str, segment: str = "manufacturing") -> Optional[Dict[str, Any]]:
    """Fetch public homepage text for compliance/manufacturing signals (robots-aware)."""
    url = (url or "").strip()
    if not url.startswith("http"):
        url = "https://" + url
    if is_mock_domain(url):
        return None
    if not robots_allows_fetch(url):
        logger.info("robots.txt disallows fetch: %s", url)
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return None
            html = resp.read(500_000).decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Public page fetch failed %s: %s", url, e)
        return None

    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    text = parser.text()[:8000].lower()
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.replace("www.", "")

    signals = []
    for term in ("cmmc", "as9100", "iso 9001", "itar", "defense", "aerospace", "machining", "quality", "audit"):
        if term in text:
            signals.append(term)
    if not signals and "manufacturing" not in text and "fabricat" not in text:
        return None

    title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    title = title_m.group(1).strip() if title_m else host

    seg = normalize_segment(segment) or "manufacturing"
    return {
        "company_name": title[:120] if title else host,
        "website": url,
        "contact_name": "",
        "contact_title": "",
        "contact_email": "",
        "linkedin_url": "",
        "industry": "Manufacturing" if seg == "manufacturing" else "Aerospace/Defense",
        "segment": seg,
        "source": "public_website",
        "source_url": url,
        "location": "",
        "notes": f"Public page signals: {', '.join(signals[:8])}",
    }


def run_public_discovery(
    *,
    usaspending_queries: Optional[List[str]] = None,
    website_urls: Optional[List[str]] = None,
    limit_per_query: int = 15,
) -> List[Dict[str, Any]]:
    """
    Aggregate lawful public discovery. Owner should verify contacts before outreach.
    """
    usaspending_queries = usaspending_queries or [
        "precision machining",
        "aerospace",
        "defense manufacturing",
    ]
    website_urls = website_urls or []
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    for q in usaspending_queries:
        for row in discover_usaspending_recipients(q, limit=limit_per_query):
            key = (row.get("company_name") or "").lower()
            if key and key not in seen:
                seen.add(key)
                out.append(row)

    for url in website_urls:
        if is_mock_domain(url):
            continue
        row = discover_public_website(url)
        if row:
            key = (row.get("company_name") or "").lower()
            if key not in seen:
                seen.add(key)
                out.append(row)

    return out

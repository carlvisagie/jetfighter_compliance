"""Rule-based entity extraction from document text."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Set

from .extraction import safe_snippet
from .schemas import ExtractedItem

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+\.[a-zA-Z]{2,})"
)
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
DATE_RE = re.compile(
    r"\b(?:20\d{2}|19\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}\b",
    re.I,
)

VENDOR_PRODUCTS: Dict[str, str] = {
    "microsoft 365": "Microsoft 365",
    "office 365": "Microsoft 365",
    "azure": "Microsoft Azure",
    "entra id": "Microsoft Entra ID",
    "google workspace": "Google Workspace",
    "aws": "Amazon Web Services",
    "okta": "Okta",
    "duo": "Duo Security",
    "crowdstrike": "CrowdStrike",
    "sentinelone": "SentinelOne",
    "microsoft defender": "Microsoft Defender",
    "knowbe4": "KnowBe4",
    "proofpoint": "Proofpoint",
    "mimecast": "Mimecast",
    "fortinet": "Fortinet",
    "palo alto": "Palo Alto Networks",
    "cisco": "Cisco",
    "sophos": "Sophos",
    "bitdefender": "Bitdefender",
    "sharepoint": "SharePoint",
    "onedrive": "OneDrive",
    "dropbox": "Dropbox",
    "box.com": "Box",
}

COMPLIANCE_REFS: Dict[str, str] = {
    "cmmc": "CMMC",
    "nist": "NIST",
    "800-171": "NIST SP 800-171",
    "dfars": "DFARS",
    "itar": "ITAR",
    "iso 27001": "ISO 27001",
    "soc 2": "SOC 2",
    "soc2": "SOC 2",
    "hipaa": "HIPAA",
    "gdpr": "GDPR",
    "digital product passport": "EU Digital Product Passport",
    " dpp": "DPP",
    "sbom": "SBOM",
}

COMPANY_SUFFIX = re.compile(
    r"\b([A-Z][A-Za-z0-9&\.\- ]{2,60}(?:LLC|Inc\.?|Corp\.?|Corporation|Company|Co\.|Ltd\.?|LP|LLP|GmbH|Defense|Manufacturing|Industries))\b"
)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _item(value: str, typ: str, confidence: float, source_file: str, span: str = "") -> ExtractedItem:
    return ExtractedItem(
        value=value.strip()[:200],
        type=typ,
        confidence=confidence,
        source_file=source_file,
        extraction_method="rules",
        evidence_span=safe_snippet(span, 120),
        created_utc=_ts(),
        status="inferred",
    )


def extract_entities(text: str, source_file: str, filename: str = "") -> List[ExtractedItem]:
    blob = f"{filename}\n{text}".lower()
    display = f"{filename}\n{text}"
    found: List[ExtractedItem] = []
    seen: Set[str] = set()

    def add(item: ExtractedItem) -> None:
        key = f"{item.type}:{item.value.lower()}"
        if key in seen or not item.value:
            return
        seen.add(key)
        found.append(item)

    for m in EMAIL_RE.finditer(display):
        email = m.group(0).lower()
        if email.endswith(".png") or email.endswith(".jpg"):
            continue
        add(_item(email, "email", 0.92, source_file, m.group(0)))

    for m in DOMAIN_RE.finditer(display):
        dom = m.group(1).lower()
        if dom.endswith(".example.com") or "localhost" in dom:
            continue
        add(_item(dom, "domain", 0.85, source_file, m.group(0)))

    for m in PHONE_RE.finditer(display):
        add(_item(m.group(0), "phone", 0.7, source_file, m.group(0)))

    for m in DATE_RE.finditer(display):
        add(_item(m.group(0), "date", 0.75, source_file, m.group(0)))

    for needle, label in VENDOR_PRODUCTS.items():
        if needle in blob:
            add(_item(label, "technology", 0.8, source_file, needle))

    for needle, label in COMPLIANCE_REFS.items():
        if needle in blob:
            add(_item(label, "compliance_reference", 0.78, source_file, needle))

    for m in COMPANY_SUFFIX.finditer(text):
        name = m.group(1).strip()
        if len(name) < 4 or name.lower() in ("the company", "our company"):
            continue
        add(_item(name, "company_name", 0.55, source_file, m.group(0)))

    return found

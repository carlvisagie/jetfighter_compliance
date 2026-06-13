"""Curated authoritative source registry."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import SourceRecord
from services.defensive_wiring import safe_write_text, safe_write_json

DEFAULT_SOURCES: List[Dict[str, Any]] = [
    {
        "source_id": "nist_csrc",
        "name": "NIST CSRC",
        "url": "https://csrc.nist.gov/",
        "authority_level": "primary",
        "topic_tags": ["nist", "publications", "security"],
        "polling_frequency": "weekly",
    },
    {
        "source_id": "nist_sp800_171",
        "name": "NIST SP 800-171 Rev 2",
        "url": "https://csrc.nist.gov/publications/detail/sp/800-171/rev-2/final",
        "authority_level": "primary",
        "topic_tags": ["nist", "800-171", "cmmc", "cui"],
        "polling_frequency": "weekly",
    },
    {
        "source_id": "nist_sp800_53",
        "name": "NIST SP 800-53 Rev 5",
        "url": "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
        "authority_level": "primary",
        "topic_tags": ["nist", "800-53", "controls"],
        "polling_frequency": "monthly",
    },
    {
        "source_id": "cyber_ab",
        "name": "Cyber AB (CMMC Accreditation Body)",
        "url": "https://www.cyberab.org/",
        "authority_level": "primary",
        "topic_tags": ["cmmc", "accreditation"],
        "polling_frequency": "weekly",
    },
    {
        "source_id": "dod_cmmc",
        "name": "DoD CIO CMMC",
        "url": "https://dodcio.defense.gov/CMMC/",
        "authority_level": "primary",
        "topic_tags": ["cmmc", "dod"],
        "polling_frequency": "weekly",
    },
    {
        "source_id": "dfars",
        "name": "DFARS (Acquisition.gov)",
        "url": "https://www.acquisition.gov/dfars",
        "authority_level": "primary",
        "topic_tags": ["dfars", "contract"],
        "polling_frequency": "weekly",
    },
    {
        "source_id": "far",
        "name": "FAR (Acquisition.gov)",
        "url": "https://www.acquisition.gov/far/current",
        "authority_level": "reference",
        "topic_tags": ["far", "contract"],
        "polling_frequency": "monthly",
    },
    {
        "source_id": "federal_register",
        "name": "Federal Register",
        "url": "https://www.federalregister.gov/",
        "authority_level": "reference",
        "topic_tags": ["regulation", "federal"],
        "polling_frequency": "weekly",
    },
    {
        "source_id": "cisa_advisories",
        "name": "CISA Cybersecurity Advisories",
        "url": "https://www.cisa.gov/news-events/cybersecurity-advisories",
        "authority_level": "primary",
        "topic_tags": ["cisa", "vulnerability", "alert"],
        "polling_frequency": "daily",
    },
    {
        "source_id": "nara_cui",
        "name": "NARA CUI Registry",
        "url": "https://www.archives.gov/cui",
        "authority_level": "primary",
        "topic_tags": ["cui", "nara"],
        "polling_frequency": "monthly",
    },
    {
        "source_id": "ddtc_itar",
        "name": "DDTC / ITAR",
        "url": "https://www.pmddtc.state.gov/",
        "authority_level": "primary",
        "topic_tags": ["itar", "export"],
        "polling_frequency": "monthly",
    },
    {
        "source_id": "sam_gov",
        "name": "SAM.gov",
        "url": "https://sam.gov/content/home",
        "authority_level": "reference",
        "topic_tags": ["sam", "contractor"],
        "polling_frequency": "monthly",
    },
    {
        "source_id": "eu_dpp_espr",
        "name": "EU Digital Product Passport (ESPR)",
        "url": "https://environment.ec.europa.eu/topics/circular-economy/digital-product-passport_en",
        "authority_level": "primary",
        "topic_tags": ["eu", "dpp", "espr", "product"],
        "polling_frequency": "weekly",
    },
]


def _root() -> Path:
    from ..config import DATA

    d = DATA / "compliance_intelligence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sources_path() -> Path:
    return _root() / "sources.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_sources() -> List[SourceRecord]:
    path = sources_path()
    if not path.is_file():
        seed_sources(DEFAULT_SOURCES)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("sources") if isinstance(raw, dict) else raw
        return [SourceRecord.model_validate(s) for s in (items or [])]
    except Exception:
        return [SourceRecord.model_validate(s) for s in DEFAULT_SOURCES]


def save_sources(sources: List[SourceRecord]) -> None:
    path = sources_path()
    payload = {"updated_utc": _utc(), "sources": [s.model_dump() for s in sources]}
    safe_write_json(

        path,

        payload,

        component="compliance_intel",

        context="sources"

    )


def seed_sources(items: Optional[List[Dict[str, Any]]] = None) -> None:
    src = items or DEFAULT_SOURCES
    save_sources([SourceRecord.model_validate(s) for s in src])


def get_source(source_id: str) -> Optional[SourceRecord]:
    for s in load_sources():
        if s.source_id == source_id:
            return s
    return None


def update_source_fields(source_id: str, **fields: Any) -> None:
    sources = load_sources()
    out: List[SourceRecord] = []
    for s in sources:
        if s.source_id == source_id:
            data = s.model_dump()
            data.update(fields)
            out.append(SourceRecord.model_validate(data))
        else:
            out.append(s)
    save_sources(out)


def sources_due_for_poll(frequency: str = "daily") -> List[SourceRecord]:
    """Return enabled sources matching polling_frequency (or all if frequency empty)."""
    out = []
    for s in load_sources():
        if not s.enabled:
            continue
        if frequency and s.polling_frequency != frequency:
            continue
        out.append(s)
    return out


def detect_stale_sources(max_age_days: int = 14) -> List[str]:
    stale: List[str] = []
    now = datetime.now(timezone.utc)
    for s in load_sources():
        if not s.enabled:
            continue
        if not s.last_seen_utc:
            stale.append(s.source_id)
            continue
        try:
            seen = datetime.strptime(s.last_seen_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if (now - seen).days >= max_age_days:
                stale.append(s.source_id)
        except ValueError:
            stale.append(s.source_id)
    return stale

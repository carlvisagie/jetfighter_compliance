"""Paths for acquisition intelligence and forensic memory (under data/acquisition/)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import DATA

ACQ_ROOT = DATA / "acquisition"
INTEL_DIR = ACQ_ROOT / "intelligence"
LEADS_DIR = ACQ_ROOT / "leads"
REPORTS_DIR = ACQ_ROOT / "reports"

OUTCOMES_JSONL = "outcomes.jsonl"
FORENSIC_EVENTS_JSONL = "forensic_events.jsonl"
ORG_PROFILES_JSONL = "org_profiles.jsonl"
LONGITUDINAL_JSONL = "longitudinal.jsonl"
WEIGHTS_JSON = "weights.json"

TARGETS_JSONL = "targets.jsonl"
SIGNALS_JSONL = "signals.jsonl"
INTERACTIONS_JSONL = "interactions.jsonl"
CAMPAIGNS_JSONL = "campaigns.jsonl"
WINNERS_JSONL = "winners.jsonl"
FAILURES_JSONL = "failures.jsonl"
EXPERIMENTS_JSONL = "experiments.jsonl"

MOCK_DOMAIN_BLOCKLIST = (
    "example.com",
    "example.org",
    "example-precision.example",
    "test.com",
    "localhost",
)


def ensure_intel_dirs(base: Optional[Path] = None) -> Path:
    root = base or INTEL_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def is_mock_domain(url_or_email: str) -> bool:
    s = (url_or_email or "").lower()
    return any(b in s for b in MOCK_DOMAIN_BLOCKLIST)

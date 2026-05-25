"""Persist leads (append-only JSONL, CSV sync) with deduplication."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import IMPORT_COLUMNS, Lead, utc_now

from ..config import DATA

DEFAULT_LEADS_DIR = DATA / "acquisition" / "leads"
DEFAULT_REPORTS_DIR = DATA / "acquisition" / "reports"

LEAD_JSONL = "leads.jsonl"
LEAD_CSV = "leads.csv"
REVIEW_QUEUE_CSV = "review_queue.csv"
IMPORT_CSV = "import_candidates.csv"

CSV_FIELDNAMES = [
    "lead_id",
    "company_name",
    "website",
    "contact_name",
    "contact_title",
    "contact_email",
    "linkedin_url",
    "industry",
    "segment",
    "source",
    "source_url",
    "location",
    "pain_signals",
    "compliance_signals",
    "fit_score",
    "confidence_score",
    "notes",
    "status",
    "created_utc",
    "updated_utc",
    "reason_summary",
    "inquiry_routed_link",
]

REVIEW_QUEUE_FIELDS = CSV_FIELDNAMES


def leads_dir(base: Optional[Path] = None) -> Path:
    d = base or DEFAULT_LEADS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def reports_dir(acquisition_root: Optional[Path] = None) -> Path:
    if acquisition_root is None:
        d = DEFAULT_REPORTS_DIR
    elif acquisition_root.name == "reports":
        d = acquisition_root
    elif acquisition_root.name == "leads":
        d = acquisition_root.parent / "reports"
    else:
        d = acquisition_root / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def normalize_company(name: str) -> str:
    n = (name or "").lower().strip()
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def normalize_website(url: str) -> str:
    u = (url or "").lower().strip()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/")


def dedupe_key(lead: Lead) -> str:
    parts = [
        normalize_website(lead.website),
        normalize_company(lead.company_name),
        (lead.contact_email or "").lower().strip(),
        (lead.linkedin_url or "").lower().strip(),
    ]
    return "|".join(parts)


def load_all_leads(base: Optional[Path] = None) -> Tuple[List[Lead], Dict[str, Lead]]:
    """Load from JSONL; returns list and map by dedupe key."""
    path = leads_dir(base) / LEAD_JSONL
    leads: List[Lead] = []
    by_key: Dict[str, Lead] = {}
    if not path.exists():
        return leads, by_key
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        lead = Lead.from_dict(json.loads(line))
        leads.append(lead)
        by_key[dedupe_key(lead)] = lead
    return leads, by_key


def append_lead(lead: Lead, base: Optional[Path] = None) -> None:
    path = leads_dir(base) / LEAD_JSONL
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(lead.to_dict(), ensure_ascii=False) + "\n")


def _lead_to_csv_row(lead: Lead) -> dict:
    d = lead.to_dict()
    d["pain_signals"] = "; ".join(lead.pain_signals)
    d["compliance_signals"] = "; ".join(lead.compliance_signals)
    return d


def rewrite_leads_csv(leads: List[Lead], base: Optional[Path] = None) -> None:
    path = leads_dir(base) / LEAD_CSV
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for lead in sorted(leads, key=lambda x: x.lead_id):
            w.writerow(_lead_to_csv_row(lead))


def rewrite_review_queue(leads: List[Lead], base: Optional[Path] = None, min_fit: int = 65) -> List[Lead]:
    """Leads in review queue: fit >= min_fit, status new or reviewed only."""
    queue = [
        l
        for l in leads
        if l.fit_score >= min_fit and l.status in ("new", "reviewed")
    ]
    path = leads_dir(base) / REVIEW_QUEUE_CSV
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_QUEUE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for lead in sorted(queue, key=lambda x: -x.fit_score):
            w.writerow(_lead_to_csv_row(lead))
    return queue


def next_lead_id(existing: List[Lead]) -> str:
    ts = utc_now()[:10].replace("-", "")
    prefix = f"L-{ts}-"
    nums = []
    for lead in existing:
        if lead.lead_id.startswith(prefix):
            try:
                nums.append(int(lead.lead_id.split("-")[-1]))
            except ValueError:
                pass
    n = max(nums) + 1 if nums else 1
    return f"{prefix}{n:04d}"

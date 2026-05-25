"""CSV/manual lead import pipeline (no scraping, no auto-contact)."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from .export import write_discovery_report
from .models import IMPORT_COLUMNS, ImportStats, Lead, normalize_segment, utc_now
from .finder import run_public_discovery
from .intelligence_paths import is_mock_domain
from .scoring import score_lead_full
from .storage import (
    IMPORT_CSV,
    append_lead,
    dedupe_key,
    leads_dir,
    load_all_leads,
    next_lead_id,
    reports_dir,
    rewrite_leads_csv,
    rewrite_review_queue,
)

from ..public_url import get_public_base_url

INQUIRY_SUBJECT_BY_SEGMENT = {
    "aerospace": "CMMC Level 1",
    "manufacturing": "CMMC Level 1",
    "compliance-heavy": "AI Compliance Essential",
    "audit-stressed": "CMMC Level 1",
    "government-subcontractor": "CMMC Level 1",
    "quality-ops-manager": "CMMC Level 1",
}


def build_inquiry_link(lead_id: str, segment: str, base_url: Optional[str] = None) -> str:
    base = (base_url or get_public_base_url()).rstrip("/")
    subject = INQUIRY_SUBJECT_BY_SEGMENT.get(segment, "CMMC Level 1")
    q = f"subject={quote(subject)}&ref={quote(lead_id)}"
    return f"{base}/ui/inquiry.html?{q}"


def validate_row(row: Dict[str, str], line_no: int) -> tuple[Optional[Dict[str, str]], Optional[str]]:
    company = (row.get("company_name") or "").strip()
    if not company:
        return None, f"line {line_no}: missing company_name"
    site = (row.get("website") or "").strip()
    email = (row.get("contact_email") or "").strip()
    if is_mock_domain(site) or is_mock_domain(email):
        return None, f"line {line_no}: mock/example domain not allowed in production path"
    seg = normalize_segment(row.get("segment") or "")
    if not seg:
        return None, f"line {line_no}: invalid or missing segment"
    cleaned = {k: (row.get(k) or "").strip() for k in IMPORT_COLUMNS}
    cleaned["segment"] = seg
    return cleaned, None


def row_to_lead(cleaned: Dict[str, str], lead_id: str, base_url: Optional[str] = None) -> Lead:
    mem_ctx = {}
    try:
        from services.memory import safe_read_before_lead_score

        mem_ctx = safe_read_before_lead_score(
            cleaned.get("company_name", ""),
            cleaned.get("contact_email", ""),
        )
    except Exception:
        pass
    lead = Lead(
        lead_id=lead_id,
        company_name=cleaned["company_name"],
        website=cleaned.get("website", ""),
        contact_name=cleaned.get("contact_name", ""),
        contact_title=cleaned.get("contact_title", ""),
        contact_email=cleaned.get("contact_email", ""),
        linkedin_url=cleaned.get("linkedin_url", ""),
        industry=cleaned.get("industry", ""),
        segment=cleaned["segment"],
        source=cleaned.get("source") or "csv_import",
        source_url=cleaned.get("source_url", ""),
        location=cleaned.get("location", ""),
        notes=cleaned.get("notes", ""),
        status="new",
    )
    lead = score_lead_full(lead, mem_ctx)
    lead.inquiry_routed_link = build_inquiry_link(lead_id, lead.segment, base_url)
    lead.updated_utc = utc_now()
    return lead


def run_csv_import(
    import_path: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    public_base_url: Optional[str] = None,
) -> ImportStats:
    """
    Import candidates from CSV. Does not contact anyone. Does not set approved_for_outreach.
    """
    stats = ImportStats()
    root = leads_dir(base_dir)
    src = import_path or (root / IMPORT_CSV)
    if not src.exists():
        raise FileNotFoundError(f"Import file not found: {src}")

    existing_list, by_key = load_all_leads(base_dir)
    all_leads = list(existing_list)

    with src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        for line_no, row in enumerate(reader, start=2):
            stats.total_rows += 1
            cleaned, err = validate_row(row, line_no)
            if err:
                stats.rejected_rows += 1
                stats.rejection_reasons.append(err)
                continue
            stats.valid_rows += 1
            tmp_id = "pending"
            lead = row_to_lead(cleaned, tmp_id, public_base_url)
            key = dedupe_key(lead)
            if key in by_key and by_key[key].lead_id:
                stats.duplicates_skipped += 1
                continue
            lead.lead_id = next_lead_id(all_leads)
            lead.inquiry_routed_link = build_inquiry_link(lead.lead_id, lead.segment, public_base_url)
            append_lead(lead, base_dir)
            all_leads.append(lead)
            by_key[key] = lead
            try:
                from services.memory import link_lead, resolve_or_create_entity

                eid = resolve_or_create_entity(
                    email=lead.contact_email,
                    company=lead.company_name,
                    contact_name=lead.contact_name,
                    display_name=lead.company_name,
                )
                link_lead(lead.lead_id, eid, {"source": lead.source, "segment": lead.segment})
            except Exception:
                pass
            stats.imported += 1
            stats.new_lead_ids.append(lead.lead_id)
            if lead.fit_score >= 80:
                stats.scored_80_plus += 1
            elif lead.fit_score >= 65:
                stats.scored_65_79 += 1
            else:
                stats.low_fit += 1
            for p in lead.pain_signals:
                stats.top_pain_signals[p] = stats.top_pain_signals.get(p, 0) + 1

    rewrite_leads_csv(all_leads, base_dir)
    rewrite_review_queue(all_leads, base_dir, min_fit=65)
    report_root = base_dir.parent if base_dir and base_dir.name == "leads" else None
    write_discovery_report(stats, all_leads, report_root)
    return stats


def run_finder_discovery(
    *,
    usaspending_queries: Optional[List[str]] = None,
    website_urls: Optional[List[str]] = None,
    base_dir: Optional[Path] = None,
    public_base_url: Optional[str] = None,
    limit_per_query: int = 15,
) -> ImportStats:
    """
    Lawful public discovery → score → store. No auto-contact. Owner verifies contacts.
    """
    import csv

    candidates = run_public_discovery(
        usaspending_queries=usaspending_queries,
        website_urls=website_urls,
        limit_per_query=limit_per_query,
    )
    root = leads_dir(base_dir)
    staging = root / "import_candidates.csv"
    fields = list(IMPORT_COLUMNS)
    with staging.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in candidates:
            w.writerow({k: row.get(k, "") for k in fields})
    return run_csv_import(import_path=staging, base_dir=base_dir, public_base_url=public_base_url)

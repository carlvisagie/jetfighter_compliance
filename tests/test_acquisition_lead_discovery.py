"""Lead discovery engine: import, dedupe, scoring, review queue, no auto-contact."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from services.acquisition.discovery import build_inquiry_link, run_csv_import
from services.acquisition.models import Lead
from services.acquisition.scoring import score_lead
from services.acquisition.storage import (
    REVIEW_QUEUE_CSV,
    dedupe_key,
    load_all_leads,
    rewrite_review_queue,
)


@pytest.fixture
def acq_tmp(tmp_path):
    leads = tmp_path / "leads"
    reports = tmp_path / "reports"
    leads.mkdir()
    reports.mkdir()
    return leads, reports


def _write_import(path: Path, rows: list[dict]) -> None:
    fields = [
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
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_csv_import_works(acq_tmp):
    leads_dir, _ = acq_tmp
    imp = leads_dir / "import_candidates.csv"
    _write_import(
        imp,
        [
            {
                "company_name": "Aero Parts Inc",
                "website": "https://aeroparts.example",
                "contact_name": "Sam QA",
                "contact_title": "Quality Manager",
                "contact_email": "sam@aeroparts.example",
                "linkedin_url": "",
                "industry": "Aerospace",
                "segment": "aerospace",
                "source": "owner_list",
                "source_url": "",
                "location": "TX",
                "notes": "CMMC mentioned",
            },
        ],
    )
    stats = run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://compliance.keepyourcontracts.com")
    assert stats.imported == 1
    assert stats.valid_rows == 1
    all_leads, _ = load_all_leads(leads_dir)
    assert len(all_leads) == 1
    assert all_leads[0].status == "new"
    assert all_leads[0].fit_score >= 0


def test_invalid_rows_rejected(acq_tmp):
    leads_dir, _ = acq_tmp
    imp = leads_dir / "import_candidates.csv"
    _write_import(
        imp,
        [
            {
                "company_name": "",
                "website": "",
                "contact_name": "",
                "contact_title": "",
                "contact_email": "",
                "linkedin_url": "",
                "industry": "",
                "segment": "aerospace",
                "source": "",
                "source_url": "",
                "location": "",
                "notes": "",
            },
            {
                "company_name": "Bad Segment Co",
                "website": "",
                "contact_name": "",
                "contact_title": "",
                "contact_email": "",
                "linkedin_url": "",
                "industry": "",
                "segment": "invalid-segment",
                "source": "",
                "source_url": "",
                "location": "",
                "notes": "",
            },
        ],
    )
    stats = run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://test.example")
    assert stats.imported == 0
    assert stats.rejected_rows == 2


def test_deduplication_works(acq_tmp):
    leads_dir, _ = acq_tmp
    imp = leads_dir / "import_candidates.csv"
    row = {
        "company_name": "Dup Mfg LLC",
        "website": "https://dupmfg.example",
        "contact_name": "Pat Ops",
        "contact_title": "Operations Manager",
        "contact_email": "pat@dupmfg.example",
        "linkedin_url": "",
        "industry": "Manufacturing",
        "segment": "manufacturing",
        "source": "csv",
        "source_url": "",
        "location": "",
        "notes": "ISO 9001 audit documentation",
    }
    _write_import(imp, [row, row])
    stats = run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://test.example")
    assert stats.imported == 1
    assert stats.duplicates_skipped == 1


def test_score_calculation_works():
    lead = Lead(
        lead_id="L-test-0001",
        company_name="Defense Machining LLC",
        website="https://defmac.example",
        contact_title="Compliance Manager",
        contact_email="c@defmac.example",
        segment="government-subcontractor",
        industry="Defense manufacturing",
        notes="DFARS flowdown and CMMC readiness",
    )
    fit, conf, pain, comp, summary = score_lead(lead)
    assert fit >= 65
    assert conf > 0
    assert summary
    assert pain or comp


def test_review_queue_created(acq_tmp):
    leads_dir, _ = acq_tmp
    imp = leads_dir / "import_candidates.csv"
    _write_import(
        imp,
        [
            {
                "company_name": "High Fit Aero",
                "website": "https://highfit.example",
                "contact_name": "Q Manager",
                "contact_title": "Quality Manager",
                "contact_email": "q@highfit.example",
                "linkedin_url": "",
                "industry": "Aerospace",
                "segment": "aerospace",
                "source": "owner",
                "source_url": "",
                "location": "",
                "notes": "AS9100 CMMC documentation traceability audit",
            },
        ],
    )
    run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://test.example")
    rq = leads_dir / REVIEW_QUEUE_CSV
    assert rq.exists()
    text = rq.read_text(encoding="utf-8")
    assert "High Fit Aero" in text
    all_leads, _ = load_all_leads(leads_dir)
    high = [l for l in all_leads if l.fit_score >= 65]
    assert high
    queue = rewrite_review_queue(all_leads, leads_dir, min_fit=65)
    assert queue


def test_routed_inquiry_link_created(acq_tmp):
    leads_dir, _ = acq_tmp
    imp = leads_dir / "import_candidates.csv"
    _write_import(
        imp,
        [
            {
                "company_name": "Link Test Co",
                "website": "https://linktest.example",
                "contact_name": "Alex",
                "contact_title": "QA Manager",
                "contact_email": "alex@linktest.example",
                "linkedin_url": "",
                "industry": "Manufacturing",
                "segment": "manufacturing",
                "source": "manual",
                "source_url": "",
                "location": "",
                "notes": "",
            },
        ],
    )
    run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://compliance.keepyourcontracts.com")
    all_leads, _ = load_all_leads(leads_dir)
    lead = all_leads[0]
    assert "compliance.keepyourcontracts.com/ui/inquiry.html" in lead.inquiry_routed_link
    assert "ref=" in lead.inquiry_routed_link
    assert lead.lead_id in lead.inquiry_routed_link
    link = build_inquiry_link("L-20260101-0001", "aerospace", "https://compliance.keepyourcontracts.com")
    assert "subject=" in link
    assert "ref=L" in link


def test_no_auto_contact(acq_tmp):
    leads_dir, _ = acq_tmp
    imp = leads_dir / "import_candidates.csv"
    _write_import(
        imp,
        [
            {
                "company_name": "No Contact LLC",
                "website": "https://nocontact.example",
                "contact_name": "Chris",
                "contact_title": "Operations Manager",
                "contact_email": "chris@nocontact.example",
                "linkedin_url": "",
                "industry": "Manufacturing",
                "segment": "manufacturing",
                "source": "csv",
                "source_url": "",
                "location": "",
                "notes": "",
            },
        ],
    )
    stats = run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://test.example")
    all_leads, _ = load_all_leads(leads_dir)
    assert stats.imported == 1
    for lead in all_leads:
        assert lead.status == "new"
        assert lead.status != "approved_for_outreach"
        assert lead.status != "contacted"

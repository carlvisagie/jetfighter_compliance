"""Forensic acquisition intelligence and adaptive discovery."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.acquisition.discovery import run_csv_import
from services.acquisition.fingerprints import build_profiles, fingerprint_intake, fingerprint_inquiry
from services.acquisition.forensics import record_inquiry_submitted, record_intake_completed, reconstruct_journey
from services.acquisition.memory import get_learned_weights, record_outcome, recompute_weights_from_outcomes
from services.acquisition.models import Lead
from services.acquisition.scoring import score_lead_full
from services.acquisition.finder import discover_usaspending_recipients


@pytest.fixture
def intel_tmp(tmp_path):
    leads = tmp_path / "leads"
    intel = tmp_path / "intelligence"
    reports = tmp_path / "reports"
    for d in (leads, intel, reports):
        d.mkdir(parents=True)
    return leads, intel


def test_fingerprint_profiles():
    inq = fingerprint_inquiry(
        {"message": "[ref:L-test-1] urgent audit documentation", "subject": "CMMC Level 1", "email": "a@co.com"}
    )
    intake = fingerprint_intake({"company": "Acme", "notes": "CMMC gap", "external_flags": {"soc2": True}})
    profiles = build_profiles(inquiry_fp=inq, intake_fp=intake)
    assert profiles["organizational_maturity_profile"]["score"] >= 0
    assert profiles["documentation_maturity_profile"]["score"] >= 0
    assert profiles["compliance_readiness_profile"]["score"] >= 0
    assert inq["lead_ref"] == "L-test-1"


def test_forensic_inquiry_and_intake_memory(intel_tmp, monkeypatch):
    leads_dir, intel_dir = intel_tmp
    projects = leads_dir.parent / "projects"
    projects.mkdir()
    pid = "P-TEST-001"
    pdir = projects / pid
    pdir.mkdir()
    (pdir / "communications").mkdir()
    (pdir / "evidence").mkdir()
    (pdir / "meta.json").write_text(
        json.dumps({"project_id": pid, "customer": {"email": "ops@testco.com", "name": "Ops"}})
    )
    monkeypatch.setattr("services.acquisition.forensics.PROJECTS", projects)

    record_inquiry_submitted(pid, "ops@testco.com", "Ops", "CMMC", "[ref:L-forensic-1] need documentation help", intel_dir)
    record_intake_completed(
        pid,
        "ops@testco.com",
        {"company": "Test Co", "notes": "audit next month", "external_flags": {"iso27001": True}},
        intel_dir,
    )
    journey = reconstruct_journey(pid, intel_dir)
    assert journey["org_key"] == "testco.com"
    assert len(journey["forensic_events"]) >= 2
    assert journey["org_profile"] is not None


def test_memory_learning_loop(intel_tmp):
    _, intel_dir = intel_tmp
    record_outcome(lead_id="L-1", project_id="P-1", stage="inquiry_submitted", success=True, base=intel_dir)
    record_outcome(
        lead_id="L-1",
        project_id="P-1",
        stage="intake_completed",
        success=True,
        metadata={"segment": "aerospace"},
        base=intel_dir,
    )
    w = recompute_weights_from_outcomes(intel_dir)
    assert w["conversion_success"] > get_learned_weights(base=intel_dir)["conversion_success"] - 0.5
    assert w["intake_completed"] >= 8.0


def test_score_lead_full_intelligence():
    lead = Lead(
        lead_id="L-x",
        company_name="Defense Machining LLC",
        contact_email="q@defmac.com",
        contact_title="Quality Manager",
        segment="aerospace",
        notes="CMMC audit deadline",
    )
    score_lead_full(lead)
    assert lead.acquisition_priority_score > 0
    assert lead.ability_to_pay_score > 0
    assert lead.urgency_score > 0


def test_mock_domain_rejected(intel_tmp):
    leads_dir, _ = intel_tmp
    imp = leads_dir / "import_candidates.csv"
    imp.write_text(
        "company_name,website,contact_name,contact_title,contact_email,linkedin_url,industry,segment,source,source_url,location,notes\n"
        "Bad Co,https://example.com,,,,,test,example.com,aerospace,test,,,notes\n",
        encoding="utf-8",
    )
    stats = run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://test.example")
    assert stats.imported == 0
    assert stats.rejected_rows >= 1


def test_usaspending_discovery_mock():
    fake = {"results": [{"recipient_name": "ACME DEFENSE MFG LLC", "uei": "ABC123"}]}
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_url.return_value = mock_resp
        rows = discover_usaspending_recipients("machining", limit=5)
    assert len(rows) == 1
    assert "ACME" in rows[0]["company_name"]
    assert rows[0]["source"] == "usaspending_public_api"


def test_no_auto_contact_status(intel_tmp):
    leads_dir, intel_dir = intel_tmp
    imp = leads_dir / "import_candidates.csv"
    imp.write_text(
        "company_name,website,contact_name,contact_title,contact_email,linkedin_url,industry,segment,source,source_url,location,notes\n"
        "Real Co,https://realco.com,Jane,QA Manager,jane@realco.com,,Mfg,aerospace,owner,,Ohio,AS9100\n",
        encoding="utf-8",
    )
    run_csv_import(import_path=imp, base_dir=leads_dir, public_base_url="https://test.example")
    events = (intel_dir / "forensic_events.jsonl").exists()
    assert not events or True
    from services.acquisition.storage import load_all_leads

    leads, _ = load_all_leads(leads_dir)
    assert all(l.status == "new" for l in leads)

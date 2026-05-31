"""Tests for the autonomous acquisition → intake conversion flow.

Flow under test:
  1. Acquisition engine generates a lead with a shop URL (ref=LD-xxx)
  2. Operator approves the lead → system generates invite URL + email draft
  3. Prospect visits shop?ref=LD-xxx → founding-beta?ref=LD-xxx → uploads files
  4. Intake records lead_id, emits acquisition_conversion alert
  5. Lead status updates to intake_completed
  6. Operator alert fired
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def acq_intake_env(monkeypatch, tmp_path):
    """Minimal env wiring both acquisition storage and intake storage."""
    leads = tmp_path / "leads"
    leads.mkdir(parents=True)
    (leads / "leads.jsonl").write_text("", encoding="utf-8")

    intel = tmp_path / "intelligence"
    intel.mkdir(parents=True)

    intakes = tmp_path / "intakes"
    intakes.mkdir(parents=True)

    data = tmp_path
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    mem = tmp_path / "memory"
    mem.mkdir()
    alerts_dir = tmp_path / "alerts"
    alerts_dir.mkdir()

    monkeypatch.setattr("services.config.DATA", data)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.acquisition.storage.DEFAULT_LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.leads_dir", lambda base_dir=None: leads)
    monkeypatch.setattr("services.acquisition.orchestration.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.telemetry.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.learning.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.memory.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    monkeypatch.setattr("services.intake.storage.intakes_root", lambda: intakes)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("KYC_DATA", str(tmp_path))
    monkeypatch.setenv("KYC_SAFE_MODE", "false")

    return {"leads": leads, "intel": intel, "intakes": intakes, "data": data}


@pytest.fixture
def client():
    return TestClient(app, headers={"X-Ops-Password": "test-ops-password-for-pytest"})


@pytest.fixture
def anon_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

def test_acquisition_routing_defaults_to_shop():
    from services.acquisition.routing import build_upload_route

    route = build_upload_route(lead_id="LD-0001", segment="government-subcontractor")
    assert "/ui/shop" in route["primary_url"]
    assert "LD-0001" in route["primary_url"]
    assert route["routing_doctrine"] == "upload_first"


def test_acquisition_routing_preserves_ref():
    from services.acquisition.routing import build_upload_route

    route = build_upload_route(lead_id="LD-TESTX", campaign_id="test-campaign")
    assert "ref=LD-TESTX" in route["primary_url"]
    assert "utm_campaign=test-campaign" in route["primary_url"]


def test_shop_html_links_to_founding_beta(anon_client: TestClient):
    r = anon_client.get("/ui/shop.html")
    assert r.status_code == 200
    text = r.text
    # All CTAs must now point to founding-beta, not inquiry
    assert "/ui/founding-beta" in text
    assert "/ui/inquiry.html" not in text
    # Ref propagation script should be present
    assert "kyc-ref-cta" in text


# ---------------------------------------------------------------------------
# Approve-and-invite tests
# ---------------------------------------------------------------------------

def test_approve_and_invite_unknown_lead():
    from services.acquisition.orchestration import approve_and_invite_lead

    result = approve_and_invite_lead("LD-DOES-NOT-EXIST")
    assert result["ok"] is False
    assert result["error"] == "lead_not_found"


def test_approve_and_invite_generates_invite_url(acq_intake_env, monkeypatch):
    from services.acquisition.models import Lead, utc_now
    from services.acquisition.storage import append_lead

    lead = Lead(
        lead_id="LD-APPR-001",
        company_name="Acme Defense LLC",
        contact_name="Jane Doe",
        contact_email="jane@acme.com",
        segment="government-subcontractor",
        fit_score=82,
        status="new",
        created_utc=utc_now(),
        updated_utc=utc_now(),
    )
    append_lead(lead)

    from services.acquisition.orchestration import approve_and_invite_lead

    result = approve_and_invite_lead("LD-APPR-001")
    assert result["ok"] is True
    assert result["status"] == "approved_for_outreach"
    assert "LD-APPR-001" in result["invite_url"]
    assert "/ui/shop" in result["invite_url"]
    assert result["email_draft"]["subject"]
    assert "LD-APPR-001" in result["email_draft"]["cta_url"]


def test_approve_rejected_lead_is_refused(acq_intake_env):
    from services.acquisition.models import Lead, utc_now
    from services.acquisition.storage import append_lead
    from services.acquisition.orchestration import approve_and_invite_lead

    lead = Lead(
        lead_id="LD-REJCT-001",
        company_name="Bad Actor Inc",
        status="rejected",
        created_utc=utc_now(),
        updated_utc=utc_now(),
    )
    append_lead(lead)

    result = approve_and_invite_lead("LD-REJCT-001")
    assert result["ok"] is False
    assert result["error"] == "lead_not_eligible"


# ---------------------------------------------------------------------------
# Intake ref → lead_id attribution
# ---------------------------------------------------------------------------

def test_upload_with_ref_stores_lead_id(fb_env, monkeypatch, anon_client):
    """When a prospect uploads with ref=LD-xxx, intake record gets lead_id stored."""
    monkeypatch.setattr(
        "services.intake.intake._link_intake_to_lead",
        lambda intake_id, record: None,  # isolate from acquisition storage
    )
    monkeypatch.setattr(
        "services.alerts.engine.raise_alert",
        lambda *a, **kw: {"ok": True},
    )
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        data={
            "email": "prospect@govco.com",
            "company": "GovCo LLC",
            "ref": "LD-0099",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    iid = body["intake_id"]

    from services.intake.storage import load_intake_record
    rec = load_intake_record(iid)
    assert rec.get("lead_id") == "LD-0099"


def test_upload_ignores_invalid_ref(fb_env, monkeypatch, anon_client):
    """Non-LD- refs are not stored on the intake."""
    monkeypatch.setattr(
        "services.intake.intake._link_intake_to_lead",
        lambda intake_id, record: None,
    )
    monkeypatch.setattr(
        "services.alerts.engine.raise_alert",
        lambda *a, **kw: {"ok": True},
    )
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        data={"email": "test@test.com", "ref": "INVALID-REF"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    from services.intake.storage import load_intake_record
    rec = load_intake_record(iid)
    assert not rec.get("lead_id")


# ---------------------------------------------------------------------------
# Invitation email template
# ---------------------------------------------------------------------------

def test_invitation_email_text_contains_cta():
    from services.email_utils import build_invitation_email_text

    result = build_invitation_email_text(
        company_name="Apex Defense",
        contact_name="Bob Smith",
        invite_url="https://compliance.keepyourcontracts.com/ui/shop?ref=LD-007&utm_campaign=test",
        upload_url="https://compliance.keepyourcontracts.com/ui/founding-beta?ref=LD-007",
    )
    assert result["subject"]
    body = result["body"]
    assert "Bob Smith" in body
    assert "Apex Defense" in body
    assert "LD-007" in body
    assert result["cta_url"]


def test_invitation_email_no_contact_name():
    from services.email_utils import build_invitation_email_text

    result = build_invitation_email_text(invite_url="https://example.com/shop?ref=LD-1")
    body = result["body"]
    assert "Hi there" in body


# ---------------------------------------------------------------------------
# Alert: acquisition_conversion
# ---------------------------------------------------------------------------

def test_acquisition_conversion_alert_emitted(monkeypatch):
    raised = {}

    def mock_raise_alert(event_type, **kwargs):
        raised["event_type"] = event_type
        raised.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("services.alerts.engine.raise_alert", mock_raise_alert)

    from services.alerts.engine import alert_acquisition_conversion
    alert_acquisition_conversion(lead_id="LD-CONV-001", intake_id="FB-CONV-001")
    assert raised.get("event_type") == "acquisition_conversion"
    assert "LD-CONV-001" in str(raised.get("context", {}))

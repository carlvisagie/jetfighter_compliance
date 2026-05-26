"""Autonomous acquisition intelligence organism."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.acquisition.messaging import generate_message
from services.acquisition.models import Lead
from services.acquisition.orchestration import (
    get_operator_dashboard,
    ingest_public_signal,
    run_acquisition_cycle,
    track_funnel_event,
)
from services.acquisition.qualification import qualify_lead
from services.acquisition.routing import build_upload_route
from services.acquisition.signals import detect_signals
from services.acquisition import learning, telemetry
from services.acquisition.intelligence_paths import (
    TARGETS_JSONL,
    WINNERS_JSONL,
    ensure_intel_dirs,
)
from services.memory.timeline import load_timeline
from services.memory.entity_graph import find_entity_id


@pytest.fixture
def acq_env(monkeypatch, tmp_path):
    intel = tmp_path / "intelligence"
    intel.mkdir(parents=True)
    leads = tmp_path / "leads"
    leads.mkdir(parents=True)
    (leads / "leads.jsonl").write_text("", encoding="utf-8")
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    mem = tmp_path / "memory"
    mem.mkdir()

    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.acquisition.intelligence_paths.ACQ_ROOT", tmp_path)
    monkeypatch.setattr("services.acquisition.intelligence_paths.INTEL_DIR", intel)
    monkeypatch.setattr("services.acquisition.intelligence_paths.LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.DEFAULT_LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.leads_dir", lambda base_dir=None: leads)
    monkeypatch.setattr("services.acquisition.orchestration.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.telemetry.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.learning.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.memory.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    return intel


def test_signal_detection_critical(acq_env):
    sig = detect_signals("We are overwhelmed and need CMMC help before our audit deadline")
    assert sig["signal_level"] in ("high", "critical")
    assert sig["burden_detected"] is True
    assert "overwhelm" in sig["pain_tags"] or "cmmc_help_seeking" in sig["pain_tags"]


def test_qualification_has_confidence_not_certainty(acq_env):
    lead = Lead(lead_id="LD-T1", company_name="Acme Mfg", segment="manufacturing", notes="small shop")
    qual = qualify_lead(lead, detect_signals("audit pressure"))
    assert qual["company_size"]["confidence"] < 100
    assert "qualification_note" in qual


def test_upload_first_routing(acq_env):
    routes = build_upload_route(lead_id="LD-ABC", segment="aerospace", campaign_id="upload-first", message_variant="A")
    assert "/ui/inquiry.html" in routes["primary_url"]
    assert "utm_campaign=upload-first" in routes["primary_url"]
    assert routes["routing_doctrine"] == "upload_first"


def test_ingest_public_signal_creates_target(acq_env):
    out = ingest_public_signal(
        text="DFARS confusion — where do I start with documentation?",
        source="public_forum",
        company_name="Test Co",
    )
    assert out["ok"] is True
    targets = (acq_env / TARGETS_JSONL).read_text(encoding="utf-8")
    assert "Test Co" in targets
    assert "TGT-" in targets


def test_telemetry_emitted_on_ingest(acq_env):
    ingest_public_signal(text="need cmmc help overwhelmed", source="test")
    interactions = telemetry.load_interactions(event_type="acquisition_target_detected", base=acq_env)
    assert len(interactions) >= 1


def test_winner_failure_persistence(acq_env):
    learning.record_winner(reason="upload_completed", lead_id="LD-W", campaign_id="c1", variant="A", base=acq_env)
    learning.record_failure(reason="upload_abandoned", lead_id="LD-F", base=acq_env)
    assert len(learning.load_winners(acq_env)) >= 1
    assert len(learning.load_failures(acq_env)) >= 1


def test_track_funnel_conversion(acq_env):
    track_funnel_event(
        "workspace_created",
        success=True,
        lead_id="LD-X",
        project_id="P-TEST-1",
        campaign_id="upload-first",
        base=acq_env,
    )
    assert (acq_env / WINNERS_JSONL).is_file()


def test_message_burden_removal_no_guarantees():
    lead = Lead(lead_id="LD-M", company_name="Co", segment="compliance-heavy")
    msg = generate_message(lead, "A")
    assert "upload" in msg["cta"].lower()
    assert "guaranteed certification" not in msg["body"].lower()
    assert msg["doctrine"] == "upload_first_no_auto_send"


def test_operator_dashboard(acq_env):
    ingest_public_signal(text="security questionnaire stress", source="web", company_name="Dash Co")
    dash = get_operator_dashboard(base=acq_env)
    assert dash["ok"] is True
    assert dash["doctrine"]["success_metric"] == "real_paperwork_submitted"
    assert isinstance(dash["hottest_targets"], list)


def test_cockpit_api_requires_ops(client):
    anon = TestClient(app)
    r = anon.get("/api/operator/acquisition-intelligence")
    assert r.status_code == 403


def test_cockpit_api_authenticated(client, acq_env):
    r = client.get("/api/operator/acquisition-intelligence")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_run_cycle_empty_leads(acq_env):
    out = run_acquisition_cycle(base=acq_env)
    assert out["ok"] is True


def test_experiment_persistence(acq_env):
    exp = learning.record_experiment(
        name="CTA framing",
        hypothesis="Burden removal beats fear",
        variants=["A", "B"],
        base=acq_env,
    )
    assert exp["experiment_id"].startswith("EXP-")


def test_memory_linkage_on_winner(acq_env, tmp_path):
    mem = tmp_path / "memory2"
    mem.mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
        mp.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
        learning.record_winner(reason="conversion:test", lead_id="LD-MEM-1", base=acq_env)
    eid = find_entity_id(lead_id="LD-MEM-1", base=mem)
    if eid:
        events = [t["event_type"] for t in load_timeline(eid, mem)]
        assert "acquisition_winner" in events


def test_public_ui_no_acquisition_ops_links():
    from tests.test_public_ui_exposure import PUBLIC_PAGES

    root = Path(__file__).resolve().parents[1]
    for path in PUBLIC_PAGES:
        html = (root / path.lstrip("/")).read_text(encoding="utf-8", errors="replace")
        assert "/api/operator/acquisition" not in html

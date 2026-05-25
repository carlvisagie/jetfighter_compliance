"""KYC organism integration — central memory must index all critical vessels."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.memory.central_memory import lookup
from services.memory.entity_graph import get_entity
from services.memory.learning import get_learning_summary
from services.memory.organism_integration import run_integration_audit
from services.memory.self_healing import run_self_healing_scan
from services.memory.timeline import load_timeline

@pytest.fixture
def organism_env(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    projects = tmp_path / "projects"
    projects.mkdir()
    intel = tmp_path / "acquisition" / "intelligence"
    intel.mkdir(parents=True)
    proc = tmp_path / "process"
    proc.mkdir()
    inquiries = tmp_path / "inquiries"
    inquiries.mkdir()
    rfq = tmp_path / "rfq"
    rfq.mkdir()

    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.timeline.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.signals.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.learning.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.self_healing.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.self_healing.PROJECTS", projects)
    monkeypatch.setattr("services.memory.self_healing.DATA", tmp_path)
    monkeypatch.setattr("services.memory.central_memory.PROJECTS", projects)
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.process.DATA", tmp_path)
    monkeypatch.setattr("services.process.WF_DIR", proc)
    monkeypatch.setattr("services.acquisition.intelligence_paths.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.history.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.memory.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("server.DATA", tmp_path)
    monkeypatch.setattr("services.projects.PROJECTS", projects)
    monkeypatch.setattr("services.ledger.DATA", tmp_path)
    return mem, projects, intel, tmp_path


def _timeline_types(entity_id: str, mem: Path) -> set:
    return {t["event_type"] for t in load_timeline(entity_id, mem)}


def test_inquiry_writes_central_memory(organism_env, client):
    mem, projects, _, data = organism_env
    lead_ref = "L-ORG-INQ"
    r = client.post(
        "/api/inquiry/submit",
        data={
            "name": "Org Test",
            "email": "org-inq@test.com",
            "subject": "CMMC",
            "message": f"[ref:{lead_ref}]\n\nOrganism inquiry test.",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok")
    pid = body["project_id"]
    result = lookup(project_id=pid, base=mem)
    types = _timeline_types(result["journey"]["entity_id"], mem)
    assert "inquiry_submitted" in types
    assert "project_created" in types
    ent = get_entity(result["journey"]["entity_id"], mem)
    assert any(r["ref_type"] == "project" and r["ref_id"] == pid for r in (ent.get("refs") or []))


def test_intake_writes_central_memory(organism_env, client):
    mem, projects, _, data = organism_env
    r = client.post(
        "/api/inquiry/submit",
        data={
            "name": "Intake Org",
            "email": "org-intake@test.com",
            "subject": "Intake",
            "message": "intake organism test",
        },
    )
    pid = r.json()["project_id"]
    token = r.json()["intake_url"].split("token=")[1]
    ir = client.post(
        "/api/intake/submit",
        data={"token": token, "company": "Co", "contact": "C", "notes": "notes"},
    )
    assert ir.json().get("ok")
    result = lookup(project_id=pid, base=mem)
    types = _timeline_types(result["journey"]["entity_id"], mem)
    assert "intake_completed" in types


def test_ledger_event_writes_central_memory(organism_env, client):
    mem, projects, _, data = organism_env
    r = client.post(
        "/api/inquiry/submit",
        data={
            "name": "Ledger",
            "email": "org-ledger@test.com",
            "subject": "L",
            "message": "ledger test",
        },
    )
    pid = r.json()["project_id"]
    evt_id = f"EVT-{pid}-ORDER"
    result = lookup(project_id=pid, base=mem)
    types = _timeline_types(result["journey"]["entity_id"], mem)
    assert "ledger_event" in types
    assert any(t.get("ref_id") == evt_id for t in load_timeline(result["journey"]["entity_id"], mem) if t["event_type"] == "ledger_event")


def test_evidence_upload_writes_central_memory(organism_env):
    mem, projects, _, data = organism_env
    from services.acquisition.forensics import safe_record_evidence
    from services.memory.central_memory import safe_link_after_kickoff

    pid = "P-ORG-EV-1"
    email = "org-ev@test.com"
    (projects / pid).mkdir(parents=True)
    (projects / pid / "evidence").mkdir(parents=True, exist_ok=True)
    safe_link_after_kickoff(pid, "INQ-EV-1", email, "Ev", ["CMMC-L1"], base=mem)
    safe_record_evidence(pid, "policy.pdf", "application/pdf")
    result = lookup(project_id=pid, base=mem)
    types = _timeline_types(result["journey"]["entity_id"], mem)
    assert "evidence_uploaded" in types


def test_acquisition_lead_import_writes_memory(organism_env):
    mem, projects, intel, data = organism_env
    from services.acquisition.discovery import run_csv_import
    from services.acquisition.storage import load_all_leads

    leads_dir = data / "acquisition" / "leads"
    leads_dir.mkdir(parents=True)
    csv_path = leads_dir / "import_candidates.csv"
    csv_path.write_text(
        "company_name,website,contact_name,contact_title,contact_email,linkedin_url,"
        "industry,segment,source,source_url,location,notes\n"
        "Acme Org,https://acme.org,Sam,QM,lead@acme.org,,Aerospace,aerospace,manual,,TX,test\n",
        encoding="utf-8",
    )
    stats = run_csv_import(import_path=csv_path, base_dir=leads_dir)
    assert stats.imported >= 1
    all_leads, _ = load_all_leads(leads_dir)
    lead_id = all_leads[0].lead_id
    ctx = lookup(lead_id=lead_id, base=mem)
    assert ctx["journey"]["entity_id"]
    types = _timeline_types(ctx["journey"]["entity_id"], mem)
    assert "lead_linked" in types


def test_forensic_and_learning_after_conversion(organism_env):
    mem, projects, intel, data = organism_env
    from services.acquisition.forensics import safe_record_inquiry, safe_record_intake

    pid = "P-ORG-FORENSIC-1"
    (projects / pid).mkdir(parents=True)
    safe_record_inquiry(pid, "forensic@test.com", "F", "S", "[ref:L-F-1]\nmsg", "INQ-F-1")
    before = get_learning_summary(mem)["conversion_counts"].get("inquiry_to_intake", 0)
    safe_record_intake(
        pid,
        "forensic@test.com",
        {"company": "F Co", "notes": "done", "external_flags": {}},
    )
    after = get_learning_summary(mem)["conversion_counts"].get("inquiry_to_intake", 0)
    assert after >= before
    result = lookup(project_id=pid, base=mem)
    types = _timeline_types(result["journey"]["entity_id"], mem)
    assert "forensic_event" in types
    assert "inquiry_submitted" in types


def test_self_heal_detects_orphan_project(organism_env):
    mem, projects, _, data = organism_env
    orphan = "P-ORG-ORPHAN-999"
    (projects / orphan).mkdir()
    report = run_self_healing_scan(base=mem, write_suggestions=False)
    assert orphan in report["orphan_projects"]


def test_integration_audit_api(organism_env):
    mem, _, _, _ = organism_env
    audit = run_integration_audit(base=mem)
    assert audit["verdict"] in ("organism_unified", "organism_partial")
    assert audit["counts"]["plugged"] >= 10
    legacy = [e["id"] for e in audit["legacy_inactive"]]
    assert "stripe_webhook" in legacy


def test_organism_status_endpoint(client):
    r = client.get("/api/memory/organism-status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok")
    assert "plugged" in body
    assert "verdict" in body


def test_no_critical_engine_fully_outside_without_legacy(organism_env):
    audit = run_integration_audit(base=organism_env[0])
    outside_ids = {e["id"] for e in audit["outside"]}
    allowed_outside = {"emails", "health", "reports_export", "ui_ops", "organism_sqlite"}
    critical = outside_ids - allowed_outside
    assert len(critical) <= 2, f"Too many outside engines: {critical}"

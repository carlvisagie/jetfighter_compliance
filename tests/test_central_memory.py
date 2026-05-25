"""Central KYC memory — one brain, many vessels."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.memory.central_memory import (
    link_event,
    link_inquiry,
    link_intake,
    link_lead,
    link_project,
    lookup,
    read_entity_context,
    reconstruct_journey,
    resolve_or_create_entity,
)
from services.memory.learning import get_learning_summary, record_learning_signal
from services.memory.self_healing import run_self_healing_scan


@pytest.fixture
def mem_tmp(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.timeline.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.signals.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.learning.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.self_healing.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.self_healing.PROJECTS", projects)
    monkeypatch.setattr("services.memory.central_memory.PROJECTS", projects)
    return mem, projects


def test_entity_created_from_lead(mem_tmp):
    mem, _ = mem_tmp
    eid = resolve_or_create_entity(email="lead@acme.com", company="Acme Defense", contact_name="Sam", base=mem)
    link_lead("L-TEST-0001", eid, {"source": "csv"}, base=mem)
    ctx = read_entity_context(lead_id="L-TEST-0001", base=mem)
    assert ctx["known"]
    assert ctx["entity_id"] == eid


def test_inquiry_links_to_entity(mem_tmp):
    mem, _ = mem_tmp
    eid = resolve_or_create_entity(email="inquiry@co.com", company="Co LLC", base=mem)
    link_inquiry("P-INQ-001", "INQ-001", eid, {"subject": "CMMC"}, base=mem)
    ctx = read_entity_context(project_id="P-INQ-001", base=mem)
    assert ctx["entity_id"] == eid
    types = [t["event_type"] for t in ctx["timeline"]]
    assert "inquiry_submitted" in types


def test_project_links_to_entity(mem_tmp):
    mem, projects = mem_tmp
    eid = resolve_or_create_entity(email="proj@test.com", base=mem)
    pid = "P-TEST-001"
    (projects / pid).mkdir()
    (projects / pid / "meta.json").write_text(
        json.dumps({"project_id": pid, "customer": {"email": "proj@test.com"}})
    )
    link_project(pid, eid, base=mem)
    assert read_entity_context(project_id=pid, base=mem)["entity_id"] == eid


def test_event_links_to_timeline(mem_tmp):
    mem, _ = mem_tmp
    eid = resolve_or_create_entity(email="evt@x.com", base=mem)
    link_event("EVT-1", eid, "P-1", base=mem)
    timeline = read_entity_context(entity_id=eid, base=mem)["timeline"]
    assert any(t["event_type"] == "ledger_event" for t in timeline)


def test_duplicate_company_detection(mem_tmp):
    from services.memory.entity_graph import append_entity, utc_now

    mem, _ = mem_tmp
    ts = utc_now()
    append_entity(
        {
            "entity_id": "E-dupco-0001",
            "entity_type": "organization",
            "display_name": "Duplicate Co A",
            "company_norm": "duplicate-co",
            "email_domain": "a.com",
            "refs": [],
            "created_utc": ts,
            "updated_utc": ts,
        },
        mem,
    )
    append_entity(
        {
            "entity_id": "E-dupco-0002",
            "entity_type": "organization",
            "display_name": "Duplicate Co B",
            "company_norm": "duplicate-co",
            "email_domain": "b.com",
            "refs": [],
            "created_utc": ts,
            "updated_utc": ts,
        },
        mem,
    )
    report = run_self_healing_scan(base=mem, write_suggestions=False)
    assert len(report["duplicate_companies"]) >= 1


def test_orphan_detection(mem_tmp):
    mem, projects = mem_tmp
    (projects / "P-ORPHAN-999").mkdir()
    report = run_self_healing_scan(base=mem, write_suggestions=False)
    assert "P-ORPHAN-999" in report["orphan_projects"]


def test_learning_state_updates(mem_tmp):
    mem, _ = mem_tmp
    record_learning_signal("urgency:audit", "inquiry_to_intake", success=True, segment="aerospace", base=mem)
    state = get_learning_summary(base=mem)
    assert state["signal_effectiveness"]["urgency:audit"]["success"] >= 1
    assert state["conversion_counts"]["inquiry_to_intake"] >= 1


def test_forensic_journey_reconstruction(mem_tmp):
    mem, projects = mem_tmp
    eid = resolve_or_create_entity(email="j@journey.com", company="Journey Inc", base=mem)
    pid = "P-JOURNEY-1"
    (projects / pid).mkdir(parents=True)
    (projects / "communications").mkdir(exist_ok=True)
    link_lead("L-J-1", eid, base=mem)
    link_inquiry(pid, "INQ-J-1", eid, base=mem)
    link_intake(pid, eid, {"company": "Journey Inc", "notes": "CMMC gap", "external_flags": {}}, base=mem)
    journey = reconstruct_journey(entity_id=eid, project_id=pid, lead_id="L-J-1", base=mem)
    assert journey["entity_id"] == eid
    assert len(journey["stages"]) >= 2


def test_lookup_api_shape(mem_tmp):
    mem, _ = mem_tmp
    eid = resolve_or_create_entity(email="look@up.com", base=mem)
    link_lead("L-UP-1", eid, base=mem)
    result = lookup(entity_id=eid, base=mem)
    assert "journey" in result
    assert "learning" in result
    assert "self_healing" in result

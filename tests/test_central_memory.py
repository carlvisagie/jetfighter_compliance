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
    safe_link_after_kickoff,
    safe_link_ledger_event,
    safe_write_after_inquiry,
    safe_write_after_intake,
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


def test_upsert_preserves_entity_refs(mem_tmp):
    mem, _ = mem_tmp
    eid = resolve_or_create_entity(email="refs@acme.com", company="Acme", base=mem)
    link_project("P-REF-1", eid, base=mem)
    resolve_or_create_entity(email="refs@acme.com", company="Acme", base=mem)
    ent = read_entity_context(entity_id=eid, base=mem)["entity"]
    ref_keys = {f"{r['ref_type']}:{r['ref_id']}" for r in (ent.get("refs") or [])}
    assert "project:P-REF-1" in ref_keys


def test_kickoff_journey_full_chain(mem_tmp):
    """lead/ref → inquiry → intake → project_created → ledger_event → lookup."""
    mem, projects = mem_tmp
    lead_ref = "organism-test-regression"
    email = "organism.regression@acme.test"
    order_id = "INQ-REG-001"
    project_id = "P-INQ-REG-001"
    evt_id = f"EVT-{project_id}-ORDER"

    (projects / project_id).mkdir(parents=True)
    (projects / project_id / "meta.json").write_text(
        json.dumps({"project_id": project_id, "customer": {"email": email, "name": "Regression"}})
    )
    (projects / project_id / "communications").mkdir(exist_ok=True)

    eid = safe_link_after_kickoff(project_id, order_id, email, "Regression", ["CMMC-L1"], lead_ref, base=mem)
    assert eid
    safe_link_ledger_event(
        evt_id,
        project_id,
        email=email,
        name="Regression",
        event_type="ATTEST",
        why="Onboarding started; project created",
        base=mem,
    )
    safe_write_after_inquiry(
        project_id,
        order_id,
        email,
        "Regression",
        "CMMC",
        f"[ref:{lead_ref}]\n\nOrganism regression inquiry.",
        lead_ref,
        base=mem,
    )
    safe_write_after_intake(
        project_id,
        email,
        {"company": "Acme Regression LLC", "notes": "intake done", "external_flags": {}},
        base=mem,
    )

    result = lookup(project_id=project_id, base=mem)
    journey = result["journey"]
    entity = journey["context"]["entity"]
    stage_types = [s["type"] for s in journey["stages"]]

    assert journey["entity_id"] == eid
    ref_keys = {f"{r['ref_type']}:{r['ref_id']}" for r in (entity.get("refs") or [])}
    assert f"project:{project_id}" in ref_keys
    assert f"lead:{lead_ref}" in ref_keys
    assert f"inquiry:{order_id}" in ref_keys
    assert f"email:{email}" in ref_keys
    assert "project_created" in stage_types
    assert "ledger_event" in stage_types
    assert "inquiry_submitted" in stage_types
    assert "lead_linked" in stage_types
    assert "intake_completed" in stage_types


def test_compact_entities_dedupes_history(mem_tmp):
    """REGRESSION GUARD — entity-graph compaction must keep only the
    most recent row per entity_id.

    The forensic audit (2026-06-04) flagged entities.jsonl as
    append-on-every-upsert, producing thousands of duplicate snapshots
    for a small entity set. compact_entities() rewrites the file
    atomically so read paths and inspection both see one row per id.
    """
    from services.memory.entity_graph import (
        compact_entities,
        load_entities,
        upsert_entity,
    )

    mem, _ = mem_tmp
    # Same entity (email + company), upserted many times.
    for i in range(12):
        upsert_entity(
            email="dup@compact.example.com",
            company="Compact Co",
            contact_name=f"Carl {i}",
            base=mem,
        )
    rows_before = len(load_entities(mem, limit=10_000))
    assert rows_before >= 12, (
        "expected many appended rows for a single entity; "
        f"got {rows_before}"
    )

    report = compact_entities(mem)
    assert report["ok"] is True
    assert report["compacted"] is True
    assert report["entities_kept"] == 1
    assert report["rows_after"] == 1
    assert report["rows_removed"] == rows_before - 1

    rows_after = load_entities(mem, limit=10_000)
    assert len(rows_after) == 1
    raw = (mem / "entities.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(raw) == 1
    kept = rows_after[0]
    assert kept["entity_id"].startswith("E-")
    assert kept.get("updated_utc"), (
        "compacted entity row must carry an updated_utc timestamp"
    )


def test_acquisition_weights_mirror_into_learning_state(mem_tmp, tmp_path,
                                                       monkeypatch):
    """REGRESSION GUARD — saving acquisition weights must also mirror
    them into central learning_state.json so the organism has one
    place to see what learning actually steers.

    Forensic-audit fix (2026-06-04, Central Memory): two parallel
    "learning" surfaces violated the one-brain doctrine. Mirroring is
    cheap, lossless, and gives the awareness layer a single observable.
    """
    mem, _ = mem_tmp
    intel_root = tmp_path / "intel"
    intel_root.mkdir()
    monkeypatch.setattr(
        "services.acquisition.intelligence_paths.ensure_intel_dirs",
        lambda base=None: intel_root,
    )

    from services.acquisition.memory import save_learned_weights
    from services.memory.learning import load_learning_state

    weights = {"segment_aerospace": 4.2, "intake_completed": 9.5}
    save_learned_weights(weights)

    state = load_learning_state()
    mirror = state.get("acquisition_weights") or {}
    assert mirror, "central learning_state must include acquisition_weights"
    assert mirror["values"]["segment_aerospace"] == 4.2
    assert mirror["values"]["intake_completed"] == 9.5
    assert mirror.get("mirrored_utc"), "mirror must carry a timestamp"

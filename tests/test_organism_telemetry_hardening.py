"""Organism telemetry hardening — emission, funnels, silent failures, beacons."""
from __future__ import annotations

import json

import pytest

from services.memory.telemetry import emit_telemetry, load_telemetry
from services.organism_observability import (
    compute_acquisition_funnel,
    compute_upload_funnel,
    detect_silent_failures,
    get_operator_cockpit_observability,
    organism_emit,
    record_customer_beacon,
)
from services.organism_observability.registry import learning_goal_for


@pytest.fixture
def tel_env(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    monkeypatch.setattr("services.memory.timeline.memory_dir", lambda base=None: mem or tmp_path / "memory")
    return mem


def test_organism_emit_persists_learning_goal(tel_env):
    rec = organism_emit(
        "customer_session",
        "upload_page_view",
        metadata={"session_id": "CS-test"},
        base=tel_env,
    )
    assert rec and rec.get("telemetry_id", "").startswith("TEL-")
    rows = load_telemetry(subsystem="customer_session", base=tel_env)
    assert any(r["event_type"] == "upload_page_view" for r in rows)
    row = [r for r in rows if r["event_type"] == "upload_page_view"][-1]
    assert row["metadata"].get("learning_goal")
    assert learning_goal_for("customer_session", "upload_page_view") in row["metadata"]["learning_goal"]


def test_customer_beacon_records_event(tel_env):
    out = record_customer_beacon("helper_opened", session_id="CS-beacon", metadata={"client": "desktop"})
    assert out["ok"] is True
    rows = load_telemetry(subsystem="customer_session", base=tel_env)
    assert any(r["event_type"] == "helper_opened" for r in rows)


def test_upload_funnel_metrics(tel_env):
    organism_emit("customer_session", "upload_page_view", base=tel_env)
    organism_emit("customer_session", "upload_started", base=tel_env)
    organism_emit("customer_session", "upload_completed", base=tel_env)
    funnel = compute_upload_funnel(base=tel_env, limit=100)
    assert funnel["page_views"] >= 1
    assert funnel["upload_started"] >= 1
    assert funnel["upload_completed"] >= 1
    assert funnel["health"] in ("healthy", "degraded", "critical")


def test_acquisition_funnel_aliases(tel_env):
    organism_emit(
        "reddit_acquisition",
        "reddit_discovery_started",
        metadata={"connector": "reddit"},
        base=tel_env,
    )
    organism_emit(
        "acquisition_organism",
        "acquisition_cycle_started",
        metadata={"source_event": "reddit_discovery_started"},
        base=tel_env,
    )
    organism_emit(
        "reddit_acquisition",
        "prey_scored",
        metadata={"prey_score": 72, "predator_penalty": 10},
        base=tel_env,
    )
    funnel = compute_acquisition_funnel(base=tel_env, limit=100)
    assert funnel["cycles_started"] >= 1
    assert funnel["prey_scored"] >= 1


def test_silent_failure_detection_zero_cycle(tel_env):
    organism_emit(
        "reddit_acquisition",
        "reddit_discovery_completed",
        metadata={"queued": 0, "discovered": 5},
        base=tel_env,
    )
    warnings = detect_silent_failures(base=tel_env, limit=200)
    ids = {w["id"] for w in warnings}
    assert "zero_result_acquisition" in ids


def test_operator_cockpit_dashboard_shape(tel_env, monkeypatch):
    organism_emit("knowledge_cockpit", "overlay_opened", metadata={"view": "reddit_panel"}, base=tel_env)
    organism_emit(
        "evidence_intelligence",
        "document_classified",
        metadata={"document_type": "policy", "confidence": 0.8},
        base=tel_env,
    )

    def fake_core(**kwargs):
        return {
            "audit_utc": "2026-01-01T00:00:00Z",
            "verdict": "ok",
            "subsystem_health": {},
            "telemetry_count": 3,
            "recommended_improvements": [],
        }

    monkeypatch.setattr(
        "services.memory.organism_observability.get_observability_dashboard",
        fake_core,
    )
    dash = get_operator_cockpit_observability(base=tel_env, telemetry_limit=100)
    assert dash["ok"] is True
    assert "upload_funnel" in dash
    assert "acquisition_funnel" in dash
    assert "silent_failure_warnings" in dash


def test_timeline_link_when_entity_present(tel_env, monkeypatch):
    timelines = []

    def fake_append(entity_id, event_type, subsystem, ref, payload, base=None):
        timelines.append({"entity_id": entity_id, "event_type": event_type})

    monkeypatch.setattr("services.memory.timeline.append_timeline", fake_append)
    monkeypatch.setattr(
        "services.memory.central_memory.find_entity_id",
        lambda project_id="", **kw: "ENT-test" if project_id == "P-1" else "",
    )
    organism_emit(
        "customer_session",
        "workspace_created",
        project_id="P-1",
        entity_id="ENT-test",
        link_timeline=True,
        base=tel_env,
    )
    assert len(timelines) >= 1
    assert timelines[-1]["entity_id"] == "ENT-test"

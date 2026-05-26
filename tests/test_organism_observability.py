"""Organism observability — telemetry is canonical signal log; not a parallel brain."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.emails import send_email_with_result
from services.memory.adaptive_signals import load_adaptive_signals
from services.memory.organism_observability import (
    get_observability_dashboard,
    load_system_patterns,
    refresh_system_patterns_from_telemetry,
)
from services.memory.self_healing import run_self_healing_scan
from services.memory.telemetry import emit_telemetry, load_telemetry
from services.reports import export_binder


@pytest.fixture
def obs_env(tmp_path, monkeypatch):
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
    monkeypatch.setattr("services.memory.self_healing.DATA", tmp_path)
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.reports.DATA", tmp_path)
    return mem, projects, tmp_path


def test_telemetry_append_works(obs_env):
    mem, _, _ = obs_env
    rec = emit_telemetry("test", "ping", success=True, message="hello", base=mem)
    assert rec and rec["telemetry_id"].startswith("TEL-")
    rows = load_telemetry(subsystem="test", base=mem)
    assert len(rows) >= 1
    assert rows[-1]["event_type"] == "ping"


def test_email_failure_emits_telemetry(obs_env, monkeypatch):
    mem, _, _ = obs_env
    monkeypatch.setattr("services.emails.SETTINGS.smtp_enabled", True)
    monkeypatch.setattr("services.emails.SETTINGS.smtp_host", "smtp.test")
    monkeypatch.setattr("services.emails.SETTINGS.smtp_user", "u")
    monkeypatch.setattr("services.emails.SETTINGS.smtp_pass", "p")
    monkeypatch.setattr("services.emails.SETTINGS.smtp_port", 587)
    monkeypatch.setattr("services.emails.SETTINGS.smtp_from_name", "T")
    monkeypatch.setattr("services.emails.SETTINGS.smtp_from_email", "t@test.com")

    def boom(*a, **k):
        raise ConnectionError("smtp down")

    monkeypatch.setattr("services.emails.smtplib.SMTP", boom)
    result = send_email_with_result("x@y.com", "subj", "<p>hi</p>")
    assert result.get("ok") is False
    assert result.get("error") == "ConnectionError"
    fails = load_telemetry(subsystem="email", base=mem)
    types = [r["event_type"] for r in fails]
    assert "send_attempted" in types
    assert "send_failed" in types


def test_report_generation_emits_telemetry(obs_env):
    mem, projects, data = obs_env
    pid = "P-OBS-REPORT"
    pdir = projects / pid
    pdir.mkdir()
    (pdir / "meta.json").write_text(json.dumps({"project_id": pid}))
    export_binder(pid)
    types = [r["event_type"] for r in load_telemetry(subsystem="reports", base=mem)]
    assert "report_generated" in types
    assert "binder_generated" in types


def test_health_readiness_emits_telemetry(obs_env):
    mem, _, _ = obs_env
    emit_telemetry("health", "readiness_failed", severity="error", success=False, base=mem)
    emit_telemetry("health", "smtp_unconfigured", severity="warning", success=False, base=mem)
    emit_telemetry("health", "memory_orphan_count", metadata={"orphan_projects": 3}, base=mem)
    types = [r["event_type"] for r in load_telemetry(subsystem="health", base=mem)]
    assert "readiness_failed" in types
    assert "smtp_unconfigured" in types


def test_job_failure_emits_telemetry(obs_env):
    mem, _, data = obs_env
    emit_telemetry(
        "job_queue",
        "job_failed",
        success=False,
        severity="error",
        message="simulated failure",
        base=mem,
    )
    emit_telemetry("job_queue", "retry_scheduled", success=False, base=mem)
    rows = load_telemetry(subsystem="job_queue", base=mem)
    assert any(r["event_type"] == "job_failed" for r in rows)


def test_acquisition_scoring_emits_telemetry(obs_env):
    mem, _, _ = obs_env
    from services.acquisition.models import Lead
    from services.acquisition.scoring import score_lead_full

    lead = Lead(
        lead_id="L-OBS-1",
        company_name="Acme",
        contact_email="a@acme.com",
        segment="aerospace",
        source="test",
    )
    score_lead_full(lead, memory_context={"known": False})
    types = [r["event_type"] for r in load_telemetry(subsystem="acquisition", base=mem)]
    assert "lead_scored" in types


def test_self_heal_reads_telemetry(obs_env):
    mem, projects, _ = obs_env
    emit_telemetry("email", "send_failed", success=False, severity="error", message="x", base=mem)
    emit_telemetry("email", "send_failed", success=False, severity="error", message="y", base=mem)
    report = run_self_healing_scan(base=mem, write_suggestions=True)
    assert report.get("telemetry_failure_count", 0) >= 2
    assert report.get("suggestions_written", 0) >= 1


def test_system_patterns_updates(obs_env):
    mem, _, _ = obs_env
    emit_telemetry("reports", "binder_generated", success=True, base=mem)
    emit_telemetry("reports", "export_failed", success=False, base=mem)
    state = refresh_system_patterns_from_telemetry(base=mem)
    assert state.get("subsystem_health")
    assert "reports" in state["subsystem_health"]
    loaded = load_system_patterns(base=mem)
    assert loaded.get("updated_utc")


def test_no_subsystem_becomes_canonical_truth(obs_env):
    mem, _, _ = obs_env
    emit_telemetry("email", "send_success", base=mem)
    tel_path = mem / "telemetry.jsonl"
    assert tel_path.exists()
    entities = mem / "entities.jsonl"
    assert not (mem / "email_truth.json").exists()
    dash = get_observability_dashboard(telemetry_limit=50, base=mem)
    assert dash["verdict"] in ("organism_observable", "partially_observable", "not_observable")
    assert len(load_adaptive_signals(base=mem)) >= 0


def test_observability_api_shape(client):
    r = client.get("/api/memory/telemetry?limit=10")
    assert r.status_code == 200
    assert "telemetry" in r.json()
    r2 = client.get("/api/memory/observability")
    assert r2.status_code == 200
    assert "verdict" in r2.json()

"""Telemetry diagnostics — COTE actionable status (no synthetic telemetry)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from services.memory.telemetry import emit_telemetry
from services.telemetry_diagnostics import build_telemetry_status


@pytest.fixture
def tel_data(monkeypatch, tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir(parents=True)
    jobs = tmp_path / "jobs"
    jobs.mkdir(parents=True)
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.telemetry_diagnostics.DATA", tmp_path)
    monkeypatch.setattr("services.telemetry_diagnostics._JOBS_DIR", jobs)
    monkeypatch.setattr("services.cognitive_topology.DATA", tmp_path)
    monkeypatch.setattr("services.cognitive_topology._TELEMETRY", mem / "telemetry.jsonl")
    monkeypatch.setattr(
        "services.memory.telemetry.memory_dir", lambda base=None: mem
    )
    return tmp_path


def test_healthy_flow(tel_data, monkeypatch):
    monkeypatch.setattr(
        "services.organism_observability.health.detect_silent_failures",
        lambda **kw: [],
    )
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = tel_data / "memory" / "telemetry.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "subsystem": "intake",
        "event_type": "upload_completed",
        "success": True,
        "observed_at_utc": when,
        "message": "ok",
    }
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    status = build_telemetry_status()
    assert status["telemetry_health"] == "healthy"
    assert status["telemetry_pulse"] == "healthy_flow"
    assert status["stale_threshold_exceeded"] is False
    assert status["telemetry_sample_count"] >= 1


def test_stale_telemetry(tel_data):
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = tel_data / "memory" / "telemetry.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "subsystem": "system",
                "event_type": "heartbeat",
                "success": True,
                "observed_at_utc": old,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    status = build_telemetry_status()
    assert status["stale_threshold_exceeded"] is True
    assert status["telemetry_pulse"] in ("stale", "degraded")
    codes = {r["code"] for r in status["degraded_reasons"]}
    assert "stale_telemetry" in codes


def test_queue_backlog(tel_data):
    jobs = tel_data / "jobs"
    for i in range(55):
        (jobs / f"J-test-{i}.json").write_text("{}", encoding="utf-8")
    status = build_telemetry_status()
    assert status["queue_depth"] >= 55
    assert status["telemetry_pulse"] == "backlog"
    assert any(r["code"] == "queue_backup" for r in status["degraded_reasons"])


def test_write_failure_detected(tel_data, monkeypatch):
    p = tel_data / "memory" / "telemetry.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "subsystem": "organism_health",
                "event_type": "telemetry_write_failed",
                "success": False,
                "observed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "message": "disk full",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    import services.organism_observability.emit as emit_mod

    monkeypatch.setattr(emit_mod, "_write_failures", 2)
    status = build_telemetry_status()
    assert status["telemetry_health"] == "failed"
    assert status["telemetry_pulse"] == "write_failure"
    assert any(r["code"] == "write_failure" for r in status["degraded_reasons"])


def test_telemetry_recovery_after_fresh_write(tel_data, monkeypatch):
    monkeypatch.setattr(
        "services.organism_observability.health.detect_silent_failures",
        lambda **kw: [],
    )
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = tel_data / "memory" / "telemetry.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {"subsystem": "a", "event_type": "old", "success": True, "observed_at_utc": old}
        )
        + "\n"
        + json.dumps(
            {"subsystem": "b", "event_type": "fresh", "success": True, "observed_at_utc": now}
        )
        + "\n",
        encoding="utf-8",
    )
    status = build_telemetry_status()
    assert status["telemetry_health"] == "healthy"
    assert status["stale_threshold_exceeded"] is False


def test_parser_failure(tel_data):
    p = tel_data / "memory" / "telemetry.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json}\n", encoding="utf-8")
    status = build_telemetry_status()
    assert status["parse_error_count"] >= 1
    assert any(r["code"] == "parser_failure" for r in status["degraded_reasons"])


def test_telemetry_status_endpoint(client, tel_data):
    emit_telemetry("intake", "test_event", message="probe")
    r = client.get("/api/operator/telemetry-status")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "telemetry_health" in body
    assert "degraded_reasons" in body
    assert "telemetry_storage_path" in body
    assert body["telemetry_sample_count"] >= 1


def test_topology_telemetry_carries_pulse(client, tel_data):
    emit_telemetry("intake", "topology_probe", message="ok")
    r = client.get("/api/cognitive-topology")
    assert r.status_code == 200
    tel = r.json()["subsystems"]["telemetry"]
    assert tel.get("telemetry_pulse") in (
        "healthy_flow",
        "stale",
        "write_failure",
        "backlog",
        "degraded",
        "",
    )
    assert "telemetry_status" in tel

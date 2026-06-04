"""COTE — cognitive operational topology engine."""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import services.cognitive_topology as ct


@pytest.fixture
def topo_client(monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("KYC_SCHEDULERS_ENABLED", raising=False)
    import services.engine as engine_mod
    import services.runtime_boot as boot_mod
    import server as server_mod

    engine_mod.scheduler = None
    boot_mod._BOOT_LOG.clear()
    importlib.reload(server_mod)
    with TestClient(server_mod.app) as c:
        from tests.conftest import login_ops

        login_ops(c)
        yield c


def test_topology_endpoint_fast_no_orchestration(topo_client):
    for name in list(sys.modules):
        if name == "services.acquisition.orchestration":
            del sys.modules[name]
    t0 = time.perf_counter()
    r = topo_client.get("/api/cognitive-topology")
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    assert elapsed < 4.0
    body = r.json()
    assert body.get("ok") is True
    assert "subsystems" in body
    assert "system_health" in body
    subs = body["subsystems"]
    for key in (
        "acquisition",
        "knowledge",
        "observability",
        "upload_pipeline",
        "evidence_processing",
        "learning",
        "telemetry",
        "alerts",
        "system_health",
    ):
        assert key in subs
        assert "health" in subs[key]
        assert "pressure" in subs[key]
        assert "activity" in subs[key]
    assert "services.acquisition.orchestration" not in sys.modules


def test_topology_safe_mode_marks_paused_modules(topo_client):
    r = topo_client.get("/api/cognitive-topology")
    body = r.json()
    assert body.get("safe_mode") is True
    assert body["subsystems"]["acquisition"]["paused"] is True
    assert body["subsystems"]["knowledge"]["paused"] is True
    assert body["subsystems"]["observability"]["paused"] is True
    assert body["subsystems"]["upload_pipeline"]["paused"] is False


def test_topology_loads_in_safe_mode(topo_client):
    for _ in range(5):
        r = topo_client.get("/api/cognitive-topology")
        assert r.status_code == 200
        assert r.json().get("ok") is True


def test_control_html_includes_cote(client):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    text = r.text
    assert "cote-topology-section" in text
    assert "cognitive-topology.js" in text
    assert "cognitive-topology.css" in text
    assert "CoteTopology" in text or "cognitive-topology.js" in text
    assert "Healthy (still)" in text
    assert "Motion appears only when attention is required" in text


def test_cognitive_topology_module_import_lightweight():
    """Only drop orchestration — do not evict connectors.* from sys.modules (breaks reddit test mocks)."""
    for name in ("services.acquisition.orchestration",):
        sys.modules.pop(name, None)
    import services.cognitive_topology as ct

    importlib.reload(ct)
    assert "services.acquisition.orchestration" not in sys.modules
    out = ct.build_cognitive_topology()
    assert out["ok"] is True


def test_repeated_topology_no_memory_spike(topo_client):
    sizes = []
    for _ in range(20):
        r = topo_client.get("/api/cognitive-topology")
        assert r.status_code == 200
        sizes.append(len(r.content))
    assert max(sizes) - min(sizes) < 5000


def test_control_html_stable_refresh(client):
    for _ in range(10):
        r = client.get("/ui/control.html")
        assert r.status_code == 200
        assert "cote-topology-mount" in r.text


@pytest.fixture
def cote_isolated(monkeypatch, tmp_path):
    """Isolated DATA paths for learning health classification tests."""
    mem = tmp_path / "memory"
    mem.mkdir(parents=True)
    alerts = tmp_path / "alerts"
    alerts.mkdir(parents=True)
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    telem = mem / "telemetry.jsonl"
    telem.write_text("", encoding="utf-8")
    learning = mem / "learning_state.json"
    monkeypatch.setattr(ct, "DATA", tmp_path)
    monkeypatch.setattr(ct, "PROJECTS", projects)
    monkeypatch.setattr(ct, "_TELEMETRY", telem)
    monkeypatch.setattr(ct, "_ALERTS", alerts / "alerts.jsonl")
    monkeypatch.setattr(ct, "_LEARNING", learning)
    return {"mem": mem, "learning": learning, "telem": telem}


def _write_learning(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _learning_subsystem(cote_isolated, monkeypatch) -> dict:
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    out = ct.build_cognitive_topology()
    return out["subsystems"]["learning"]


def test_learning_missing_state_warming_up(cote_isolated, monkeypatch):
    learn = _learning_subsystem(cote_isolated, monkeypatch)
    assert learn["learning_status"] == "warming_up"
    assert learn["health"] >= 0.55
    assert not any("Learning health degraded" in a for a in ct.build_cognitive_topology()["operator_attention_required"])


def test_learning_unreadable_degraded(cote_isolated, monkeypatch):
    cote_isolated["learning"].write_bytes(b"\xff\xfe")
    learn = _learning_subsystem(cote_isolated, monkeypatch)
    assert learn["learning_status"] == "degraded"
    assert learn["health"] < 0.55


def test_learning_corrupt_json_degraded(cote_isolated, monkeypatch):
    cote_isolated["learning"].write_text("{not-json", encoding="utf-8")
    learn = _learning_subsystem(cote_isolated, monkeypatch)
    assert learn["learning_status"] == "degraded"


def test_learning_cycle_error_failed(cote_isolated, monkeypatch):
    _write_learning(
        cote_isolated["learning"],
        {
            "version": 1,
            "status": "failed",
            "updated_utc": "2026-05-28T12:00:00Z",
            "last_cycle_error": "index rebuild failed",
            "signal_effectiveness": {},
            "conversion_counts": {},
        },
    )
    learn = _learning_subsystem(cote_isolated, monkeypatch)
    assert learn["learning_status"] == "failed"
    assert "index rebuild" in (learn.get("learning_reason") or "")


def test_learning_with_signals_healthy(cote_isolated, monkeypatch):
    # Use a dynamic recent timestamp so this test does not silently
    # cross the 168h staleness threshold over wall-clock time
    # (previous hardcoded date became stale on 2026-06-04).
    from datetime import datetime, timezone

    recent_utc = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    _write_learning(
        cote_isolated["learning"],
        {
            "version": 1,
            "updated_utc": recent_utc,
            "signal_effectiveness": {
                "inquiry_submitted": {"success": 12, "fail": 0, "outcomes": []},
            },
            "conversion_counts": {
                "lead_to_inquiry": 5,
                "inquiry_to_intake": 3,
                "intake_to_evidence": 2,
                "lead_failed": 0,
            },
        },
    )
    learn = _learning_subsystem(cote_isolated, monkeypatch)
    assert learn["learning_status"] == "healthy"
    assert learn["uploads_seen"] >= 2
    assert learn["health"] >= 0.7


def test_mvp_no_history_not_marked_degraded(cote_isolated, monkeypatch):
    _write_learning(
        cote_isolated["learning"],
        {
            "version": 1,
            "status": "warming_up",
            "cycles_completed": 0,
            "approvals_seen": 0,
            "uploads_seen": 0,
            "last_learning_event": None,
            "updated_utc": "2026-05-28T12:00:00Z",
            "signal_effectiveness": {},
            "conversion_counts": {
                "lead_to_inquiry": 0,
                "inquiry_to_intake": 0,
                "intake_to_evidence": 0,
                "lead_failed": 0,
            },
        },
    )
    topo = ct.build_cognitive_topology()
    learn = topo["subsystems"]["learning"]
    assert learn["learning_status"] == "warming_up"
    assert learn["health"] >= 0.55
    assert not any("Learning health degraded" in x for x in topo["operator_attention_required"])


def test_learning_telemetry_failures_degraded(cote_isolated, monkeypatch):
    from datetime import datetime, timezone

    recent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_learning(
        cote_isolated["learning"],
        {
            "version": 1,
            "updated_utc": "2026-05-28T12:00:00Z",
            "signal_effectiveness": {"x": {"success": 1, "fail": 0, "outcomes": []}},
            "conversion_counts": {"intake_to_evidence": 1},
        },
    )
    lines = [
        json.dumps(
            {
                "subsystem": "learning",
                "event_type": "cycle",
                "success": False,
                "observed_at_utc": recent,
            }
        )
    ]
    cote_isolated["telem"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    learn = _learning_subsystem(cote_isolated, monkeypatch)
    assert learn["learning_status"] in ("degraded", "failed")

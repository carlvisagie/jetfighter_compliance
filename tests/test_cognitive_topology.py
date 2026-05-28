"""COTE — cognitive operational topology engine."""
from __future__ import annotations

import importlib
import sys
import time

import pytest
from fastapi.testclient import TestClient


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
    assert elapsed < 2.0
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

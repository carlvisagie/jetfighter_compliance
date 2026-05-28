"""COTE renderer hardening — API shape + node normalization suite."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import importlib

import services.cognitive_topology as ct
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def topo_client(monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
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


def test_sanitize_fills_missing_subsystems():
    raw = {
        "ok": True,
        "subsystems": {
            "acquisition": {"health": 0.8, "pressure": 0.1, "activity": 0.2, "confidence": 0.7, "latency": 0.05, "alerts": 0},
            "telemetry": None,
        },
    }
    out = ct.sanitize_topology_payload(raw)
    assert isinstance(out["subsystems"]["telemetry"], dict)
    assert out["subsystems"]["telemetry"].get("_cote_uncertain") is True
    for key in ct._RING_KEYS:
        assert key in out["subsystems"]
        assert isinstance(out["subsystems"][key], dict)


def test_topology_api_always_has_ring_nodes(topo_client):
    r = topo_client.get("/api/cognitive-topology")
    assert r.status_code == 200
    subs = r.json()["subsystems"]
    for key in ct._RING_KEYS:
        assert key in subs
        assert isinstance(subs[key], dict)
        assert "health" in subs[key]


def test_topology_survives_null_subsystem_in_build(monkeypatch):
    orig = ct.build_cognitive_topology

    def _wrapped():
        out = orig()
        out["subsystems"]["upload_pipeline"] = None
        return ct.sanitize_topology_payload(out)

    monkeypatch.setattr(ct, "build_cognitive_topology", _wrapped)
    out = ct.build_cognitive_topology()
    up = out["subsystems"]["upload_pipeline"]
    assert isinstance(up, dict)
    assert up.get("_cote_uncertain") is True


def test_cote_renderer_node_suite():
    script = ROOT / "tests" / "cote_renderer_hardening.mjs"
    try:
        r = subprocess.run(
            ["node", str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("node not installed")
    if r.returncode != 0 and "not recognized" in (r.stderr or "").lower():
        pytest.skip("node not on PATH")
    assert r.returncode == 0, r.stdout + r.stderr

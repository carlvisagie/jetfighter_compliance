"""KYC_SAFE_MODE — no schedulers at startup; healthz stays hot."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def safe_client(monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    monkeypatch.setenv("KYC_DEFER_SCHEDULER_SEC", "0")
    import services.engine as engine_mod
    import services.runtime_boot as boot_mod
    import server as server_mod

    engine_mod.scheduler = None
    boot_mod._BOOT_LOG.clear()
    importlib.reload(server_mod)
    with TestClient(server_mod.app) as c:
        yield c
    engine_mod.scheduler = None


def test_healthz_twenty_times(safe_client):
    for _ in range(20):
        r = safe_client.get("/healthz")
        assert r.status_code == 200
        assert r.json().get("ok") is True


def test_control_html_twenty_times(client):
    for _ in range(20):
        r = client.get("/ui/control.html")
        assert r.status_code == 200
        assert "Operator cockpit" in r.text


def test_no_scheduler_in_safe_mode(safe_client):
    import services.engine as engine_mod

    assert engine_mod.scheduler is None


def test_boot_status_reports_safe_mode(safe_client):
    r = safe_client.get("/api/ops/boot-status")
    assert r.status_code == 200
    body = r.json()
    assert body.get("safe_mode") is True
    assert any(e.get("component") == "worker" and e.get("status") == "skipped" for e in body.get("entries", []))


def test_reddit_run_blocked_in_safe_mode(client, monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    from services.runtime_boot import is_safe_mode

    assert is_safe_mode()
    r = client.post(
        "/api/operator/reddit-acquisition/run",
        json={"queries": ["test"], "max_posts": 1},
    )
    assert r.status_code == 503
    assert r.json().get("error_code") == "safe_mode"

"""Stage 2 stabilization — import isolation, safe-mode guards, lazy memory I/O."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def safe_client(monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("KYC_SCHEDULERS_ENABLED", raising=False)
    monkeypatch.setenv("KYC_ENABLE_MANUAL_ACQUISITION", "false")
    monkeypatch.setenv("KYC_ENABLE_KNOWLEDGE_OVERLAY", "false")
    monkeypatch.setenv("KYC_ENABLE_OBSERVABILITY", "false")
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
    engine_mod.scheduler = None


PAUSED_KEYS = {"ok", "safe_mode", "paused", "message"}


def _assert_paused(body: dict) -> None:
    assert body.get("ok") is False
    assert body.get("safe_mode") is True
    assert body.get("paused") is True
    assert "stabilization" in (body.get("message") or "").lower()


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/operator/reddit-acquisition"),
        ("GET", "/api/operator/acquisition-intelligence"),
        ("GET", "/api/operator/organism-observability"),
        ("POST", "/api/operator/knowledge-cockpit/overlay"),
        ("POST", "/api/operator/knowledge-cockpit/telemetry"),
    ],
)
def test_heavy_endpoints_return_paused_json_in_safe_mode(safe_client, method, path):
    if method == "GET":
        r = safe_client.get(path)
        assert r.status_code == 200
    else:
        r = safe_client.post(path, json={"view": "generic", "event_type": "test"})
        assert r.status_code == 200
    body = r.json()
    _assert_paused(body)


def test_reddit_run_returns_503_paused_in_safe_mode(safe_client):
    r = safe_client.post(
        "/api/operator/reddit-acquisition/run",
        json={"queries": ["test"], "max_posts": 1},
    )
    assert r.status_code == 503
    _assert_paused(r.json())


def test_safe_mode_get_reddit_does_not_import_orchestration(safe_client, monkeypatch):
    for name in list(sys.modules):
        if name.startswith("services.acquisition.orchestration"):
            del sys.modules[name]
    r = safe_client.get("/api/operator/reddit-acquisition")
    assert r.status_code == 200
    _assert_paused(r.json())
    assert "services.acquisition.orchestration" not in sys.modules


def test_safe_mode_get_acquisition_does_not_import_orchestration(safe_client, monkeypatch):
    for name in list(sys.modules):
        if name.startswith("services.acquisition.orchestration"):
            del sys.modules[name]
    r = safe_client.get("/api/operator/acquisition-intelligence")
    assert r.status_code == 200
    _assert_paused(r.json())
    assert "services.acquisition.orchestration" not in sys.modules


def test_import_acquisition_package_has_no_orchestration_side_effect():
    code = """
import sys
for k in list(sys.modules):
    if k == "services.acquisition.orchestration":
        del sys.modules[k]
import services.acquisition
assert "services.acquisition.orchestration" not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO),
        check=True,
        env={**dict(**os.environ), "PYTHONPATH": str(REPO)},
    )


def test_control_html_includes_safe_boot_assets(client):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    assert "cockpit-stabilization.js" in r.text
    assert "COCKPIT_SAFE_MODE" in r.text
    assert "Promise.allSettled" in r.text


def test_app_startup_does_not_read_entities_jsonl(monkeypatch):
    reads: list[str] = []
    orig_read_text = Path.read_text

    def tracking_read(self, *args, **kwargs):
        path_s = str(self).replace("\\", "/")
        if "entities.jsonl" in path_s:
            reads.append(path_s)
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read)
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    import services.engine as engine_mod
    import services.runtime_boot as boot_mod
    import server as server_mod

    engine_mod.scheduler = None
    boot_mod._BOOT_LOG.clear()
    importlib.reload(server_mod)
    with TestClient(server_mod.app) as c:
        c.get("/healthz")
    assert not reads


def test_healthz_safe_mode_and_schedulers_off(safe_client):
    r = safe_client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["safe_mode"] is True
    assert body["schedulers_enabled"] is False


def test_no_scheduler_registration_in_safe_mode(safe_client):
    import services.engine as engine_mod

    engine_mod.start_worker()
    assert engine_mod.scheduler is None


def test_failed_endpoint_payload_does_not_require_exception():
    """Paused JSON is a normal response shape for the cockpit."""
    from services.runtime_boot import module_pause_payload

    p = module_pause_payload("acquisition")
    assert p["paused"] is True
    assert p["ok"] is False


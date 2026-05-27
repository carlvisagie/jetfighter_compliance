"""Production runtime stability — healthz and non-blocking acquisition endpoints."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

def test_healthz_always_ok(client):
    for _ in range(5):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json().get("ok") is True


def test_health_ready_without_deep_scan(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert "checks" in body


def test_run_blocking_delegates_to_thread():
    from services.runtime_blocking import run_blocking

    def slow_add(a, b):
        return a + b

    out = asyncio.run(run_blocking(slow_add, 2, 3))
    assert out == 5


def test_reddit_run_endpoint_uses_thread_pool(client, monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    called = {"ok": False}

    def fake_cycle(**kwargs):
        return {"ok": True, "queued_for_operator": 0, "discovered": 0}

    async def mock_run_blocking(fn, /, *args, **kwargs):
        called["ok"] = True
        return fn(*args, **kwargs)

    with patch(
        "services.acquisition.connectors.reddit.run_reddit_acquisition_cycle",
        fake_cycle,
    ):
        with patch("services.runtime_blocking.run_blocking", side_effect=mock_run_blocking):
            r = client.post(
                "/api/operator/reddit-acquisition/run",
                json={"queries": ["test"], "max_posts": 1, "pause_seconds": 0},
            )
    assert r.status_code == 200
    assert called["ok"] is True


def test_static_cockpit_assets_exist(client):
    for path in (
        "/ui/assets/styles/design-system.css",
        "/ui/assets/js/cockpit-safe-boot.js",
        "/ui/assets/js/organism-intel.js",
    ):
        r = client.get(path)
        assert r.status_code == 200, path


def test_healthz_responsive_during_blocking_work(client, monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    """healthz must stay 200 while a blocking job runs in the thread pool."""

    def slow_cycle(**kwargs):
        import time

        time.sleep(0.3)
        return {"ok": True, "discovered": 0}

    async def passthrough(fn, /, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    with patch(
        "services.acquisition.connectors.reddit.run_reddit_acquisition_cycle",
        slow_cycle,
    ):
        with patch("services.runtime_blocking.run_blocking", side_effect=passthrough):
            import threading

            responses = []

            def run_post():
                responses.append(
                    client.post(
                        "/api/operator/reddit-acquisition/run",
                        json={"queries": ["x"], "max_posts": 1, "pause_seconds": 0},
                    ).status_code
                )

            t = threading.Thread(target=run_post)
            t.start()
            import time as _time

            _time.sleep(0.05)
            hz = client.get("/healthz")
            t.join(timeout=10)
            assert hz.status_code == 200
            assert hz.json().get("ok") is True
            assert responses and responses[0] == 200

"""Server-side protection for internal operator UI and APIs."""

from fastapi.testclient import TestClient

from server import app
from tests.conftest import TEST_OPS_PASSWORD

PUBLIC_UI = [
    "/ui/shop.html",
    "/ui/inquiry.html",
    "/ui/intake.html",
    "/ui/upload.html",
    "/ui/login.html",
]

PROTECTED_UI = [
    "/ui/control.html",
    "/ui/memory.html",
    "/ui/command.html",
    "/ui/status.html",
    "/ui/inbox.html",
    "/ui/webhook_test.html",
    "/ui/readiness/index.html",
]

PROTECTED_API = [
    "/api/memory/observability?limit=1",
    "/api/memory/learning",
    "/api/operator/cockpit",
    "/api/knowledge/catalog",
    "/api/projects",
    "/api/events/recent?limit=1",
]

PUBLIC_API = [
    "/healthz",
    "/health/ready",
]


def test_public_ui_open_without_session(anon_client):
    c = anon_client
    for path in PUBLIC_UI:
        r = c.get(path, follow_redirects=False)
        assert r.status_code == 200, path


def test_protected_ui_redirects_to_login(anon_client):
    c = anon_client
    for path in PROTECTED_UI:
        r = c.get(path, follow_redirects=False)
        assert r.status_code == 302, path
        assert "/ui/login.html" in (r.headers.get("location") or ""), path


def test_protected_ui_ok_with_session(ops_client):
    for path in PROTECTED_UI:
        r = ops_client.get(path)
        assert r.status_code == 200, path


def test_protected_api_returns_403_without_session(anon_client):
    c = anon_client
    for path in PROTECTED_API:
        r = c.get(path)
        assert r.status_code == 403, path
        assert r.json().get("detail") == "Unauthorized"


def test_protected_api_ok_with_session(ops_client):
    for path in PROTECTED_API:
        r = ops_client.get(path)
        assert r.status_code == 200, path


def test_public_api_and_health_open(anon_client):
    c = anon_client
    for path in PUBLIC_API:
        r = c.get(path)
        assert r.status_code == 200, path


def test_login_logout_flow(anon_client):
    c = anon_client
    bad = c.post("/api/ops/login", json={"password": "wrong"})
    assert bad.status_code == 401
    ok = c.post("/api/ops/login", json={"password": TEST_OPS_PASSWORD})
    assert ok.status_code == 200
    assert c.get("/api/ops/session").json()["authenticated"] is True
    assert c.get("/ui/control.html").status_code == 200
    c.post("/api/ops/logout")
    assert c.get("/api/ops/session").json()["authenticated"] is False
    assert c.get("/ui/control.html", follow_redirects=False).status_code == 302


def test_backup_ui_files_not_served(anon_client):
    c = anon_client
    for path in (
        "/ui/command.html.bak",
        "/ui/upload.backup-full-clean-rewrite.html",
        "/ui/intake.backup-qr.html",
    ):
        r = c.get(path)
        assert r.status_code == 404, path


def test_ops_api_key_still_works_production(monkeypatch, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPS_API_KEY", "prod-test-key")
    c = anon_client
    r = c.post(
        "/events/payment/test",
        json={"order_id": "X3", "email": "x3@y.com", "name": "X", "skus": ["T"]},
        headers={"X-Ops-Key": "prod-test-key"},
    )
    assert r.status_code == 200

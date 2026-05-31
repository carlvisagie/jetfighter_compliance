"""Operator auth contract — single path for scripts, middleware, and route handlers."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.ops_auth import OPS_API_KEY_HEADER, SESSION_COOKIE, auth_contract
from tests.conftest import TEST_OPS_PASSWORD

PRODUCTION_HTTP_SCRIPTS = [
    "scripts/verify_production_inventory.py",
    "scripts/prove_production_forensic.py",
    "scripts/archive_test_intakes.py",
    "scripts/investigate_prod_uploads.py",
    "scripts/run_prod_inventory_now.py",
]

FORBIDDEN_AUTH_PATTERNS = (
    "Authorization",
    "X-OPS-PASSWORD",
    "X-OPS-API-KEY",
    "Bearer ",
)


def test_production_scripts_use_ops_client():
    root = Path(__file__).resolve().parents[1]
    for rel in PRODUCTION_HTTP_SCRIPTS:
        text = (root / rel).read_text(encoding="utf-8")
        assert "scripts.lib.ops_client" in text, f"{rel} must import scripts.lib.ops_client"
        assert "authenticate_production" in text, f"{rel} must call authenticate_production"
        for bad in FORBIDDEN_AUTH_PATTERNS:
            assert bad not in text, f"{rel} must not use alternate auth {bad}"


def test_production_scripts_no_manual_x_ops_key_assignment():
    root = Path(__file__).resolve().parents[1]
    for rel in PRODUCTION_HTTP_SCRIPTS:
        text = (root / rel).read_text(encoding="utf-8")
        assert 'headers["X-Ops-Key"]' not in text, f"{rel} must not manually set X-Ops-Key"
        assert "headers['X-Ops-Key']" not in text, f"{rel} must not manually set X-Ops-Key"


def test_production_scripts_no_inline_env_loaders():
    root = Path(__file__).resolve().parents[1]
    for rel in PRODUCTION_HTTP_SCRIPTS:
        text = (root / rel).read_text(encoding="utf-8")
        assert ".kyc_ops_env" not in text, f"{rel} must not load alternate env files"
        assert "jetfighter_compliance" not in text, f"{rel} must not load path-specific .env"


def test_ops_client_rejects_ops_api_key(monkeypatch):
    from scripts.lib.ops_client import OpsAuthError, authenticate_production

    monkeypatch.setenv("OPS_API_KEY", "script-should-not-use-this")
    monkeypatch.delenv("OPS_PASSWORD", raising=False)
    with pytest.raises(OpsAuthError) as exc:
        authenticate_production(verify_deploy=False, base_url="http://127.0.0.1:1")
    assert exc.value.reason == "scripts_use_ops_password_only"


def test_ops_client_missing_password_points_to_ops_env(monkeypatch):
    from scripts.lib.ops_client import OpsAuthError, authenticate_production

    monkeypatch.delenv("OPS_API_KEY", raising=False)
    monkeypatch.delenv("OPS_PASSWORD", raising=False)
    with pytest.raises(OpsAuthError) as exc:
        authenticate_production(verify_deploy=False, base_url="http://127.0.0.1:1")
    assert exc.value.reason == "missing_env_var"


def test_build_info_public_no_secrets(anon_client: TestClient):
    r = anon_client.get("/api/public/build-info")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "jetfighter-compliance"
    assert "git_commit" in body
    assert "environment" in body
    text = r.text.lower()
    for forbidden in ("password", "secret", "api_key", "token", "data_root", "/var/data"):
        assert forbidden not in text


def test_auth_check_requires_ops(ops_client: TestClient, anon_client: TestClient):
    assert anon_client.get("/api/ops/auth-check").status_code == 403
    r = ops_client.get("/api/ops/auth-check")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["auth_mode"] == "session_cookie"
    assert body["service"] == "jetfighter-compliance"
    assert "data_root" in body
    assert "git_commit" in body


def test_auth_check_api_key_mode(monkeypatch, anon_client: TestClient):
    monkeypatch.setenv("OPS_API_KEY", "contract-test-key")
    r = anon_client.get("/api/ops/auth-check", headers={OPS_API_KEY_HEADER: "contract-test-key"})
    assert r.status_code == 200
    assert r.json()["auth_mode"] == "api_key"


def test_session_endpoint_exposes_contract(anon_client: TestClient):
    r = anon_client.get("/api/ops/session")
    assert r.status_code == 200
    body = r.json()
    assert "auth_contract" in body
    assert body["auth_contract"]["api_key_header"] == OPS_API_KEY_HEADER
    assert body["auth_contract"]["session_cookie"] == SESSION_COOKIE


def test_login_strips_password_whitespace(monkeypatch, anon_client: TestClient):
    monkeypatch.setenv("OPS_PASSWORD", TEST_OPS_PASSWORD)
    r = anon_client.post("/api/ops/login", json={"password": f"  {TEST_OPS_PASSWORD}  "})
    assert r.status_code == 200
    assert anon_client.get("/api/ops/auth-check").status_code == 200


def test_require_ops_access_same_as_middleware(ops_client: TestClient, anon_client: TestClient):
    assert anon_client.get("/api/operator/intake/diagnostics").status_code == 403
    assert ops_client.get("/api/operator/intake/diagnostics").status_code == 200


def test_auth_contract_constants():
    c = auth_contract()
    assert c["api_key_header"] == "X-Ops-Key"
    assert c["session_cookie"] == "kyc_ops_session"
    assert c["login_endpoint"] == "POST /api/ops/login"

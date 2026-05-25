import os

import pytest


def test_health_ready(anon_client):
    r = anon_client.get("/health/ready")
    assert r.status_code == 200
    j = r.json()
    assert "checks" in j
    assert j["checks"]["data_writable"] is True


def test_ops_routes_blocked_in_production(monkeypatch, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OPS_API_KEY", raising=False)
    r = anon_client.post(
        "/events/payment/test",
        json={"order_id": "X", "email": "x@y.com", "name": "X", "skus": ["T"]},
    )
    assert r.status_code == 403


def test_ops_routes_with_key(monkeypatch, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPS_API_KEY", "test-ops-key")
    r = anon_client.post(
        "/events/payment/test",
        json={"order_id": "X2", "email": "x2@y.com", "name": "X", "skus": ["T"]},
        headers={"X-Ops-Key": "test-ops-key"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_evidence_rejects_invalid_project(anon_client):
    r = anon_client.post(
        "/api/evidence/register?project_id=INVALID&media_type=document&owner=test",
        files={"file": ("a.txt", b"hi", "text/plain")},
    )
    assert r.status_code == 400

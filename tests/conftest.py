"""Shared test fixtures for operator authentication."""

import os

import pytest
from fastapi.testclient import TestClient

from server import app

TEST_OPS_PASSWORD = "test-ops-password-for-pytest"


@pytest.fixture(autouse=True)
def ops_password_env(monkeypatch):
    monkeypatch.setenv("OPS_PASSWORD", TEST_OPS_PASSWORD)
    monkeypatch.setenv("OPS_SECRET", "test-ops-secret-for-pytest")
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture
def anon_client():
    """Unauthenticated client (public routes + 403/302 checks)."""
    return TestClient(app)


@pytest.fixture
def client():
    """Authenticated operator session."""
    c = TestClient(app)
    r = c.post("/api/ops/login", json={"password": TEST_OPS_PASSWORD})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def ops_client(client):
    return client


def login_ops(c: TestClient) -> None:
    r = c.post("/api/ops/login", json={"password": TEST_OPS_PASSWORD})
    assert r.status_code == 200

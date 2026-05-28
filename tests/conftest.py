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


@pytest.fixture(autouse=True)
def _clear_knowledge_cockpit_caches():
    """Prevent lru_cache from retaining concepts loaded under a patched DATA root."""
    yield
    try:
        from services.knowledge_cockpit import concept_graph, encyclopedia

        encyclopedia._load_concepts_payload.cache_clear()
        encyclopedia.load_authoritative_sources.cache_clear()
        encyclopedia.load_control_matrix.cache_clear()
        encyclopedia.load_control_xref.cache_clear()
        concept_graph._edges.cache_clear()
    except Exception:
        pass


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


@pytest.fixture
def durable_paperwork_env(monkeypatch, tmp_path):
    """Isolated KYC_DATA root — same durable pipeline as production."""
    root = tmp_path.resolve()
    monkeypatch.setenv("KYC_DATA", str(root))
    monkeypatch.setattr("services.config.DATA", root)
    (root / "founding_beta" / "intakes").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def reddit_env(monkeypatch, tmp_path):
    """Isolated DATA tree for Reddit acquisition connector tests."""
    intel = tmp_path / "intelligence"
    intel.mkdir(parents=True)
    leads = tmp_path / "leads"
    leads.mkdir(parents=True)
    (leads / "leads.jsonl").write_text("", encoding="utf-8")
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    mem = tmp_path / "memory"
    mem.mkdir()

    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.acquisition.intelligence_paths.ACQ_ROOT", tmp_path)
    monkeypatch.setattr("services.acquisition.intelligence_paths.INTEL_DIR", intel)
    monkeypatch.setattr("services.acquisition.intelligence_paths.LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.DEFAULT_LEADS_DIR", leads)
    monkeypatch.setattr("services.acquisition.storage.leads_dir", lambda base_dir=None: leads)
    monkeypatch.setattr("services.acquisition.orchestration.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.telemetry.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.learning.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.acquisition.memory.ensure_intel_dirs", lambda base=None: intel)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    from services.acquisition.intelligence_paths import ensure_intel_dirs

    ensure_intel_dirs()
    return tmp_path

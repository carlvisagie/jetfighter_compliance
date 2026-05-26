"""Adaptive operator guidance engine and APIs."""

from fastapi.testclient import TestClient

from server import app
from services.memory.operator_guidance import build_operator_guidance
from tests.conftest import TEST_OPS_PASSWORD


def test_guidance_shape_empty_data(client):
    g = build_operator_guidance()
    assert g["priority_level"] in ("green", "yellow", "orange", "red", "critical")
    assert isinstance(g["next_actions"], list)
    assert isinstance(g["blocked_items"], list)
    assert isinstance(g["why_this_matters"], list)
    assert isinstance(g["recommended_learning"], list)
    assert isinstance(g["attention_targets"], list)
    assert g["organism_state"] in (
        "healthy",
        "degraded",
        "blind",
        "unstable",
        "learning",
        "blocked",
        "recovering",
    )
    assert 0 <= g["confidence"] <= 1
    assert g["priority_command"]["most_important_action"]


def test_bottlenecks_detect_smtp_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    g = build_operator_guidance()
    ids = [b["id"] for b in g["bottlenecks"]]
    assert "smtp" in ids or any("SMTP" in b.get("title", "") for b in g["bottlenecks"])


def test_learning_references_returned(client):
    g = build_operator_guidance()
    assert g["recommended_learning"]
    art = g["recommended_learning"][0]
    assert "title" in art
    assert "why_relevant_now" in art
    assert "snippet" in art


def test_guidance_api_protected(anon_client):
    r = anon_client.get("/api/operator/guidance")
    assert r.status_code == 403


def test_guidance_api_authenticated(client):
    r = client.get("/api/operator/guidance")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["guidance"]["organism_state"]


def test_bottlenecks_api(client):
    r = client.get("/api/operator/bottlenecks")
    assert r.status_code == 200
    assert "bottlenecks" in r.json()


def test_attention_api(client):
    r = client.get("/api/operator/attention")
    assert r.status_code == 200
    assert "attention_targets" in r.json()


def test_learning_api(client):
    r = client.get("/api/operator/learning?q=intake")
    assert r.status_code == 200
    assert "articles" in r.json()


def test_organism_state_api(client):
    r = client.get("/api/operator/organism-state")
    assert r.status_code == 200
    j = r.json()
    assert j["organism_state"]
    assert "summary" in j


def test_contextual_knowledge_index():
    from services.memory.knowledge_index import contextual_lookup

    items = contextual_lookup(triggers=["smtp_failure"], limit=3)
    assert items
    assert items[0].get("why_relevant_now")


def test_guidance_sparse_data_no_crash(client, tmp_path, monkeypatch):
    """Engine must not crash when memory/telemetry are minimal."""
    monkeypatch.setenv("OPS_PASSWORD", TEST_OPS_PASSWORD)
    g = build_operator_guidance(project_id="P-NONEXISTENT-999")
    assert g["priority_command"]

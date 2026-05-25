"""Operator cockpit and knowledge API tests."""

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_knowledge_catalog():
    r = client.get("/api/knowledge/catalog")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["topic_count"] >= 10
    assert j["glossary_count"] >= 5
    assert "fragmentation_note" in j


def test_knowledge_search_phase_filter():
    r = client.get("/api/knowledge/search?phase=acquisition_discovery")
    assert r.status_code == 200
    topics = r.json()["topics"]
    assert topics
    assert all("acquisition_discovery" in t["phases"] for t in topics)


def test_knowledge_topic_real_content():
    r = client.get("/api/knowledge/topic/launch-path")
    assert r.status_code == 200
    t = r.json()["topic"]
    assert t["source_path"] == "docs/LAUNCH_PATH.md"
    assert t["content_chars"] > 100
    assert not t["missing"]


def test_knowledge_topic_404():
    r = client.get("/api/knowledge/topic/does-not-exist")
    assert r.status_code == 404


def test_operator_cockpit_shape():
    r = client.get("/api/operator/cockpit")
    assert r.status_code == 200
    c = r.json()["cockpit"]
    assert "do_now" in c
    assert "why_it_matters" in c
    assert "guidance" in c
    assert "learn_phase" in c
    assert "knowledge_topic_ids" in c


def test_control_html_has_cockpit():
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    assert "Operator cockpit" in r.text
    assert "operator-cockpit.js" in r.text
    assert 'data-cockpit="command"' in r.text
    assert "Learn this step" in r.text


def test_knowledge_html_served():
    r = client.get("/ui/knowledge.html")
    assert r.status_code == 200
    assert "Operator knowledge base" in r.text

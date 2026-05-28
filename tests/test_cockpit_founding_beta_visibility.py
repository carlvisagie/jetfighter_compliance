"""Cockpit surfaces founding beta paperwork without scrolling."""
from __future__ import annotations

import io

import pytest


@pytest.fixture
def fb_env(monkeypatch, tmp_path):
    fb = tmp_path / "founding_beta"
    fb.mkdir(parents=True)
    (fb / "intakes").mkdir()
    monkeypatch.setattr("services.founding_beta.intake.DATA", tmp_path)
    monkeypatch.setattr("services.founding_beta.intake.INTAKES_ROOT", fb / "intakes")
    monkeypatch.setattr("services.founding_beta.intake.INDEX_JSONL", fb / "intakes_index.jsonl")
    monkeypatch.setattr("services.config.DATA", tmp_path)
    return tmp_path


def test_control_html_cockpit_paperwork_visibility(client):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    text = r.text
    assert "fb-paperwork-banner" in text
    assert "founding-beta-intake-panel" in text
    assert "fb-queue-atlas" in text
    assert "cockpit-founding-beta.js" in text
    assert "/api/operator/founding-beta/queue" in text
    assert "CockpitFoundingBeta" in text


def test_topology_attention_when_founding_beta_pending(client, fb_env, anon_client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("ssp.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
        data={"email": "vis@example.com", "company": "Visible Co"},
    )
    r = client.get("/api/cognitive-topology")
    assert r.status_code == 200
    body = r.json()
    up = body["subsystems"]["upload_pipeline"]
    assert up.get("pending_review", 0) >= 1 or up.get("queue_depth", 0) >= 1
    attention = " ".join(body.get("operator_attention_required") or [])
    assert "PAPERWORK" in attention.upper() or "founding beta" in attention.lower()


def test_founding_beta_queue_endpoint_ok(client, fb_env, anon_client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("notes.txt", io.BytesIO(b"policy"), "text/plain"))],
        data={"email": "q@example.com"},
    )
    r = client.get("/api/operator/founding-beta/queue")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("queue_depth", 0) >= 1
    assert len(body.get("queue") or []) >= 1

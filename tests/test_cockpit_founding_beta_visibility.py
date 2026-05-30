"""Cockpit surfaces founding beta paperwork without scrolling."""
from __future__ import annotations

import io


def test_control_html_cockpit_paperwork_visibility(client):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    text = r.text
    assert "fb-paperwork-banner" in text
    assert "founding-beta-intake-panel" in text
    assert "intake-queue-insights" in text
    assert "founding-beta-intake-insights" not in text
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
    from services.founding_beta.intake import intake_flow_metrics

    flow = intake_flow_metrics()
    assert flow.get("pending_review", 0) >= 1 or flow.get("queue_depth", 0) >= 1
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

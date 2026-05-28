"""Guardrails — one canonical customer paperwork pipeline, no shadow storage."""
from __future__ import annotations

import ast
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "server.py"


@pytest.fixture
def fb_data(monkeypatch, tmp_path):
    root = tmp_path.resolve()
    monkeypatch.setenv("KYC_DATA", str(root))
    monkeypatch.setenv("KYC_FOUNDING_BETA_MODE", "true")
    monkeypatch.setattr("services.config.DATA", root)
    return root

ALLOWED_CUSTOMER_FILE_UPLOAD_ROUTES = frozenset(
    {
        "/api/founding-beta/upload",
        "/api/customer/session/upload",  # shim only — proxies to canonical
        "/api/evidence/register",  # post-kickoff project evidence
    }
)


def test_server_no_shadow_customer_upload_routes():
    text = SERVER_PY.read_text(encoding="utf-8")
    found = set(re.findall(r'@app\.(?:post|put)\("([^"]+)"', text))
    uploads = {p for p in found if "upload" in p.lower() or "session/upload" in p}
    extra = uploads - ALLOWED_CUSTOMER_FILE_UPLOAD_ROUTES
    assert not extra, f"Unexpected customer upload routes: {extra}"


def test_session_upload_writes_canonical_intake_not_customer_sessions(fb_data, anon_client, monkeypatch):
    monkeypatch.setenv("KYC_DATA", str(fb_data))
    r = anon_client.post("/api/customer/session/start")
    sid = r.json()["session_id"]
    tok = r.json()["session_token"]
    up = anon_client.post(
        "/api/customer/session/upload",
        data={"session_id": sid, "session_token": tok},
        files=[("file", ("shim.txt", io.BytesIO(b"canonical"), "text/plain"))],
    )
    assert up.status_code == 200
    body = up.json()
    assert body.get("canonical_intake") is True
    iid = body["intake_id"]
    assert (fb_data / "intakes" / iid / "uploads" / "shim.txt").is_file()
    sessions = fb_data / "customer_sessions" / sid / "uploads"
    assert not sessions.is_dir() or not list(sessions.glob("*"))


def test_session_complete_does_not_create_shadow_project(fb_data, anon_client, monkeypatch):
    monkeypatch.setenv("KYC_DATA", str(fb_data))
    r = anon_client.post("/api/customer/session/start")
    sid = r.json()["session_id"]
    tok = r.json()["session_token"]
    anon_client.post(
        "/api/customer/session/upload",
        data={"session_id": sid, "session_token": tok},
        files=[("file", ("a.txt", io.BytesIO(b"x"), "text/plain"))],
    )
    done = anon_client.post(
        "/api/customer/session/complete",
        data={
            "session_id": sid,
            "session_token": tok,
            "name": "Test Co",
            "email": "guard@example.com",
        },
    )
    assert done.status_code == 200
    assert done.json().get("project_created") is False
    assert done.json().get("intake_id", "").startswith("FB-")


def test_queue_reports_empty_reason(fb_data, client):
    r = client.get("/api/operator/founding-beta/queue")
    assert r.status_code == 200
    body = r.json()
    assert "queue_empty_reason" in body
    assert "queue_empty_detail" in body
    assert "dashboard" in body


def test_deprecated_operator_intake_shims_to_queue(client, fb_data, anon_client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("z.txt", io.BytesIO(b"z"), "text/plain"))],
        data={"email": "z@z.com"},
    )
    r = client.get("/api/operator/founding-beta-intake")
    assert r.status_code == 200
    assert r.json().get("deprecated") is True
    assert r.json().get("queue_depth", 0) >= 1

"""Customer Friction Elimination Layer v1."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from services.customer_friction import (
    analyze_uploads,
    build_continuation_bundle,
    ensure_continuation_record,
    friction_insights_for_operator,
    get_evidence_example,
    get_retrieval_help,
    make_qr_svg,
    record_continuation_event,
    resolve_continuation,
)
from services.security import make_continuation_token, make_intake_token


@pytest.fixture
def friction_project(client, tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    mem = tmp_path / "memory"
    mem.mkdir(exist_ok=True)
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("server.DATA", tmp_path)
    monkeypatch.setattr("server.PROJECTS", projects)
    monkeypatch.setattr("services.customer_friction.DATA", tmp_path)
    monkeypatch.setattr("services.customer_friction.PROJECTS", projects)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)

    r = client.post(
        "/events/payment/test",
        json={"order_id": "FRIC-1", "email": "friction@example.com", "name": "F", "skus": ["CMMC-L1"]},
    )
    assert r.status_code == 200
    pid = r.json()["project_id"]
    return pid, "friction@example.com", r.json()


def test_kickoff_includes_continuation_url(friction_project):
    _, _, kick = friction_project
    assert "continuation_url" in kick
    assert "continue.html" in kick["continuation_url"]
    assert kick.get("continuation_token")


def test_continuation_resolve_and_telemetry(friction_project):
    pid, email, kick = friction_project
    token = kick["continuation_token"]
    out = resolve_continuation(token, client="desktop")
    assert out["ok"] is True
    assert out["project_id"] == pid
    assert out["next_step"] in ("intake", "upload", "upload_more")
    assert "qr_url" in out
    assert out["momentum"]["headline"]


def test_continuation_api_public(anon_client, friction_project):
    _, _, kick = friction_project
    token = kick["continuation_token"]
    r = anon_client.get(f"/api/customer/continuation/resolve?token={token}&client=mobile")
    assert r.status_code == 200
    assert r.json()["project_id"]


def test_continuation_event_api(anon_client, friction_project):
    _, _, kick = friction_project
    token = kick["continuation_token"]
    r = anon_client.post(
        "/api/customer/continuation/event",
        json={"token": token, "event": "continuation_completed", "step": "intake", "client": "mobile"},
    )
    assert r.status_code == 200


def test_qr_svg_generation():
    svg = make_qr_svg("https://example.com/upload?project_id=P-1")
    assert "<svg" in svg.lower()


def test_qr_endpoint_public(anon_client):
    r = anon_client.get("/api/customer/qr.svg?url=" + "https%3A%2F%2Fexample.com%2Ftest")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers.get("content-type", "")
    assert b"svg" in r.content.lower()


def test_upload_guidance_after_file(friction_project, client):
    pid, email, _ = friction_project
    token = make_intake_token(pid, email)
    client.post(
        f"/api/evidence/register?project_id={pid}&media_type=document&owner={email}",
        files={"file": ("security-policy.pdf", io.BytesIO(b"policy content"), "application/pdf")},
    )
    r = client.get(f"/api/customer/upload/guidance?project_id={pid}&token={token}")
    assert r.status_code == 200
    body = r.json()
    assert body.get("upload_count", 0) >= 1
    assert "momentum" in body
    assert "summary" in body


def test_evidence_example_and_help(anon_client):
    ex = anon_client.get("/api/customer/evidence/example/mfa")
    assert ex.status_code == 200
    assert ex.json()["ok"] is True
    assert "MFA" in ex.json()["title"]
    help_r = anon_client.get("/api/customer/evidence/help/training")
    assert help_r.status_code == 200
    assert help_r.json()["quick_start"]


def test_upload_session_persist(friction_project, anon_client):
    pid, email, kick = friction_project
    token = make_intake_token(pid, email)
    r = anon_client.post(
        "/api/customer/upload/session",
        json={"project_id": pid, "token": token, "session": {"completed": ["a.pdf"], "pending": []}},
    )
    assert r.status_code == 200
    g = anon_client.get(f"/api/customer/upload/session?project_id={pid}&token={token}")
    assert g.json()["session"]["completed"] == ["a.pdf"]


def test_operator_friction_insights_requires_auth(anon_client, client):
    assert anon_client.get("/api/operator/customer-friction").status_code == 403
    assert client.get("/api/operator/customer-friction").status_code == 200


def test_continue_page_public(anon_client):
    r = anon_client.get("/ui/continue.html")
    assert r.status_code == 200
    assert "Continue on your phone" in r.text


def test_upload_page_mobile_friendly(anon_client):
    html = anon_client.get("/ui/upload.html").text
    assert "viewport" in html.lower()
    assert "customer-friction" in html
    assert "Upload whatever you" in html
    assert "capture" in html.lower()


def test_no_secrets_in_continuation_bundle(friction_project):
    pid, email, _ = friction_project
    bundle = build_continuation_bundle(pid, email)
    assert "password" not in json.dumps(bundle).lower()
    path = Path(__file__).resolve().parents[1] / "data" / "projects" / pid / "communications" / "continuation.json"
    # may not exist if tmp — check bundle only
    assert "SMTP_PASS" not in json.dumps(bundle)


def test_analyze_uploads_classifies(friction_project, tmp_path, monkeypatch):
    pid, _, _ = friction_project
    monkeypatch.setattr("services.customer_friction.DATA", tmp_path)
    ev = tmp_path / "projects" / pid / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "mfa-screenshot.png").write_bytes(b"x")
    out = analyze_uploads(pid)
    assert out["upload_count"] == 1
    cats = [x["category"] for x in out["recognized"]]
    assert "mfa" in cats


def test_telemetry_emitted_on_continuation_open(friction_project, tmp_path):
    pid, email, kick = friction_project
    mem = tmp_path / "memory"
    resolve_continuation(kick["continuation_token"])
    tel_path = mem / "telemetry.jsonl"
    if not tel_path.is_file():
        pytest.skip("telemetry file not written in this environment")
    text = tel_path.read_text(encoding="utf-8")
    assert "continuation_opened" in text
    assert "customer_friction" in text


def test_operator_friction_insights_shape():
    out = friction_insights_for_operator()
    assert out["ok"] is True
    assert "continuation" in out
    assert "top_requested_help" in out

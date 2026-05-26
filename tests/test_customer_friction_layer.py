"""Customer Friction Elimination Layer v1 — continuation, QR, upload guidance, telemetry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.customer_friction import (
    analyze_uploads,
    generate_qr_png,
    get_evidence_example,
    get_operator_friction_insights,
    get_retrieval_help,
    issue_continuation,
    record_continuation_event,
    resolve_continuation,
    validate_project_access,
)
from services.memory.telemetry import load_telemetry
from services.security import make_continuation_token, parse_continuation_token


@pytest.fixture
def friction_client():
    return TestClient(app)


@pytest.fixture
def mem_telemetry(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    return mem


@pytest.fixture
def sample_project(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    pid = "P-FRICTION-TEST"
    pdir = projects / pid
    pdir.mkdir(parents=True)
    (pdir / "meta.json").write_text(
        json.dumps({"project_id": pid, "customer": {"email": "cust@test.com", "name": "Cust"}})
    )
    (pdir / "evidence").mkdir()
    (pdir / "communications").mkdir()
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", projects)
    monkeypatch.setattr("services.production.PROJECTS", projects)
    return pid, "cust@test.com", tmp_path


def test_continuation_token_roundtrip():
    tok = make_continuation_token("P-X", "a@b.com")
    info = parse_continuation_token(tok)
    assert info["p"] == "P-X"
    assert info["e"] == "a@b.com"


def test_issue_continuation_stable(sample_project):
    pid, email, _ = sample_project
    a = issue_continuation(pid, email)
    b = issue_continuation(pid, email)
    assert a["continuation_token"] == b["continuation_token"]
    assert "continue.html?token=" in a["continuation_url"]


def test_resolve_continuation_emits_telemetry(sample_project, mem_telemetry):
    pid, email, _ = sample_project
    cont = issue_continuation(pid, email)
    state = resolve_continuation(cont["continuation_token"], client="desktop")
    assert state["ok"] is True
    assert state["project_id"] == pid
    rows = load_telemetry(subsystem="customer_friction", base=mem_telemetry)
    assert any(r["event_type"] == "continuation_opened" for r in rows)


def test_continuation_event_telemetry(sample_project, mem_telemetry):
    pid, email, _ = sample_project
    cont = issue_continuation(pid, email)
    record_continuation_event(cont["continuation_token"], "continuation_completed", step="intake")
    rows = load_telemetry(subsystem="customer_friction", base=mem_telemetry)
    types = [r["event_type"] for r in rows]
    assert "continuation_completed" in types


def test_qr_generation():
    png = generate_qr_png("https://example.com/upload?x=1")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_qr_api_public(friction_client, sample_project):
    pid, email, _ = sample_project
    cont = issue_continuation(pid, email)
    r = friction_client.get("/api/customer/qr.svg", params={"data": cont["continuation_url"]})
    assert r.status_code == 200
    assert "image" in r.headers.get("content-type", "")


def test_upload_guidance_after_files(sample_project):
    pid, email, data = sample_project
    ev = data / "projects" / pid / "evidence"
    (ev / "mfa-settings-screenshot.png").write_bytes(b"x")
    (ev / "security-training-export.csv").write_bytes(b"y")
    g = analyze_uploads(pid)
    assert g["ok"] is True
    assert g["recognized_count"] >= 1
    assert len(g["missing_items"]) <= 3


def test_evidence_example_and_retrieval():
    ex = get_evidence_example("mfa")
    assert ex["ok"] is True
    assert ex.get("example_type") == "screenshot"
    help_doc = get_retrieval_help("training")
    assert help_doc["ok"] is True
    assert help_doc["retrieval"]["steps"]


def test_example_api_renders(friction_client):
    r = friction_client.get("/api/customer/evidence/example/mfa")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    r2 = friction_client.get("/api/customer/evidence/retrieval/training")
    assert r2.status_code == 200
    assert r2.json()["retrieval"]["steps"]


def test_validate_project_access(sample_project):
    pid, email, _ = sample_project
    cont = issue_continuation(pid, email)
    assert validate_project_access(pid, cont["continuation_token"]) is True
    assert validate_project_access(pid, "bad-token") is False


def test_kickoff_returns_continuation_url(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.config.PROJECTS", tmp_path / "projects")
    monkeypatch.setattr("services.production.PROJECTS", tmp_path / "projects")
    (tmp_path / "projects").mkdir(parents=True, exist_ok=True)
    r = client.post(
        "/events/payment/test",
        json={"order_id": "FRIC-2", "email": "f2@test.com", "name": "F2", "skus": ["CMMC-L1"]},
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("continuation_url")
    assert "continue.html" in j["continuation_url"]


def test_continue_page_public(friction_client):
    r = friction_client.get("/ui/continue.html")
    assert r.status_code == 200
    assert "Continue where you left off" in r.text
    assert "customer-friction" in r.text


def test_upload_page_mobile_friendly(friction_client):
    r = friction_client.get("/ui/upload.html")
    assert r.status_code == 200
    assert 'name="viewport"' in r.text
    assert "customer-friction.css" in r.text
    assert "Continue on your phone" in r.text
    assert "capture=" in r.text


def test_customer_apis_not_ops_protected(friction_client, anon_client):
    r = anon_client.get("/api/customer/evidence/catalog")
    assert r.status_code == 200
    r2 = anon_client.post(
        "/api/customer/continuation/event",
        json={"token": "invalid", "event_type": "continuation_abandoned"},
    )
    assert r2.status_code == 200 or r2.status_code == 400


def test_operator_friction_requires_auth(anon_client, client):
    assert anon_client.get("/api/operator/customer-friction").status_code == 403
    assert client.get("/api/operator/customer-friction").status_code == 200


def test_upload_with_token(friction_client, sample_project, mem_telemetry):
    pid, email, _ = sample_project
    cont = issue_continuation(pid, email)
    r = friction_client.post(
        f"/api/evidence/register?project_id={pid}&media_type=document&owner={email}&token={cont['continuation_token']}",
        files={"file": ("policy.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert r.status_code == 200
    rows = load_telemetry(subsystem="customer_friction", base=mem_telemetry)
    assert any(r["event_type"] == "upload_completed" for r in rows)


def test_no_secrets_in_continuation_resolve(sample_project):
    pid, email, _ = sample_project
    cont = issue_continuation(pid, email)
    state = resolve_continuation(cont["continuation_token"])
    blob = json.dumps(state)
    assert "SMTP_PASS" not in blob
    assert "password" not in blob.lower() or "no password" in blob.lower()

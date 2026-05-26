"""Pre-contact upload session — paperwork before name/email."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.config import DATA, PROJECTS
from services.memory.timeline import load_timeline
from services.memory.entity_graph import find_entity_id
from services.security import make_session_token

UI = Path(__file__).resolve().parents[1] / "ui"


@pytest.fixture
def pub():
    return TestClient(app)


@pytest.fixture
def mem_telemetry(monkeypatch, tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    projects = tmp_path / "projects"
    projects.mkdir(parents=True)
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.memory.entity_graph.MEMORY_DIR", mem)
    monkeypatch.setattr("services.customer_session.SESSIONS_ROOT", sessions)
    monkeypatch.setattr("services.customer_session.PROJECTS", projects)
    monkeypatch.setattr("services.projects.PROJECTS", projects)
    return mem


def _start(pub):
    r = pub.post("/api/customer/session/start")
    assert r.status_code == 200
    j = r.json()
    assert j["session_id"].startswith("CS-")
    assert j["session_token"]
    return j


def test_session_start_without_contact(pub, mem_telemetry):
    from services.customer_session import SESSIONS_ROOT

    j = _start(pub)
    sess_path = SESSIONS_ROOT / j["session_id"] / "session.json"
    assert sess_path.is_file()
    data = json.loads(sess_path.read_text(encoding="utf-8"))
    assert data["status"] == "active"
    assert data["project_id"] is None


def test_upload_with_valid_session_token(pub, mem_telemetry):
    j = _start(pub)
    r = pub.post(
        "/api/customer/session/upload",
        data={
            "session_id": j["session_id"],
            "session_token": j["session_token"],
        },
        files={"file": ("policy.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["upload_count"] == 1


def test_invalid_session_token_rejected(pub, mem_telemetry):
    j = _start(pub)
    r = pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": "bad-token"},
        files={"file": ("a.pdf", b"x", "application/pdf")},
    )
    assert r.status_code in (401, 403)


def test_path_traversal_filename_sanitized(pub, mem_telemetry):
    from services.customer_session import SESSIONS_ROOT

    j = _start(pub)
    r = pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": j["session_token"]},
        files={"file": ("../../evil.pdf", b"x", "application/pdf")},
    )
    assert r.status_code == 200
    manifest = json.loads(
        (SESSIONS_ROOT / j["session_id"] / "pending_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["files"][0]["safe_name"] == "evil.pdf"
    assert ".." not in manifest["files"][0]["stored_name"]


def test_complete_requires_name_email(pub, mem_telemetry):
    j = _start(pub)
    pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": j["session_token"]},
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
    )
    r = pub.post(
        "/api/customer/session/complete",
        data={
            "session_id": j["session_id"],
            "session_token": j["session_token"],
            "name": "Jane",
            "email": "not-an-email",
        },
    )
    assert r.status_code == 400


def test_complete_creates_project_and_links_files(pub, mem_telemetry, tmp_path):
    j = _start(pub)
    pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": j["session_token"]},
        files={"file": ("evidence.pdf", b"%PDF-1.4", "application/pdf")},
    )
    r = pub.post(
        "/api/customer/session/complete",
        data={
            "session_id": j["session_id"],
            "session_token": j["session_token"],
            "name": "Jane Doe",
            "email": "jane@example.com",
            "note": "From pytest",
        },
    )
    assert r.status_code == 200
    body = r.json()
    pid = body["project_id"]
    assert pid.startswith("P-")
    assert body.get("continuation_url")
    assert body.get("upload_url")
    assert body.get("qr_url")
    from services.projects import PROJECTS

    evidence = PROJECTS / pid / "evidence"
    assert list(evidence.glob("*.pdf"))


def test_continuation_and_qr_urls(pub, mem_telemetry):
    j = _start(pub)
    pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": j["session_token"]},
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
    )
    r = pub.post(
        "/api/customer/session/complete",
        data={
            "session_id": j["session_id"],
            "session_token": j["session_token"],
            "name": "Bob",
            "email": "bob@test.com",
        },
    )
    body = r.json()
    assert "continue.html" in body["continuation_url"] or "token=" in body["continuation_url"]
    from urllib.parse import urlparse

    qr_path = body["qr_url"]
    if "://" in qr_path:
        parsed = urlparse(qr_path)
        qr_path = parsed.path + ("?" + parsed.query if parsed.query else "")
    qr = pub.get(qr_path)
    assert qr.status_code == 200
    assert qr.headers.get("content-type", "").startswith("image/")


def test_telemetry_emitted(pub, mem_telemetry):
    j = _start(pub)
    pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": j["session_token"]},
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
    )
    pub.post(
        "/api/customer/session/complete",
        data={
            "session_id": j["session_id"],
            "session_token": j["session_token"],
            "name": "Tel User",
            "email": "tel@test.com",
        },
    )
    tel_path = mem_telemetry / "telemetry.jsonl"
    assert tel_path.is_file()
    types = []
    for line in tel_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            types.append(json.loads(line).get("event_type"))
    assert "customer_session_started" in types
    assert "workspace_created" in types


def test_memory_timeline_after_complete(pub, mem_telemetry):
    j = _start(pub)
    pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": j["session_token"]},
        files={"file": ("a.pdf", b"%PDF", "application/pdf")},
    )
    r = pub.post(
        "/api/customer/session/complete",
        data={
            "session_id": j["session_id"],
            "session_token": j["session_token"],
            "name": "Memory Test",
            "email": "memory@test.com",
        },
    )
    pid = r.json()["project_id"]
    eid = find_entity_id(email="memory@test.com", base=mem_telemetry)
    assert eid
    events = [t["event_type"] for t in load_timeline(eid, mem_telemetry)]
    assert "paperwork_uploaded" in events
    assert "customer_min_info_completed" in events
    assert "workspace_created" in events
    assert "continuation_created" in events


def test_customer_pages_core_copy():
    for name in ["shop.html", "inquiry.html", "upload.html"]:
        lower = (UI / name).read_text(encoding="utf-8", errors="replace").lower()
        assert "give us exactly what you have" in lower


def test_no_step_123_inquiry():
    import re

    html = (UI / "inquiry.html").read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"Step\s+[123]", html, re.I)


def test_session_token_mismatch(pub, mem_telemetry):
    j = _start(pub)
    wrong = make_session_token("CS-ffffffffffff")
    r = pub.post(
        "/api/customer/session/upload",
        data={"session_id": j["session_id"], "session_token": wrong},
        files={"file": ("a.pdf", b"x", "application/pdf")},
    )
    assert r.status_code == 403

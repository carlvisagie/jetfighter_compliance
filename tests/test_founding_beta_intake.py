"""Founding Beta intake funnel — public upload + operator panel."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def test_founding_beta_page_loads(client):
    r = client.get("/ui/intake")
    assert r.status_code == 200
    assert "Free Founding Beta Compliance Paperwork Review" in r.text


def test_upload_requires_contact(fb_env, anon_client):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        data={"email": "", "phone": ""},
    )
    assert r.status_code == 400


def test_upload_success_no_orchestration_import(fb_env, anon_client):
    for name in list(sys.modules):
        if name.startswith("services.acquisition.orchestration"):
            del sys.modules[name]
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("policy.pdf", io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf"))],
        data={"email": "beta@example.com", "company": "Acme"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("intake_id", "").startswith("FB-")
    assert body.get("magic_link")
    assert body.get("qr_png_base64")
    assert "services.acquisition.orchestration" not in sys.modules
    from services.intake.storage import intake_dir as fb_intake_dir

    assert (fb_intake_dir(body["intake_id"]) / "uploads" / "policy.pdf").is_file()


def test_operator_panel_lists_intake(client, fb_env, anon_client):
    anon_client.post(
        "/api/intake/upload",
        files=[("files", ("a.txt", io.BytesIO(b"hello"), "text/plain"))],
        data={"email": "ops@example.com", "deadline": "Friday"},
    )
    r = client.get("/api/operator/intake/queue")
    assert r.status_code == 200
    body = r.json()
    dash = body.get("dashboard") or {}
    assert body.get("queue_depth", 0) >= 1 or dash.get("uploads_received", 0) >= 1
    assert body.get("queue_depth", 0) >= 1 or dash.get("pending_review_count", 0) >= 1
    assert dash.get("newest_intake_ids") or [row.get("intake_id") for row in body.get("queue") or []]


def test_cognitive_topology_includes_upload_signal(client, fb_env, anon_client):
    anon_client.post(
        "/api/intake/upload",
        files=[("files", ("b.csv", io.BytesIO(b"a,b\n1,2"), "text/csv"))],
        data={"phone": "+15551234567"},
    )
    r = client.get("/api/cognitive-topology")
    assert r.status_code == 200
    up = r.json()["subsystems"]["upload_pipeline"]
    assert "activity" in up


def test_malformed_file_does_not_crash(fb_env, anon_client):
    r = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("bad.exe", io.BytesIO(b"MZ"), "application/octet-stream")),
            ("files", ("ok.txt", io.BytesIO(b"ok"), "text/plain")),
        ],
        data={"email": "x@y.com"},
    )
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert r.json().get("file_count", 0) >= 1


def test_healthz_stable_after_upload(fb_env, anon_client, client):
    anon_client.post(
        "/api/intake/upload",
        files=[("files", ("z.txt", io.BytesIO(b"z"), "text/plain"))],
        data={"email": "z@z.com"},
    )
    for _ in range(5):
        h = client.get("/healthz")
        assert h.status_code == 200
        assert h.json().get("ok") is True

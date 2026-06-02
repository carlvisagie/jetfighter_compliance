"""Upload contract integrity — count drift, lifecycle, operator surfacing."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str) -> tuple:
    return ("files", (name, io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf"))


def test_interrupted_multipart_upload_marks_partial(fb_env, anon_client: TestClient):
    expected_names = [f"doc{i}.pdf" for i in range(10)]
    received = expected_names[:9]
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in received],
        data={
            "email": "integrity@example.com",
            "expected_file_count": "10",
            "expected_file_names": json.dumps(expected_names),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expected_file_count"] == 10
    assert body["received_file_count"] == 9
    assert body["integrity_mismatch"] is True
    assert body["customer_may_show_success"] is False
    assert body["review_status"] in ("partial_upload", "integrity_failure")
    assert body["custody_status"] == "partial_upload"
    assert body["failed_file_count"] >= 1
    assert "doc9.pdf" in body["missing_files"]

    from services.intake.retention import load_audit_receipt
    from services.intake.storage import load_intake_record

    rec = load_intake_record(body["intake_id"])
    ui = rec.get("upload_integrity") or {}
    assert ui.get("expected_file_count") == 10
    assert ui.get("received_file_count") == 9
    assert ui.get("integrity_mismatch") is True
    assert "doc9.pdf" in (ui.get("missing_files") or [])

    audit = load_audit_receipt(body["intake_id"])
    assert audit is not None
    assert audit.get("expected_file_count") == 10
    assert audit.get("missing_files")


def test_duplicate_filename_collision_tracked(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("policy.pdf"), _pdf("policy.pdf")],
        data={
            "email": "dup@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["policy.pdf", "policy.pdf"]),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["received_file_count"] == 2
    assert body["persisted_file_count"] == 2
    assert body["verified_file_count"] == 2
    assert body["customer_may_show_success"] is True

    from services.intake.storage import load_intake_record

    lifecycle = (load_intake_record(body["intake_id"]).get("upload_integrity") or {}).get(
        "file_lifecycle"
    ) or []
    reason_codes = [e.get("reason_code") for e in lifecycle]
    stored = [e.get("stored_name") for e in lifecycle]
    assert "duplicate_renamed" in reason_codes or len(set(stored)) == 2


def test_unsupported_extension_partial_upload(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[
            _pdf("good.pdf"),
            ("files", ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")),
        ],
        data={
            "email": "ext@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["good.pdf", "virus.exe"]),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expected_file_count"] == 2
    assert body["received_file_count"] == 2
    assert body["persisted_file_count"] == 1
    assert body["integrity_mismatch"] is True
    assert body["customer_may_show_success"] is False
    assert body["review_status"] in ("partial_upload", "integrity_failure")
    assert body["custody_status"] in ("partial_upload", "rejected_files")
    assert body["rejected_file_count"] >= 1
    assert any(
        rf.get("original_name") == "virus.exe"
        for rf in body.get("rejected_files") or []
    )


def test_partial_persistence_surfaces_mismatch(fb_env, anon_client: TestClient, monkeypatch):
    original = Path.write_bytes
    calls = {"n": 0}

    def flaky_write(self, data):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated disk failure")
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write)

    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("a.pdf"), _pdf("b.pdf")],
        data={
            "email": "persist@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["a.pdf", "b.pdf"]),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expected_file_count"] == 2
    assert body["persisted_file_count"] == 1
    assert body["integrity_mismatch"] is True
    assert body["customer_may_show_success"] is False


def test_operator_queue_surfaces_integrity(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("only.pdf")],
        data={
            "email": "ops@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["only.pdf", "missing.pdf"]),
        },
    )
    intake_id = r.json()["intake_id"]
    q = client.get("/api/operator/founding-beta/queue").json()
    assert q.get("integrity_mismatch_count", 0) >= 1
    row = next(x for x in q.get("queue") or [] if x.get("intake_id") == intake_id)
    ui = row.get("upload_integrity") or {}
    assert ui.get("integrity_mismatch") is True
    assert "missing.pdf" in (ui.get("missing_files") or [])
    assert ui.get("retry_recommendation")


def test_mobile_session_retry_contract(fb_env, anon_client: TestClient):
    start = anon_client.post(
        "/api/customer/session/start",
        json={"email": "mobile@example.com"},
    )
    assert start.status_code == 200, start.text
    sess = start.json()
    r = anon_client.post(
        "/api/customer/session/upload",
        data={"session_id": sess["session_id"], "session_token": sess["session_token"]},
        files=[("file", ("mobile-doc.pdf", io.BytesIO(b"%PDF mobile"), "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("expected_file_count") == 1
    assert body.get("received_file_count") == 1
    assert body.get("customer_may_show_success") is True

    retry = anon_client.post(
        "/api/customer/session/upload",
        data={"session_id": sess["session_id"], "session_token": sess["session_token"]},
        files=[("file", ("mobile-doc.pdf", io.BytesIO(b"%PDF mobile retry"), "application/pdf"))],
    )
    assert retry.status_code == 200, retry.text
    retry_body = retry.json()
    assert retry_body.get("intake_id") == body.get("intake_id")
    assert retry_body.get("file_count", 0) >= 1


def test_cote_upload_pressure_on_integrity_mismatch(fb_env, anon_client: TestClient, client: TestClient):
    anon_client.post(
        "/api/intake/upload",
        files=[_pdf("x.pdf")],
        data={
            "email": "cote@example.com",
            "expected_file_count": "3",
            "expected_file_names": json.dumps(["x.pdf", "y.pdf", "z.pdf"]),
        },
    )
    topo = client.get("/api/cognitive-topology").json()
    up = topo["subsystems"]["upload_pipeline"]
    assert (
        up.get("integrity_mismatch_count", 0) >= 1
        or up.get("upload_node_severity") in ("amber", "red")
        or up.get("anomaly") is True
    )
    assert up.get("pressure", 0) >= 0.42

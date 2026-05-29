"""Mandatory file chain-of-custody — customer, operator, COTE, audit."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str, content: bytes = b"%PDF-1.4 minimal") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _manifest(**kwargs) -> str:
    base = {
        "client_selected_count": kwargs.pop("client_selected_count", 1),
        "filenames": kwargs.pop("filenames", ["doc.pdf"]),
        "sizes": kwargs.pop("sizes", [128]),
        "lastModified": kwargs.pop("lastModified", [1]),
        "client_user_agent": kwargs.pop("client_user_agent", "pytest"),
        "upload_session_id": kwargs.pop("upload_session_id", "pytest-session"),
        "route": kwargs.pop("route", "/ui/founding-beta"),
    }
    base.update(kwargs)
    return json.dumps(base)


def test_ten_selected_ten_verified(fb_env, anon_client: TestClient):
    names = [f"doc{i}.pdf" for i in range(10)]
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf(n) for n in names],
        data={
            "email": "ten@example.com",
            "expected_file_count": "10",
            "expected_file_names": json.dumps(names),
            "upload_manifest": _manifest(
                client_selected_count=10,
                filenames=names,
                sizes=[100] * 10,
            ),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expected_file_count"] == 10
    assert body["received_file_count"] == 10
    assert body["verified_file_count"] == 10
    assert body["failed_file_count"] == 0
    assert body["customer_may_show_success"] is True
    assert body["custody_status"] == "verified_complete"
    assert body["durable_receipt_created"] is True


def test_audit_endpoint_exposes_lifecycle(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("audit.pdf")],
        data={"email": "audit@example.com", "expected_file_count": "1"},
    )
    iid = r.json()["intake_id"]
    audit = client.get(f"/api/operator/founding-beta/intake/{iid}/audit").json()
    assert audit.get("file_lifecycle_table")
    row = audit["file_lifecycle_table"][0]
    assert row.get("original_filename") == "audit.pdf"
    assert row.get("lifecycle_state") in ("verified", "persisted", "duplicate")


def test_retention_check_compares_counts(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("a.pdf"), _pdf("b.pdf")],
        data={
            "email": "ret@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["a.pdf", "b.pdf"]),
        },
    )
    iid = r.json()["intake_id"]
    chk = client.get(f"/api/operator/founding-beta/retention-check/{iid}").json()
    bd = chk["count_breakdown"]
    assert bd["expected_file_count"] == 2
    assert bd["verified_file_count"] == 2
    assert chk["counts_match"] is True


def test_oversized_file_rejected_visible(fb_env, anon_client: TestClient, monkeypatch):
    from services.intake import intake as intake_mod

    monkeypatch.setattr(intake_mod, "MAX_FILE_BYTES", 64)
    big = b"x" * 128
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("small.pdf"), _pdf("big.pdf", big)],
        data={
            "email": "big@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["small.pdf", "big.pdf"]),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rejected_file_count"] >= 1
    assert body["custody_status"] in ("partial_upload", "rejected_files")
    assert body["customer_may_show_success"] is False


def test_magic_link_manifest_metadata(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("link.pdf")],
        data={
            "email": "magic@example.com",
            "expected_file_count": "1",
            "upload_manifest": _manifest(
                route="/ui/founding-beta?intake_id=FB-x&token=abc",
                resume_token_used=False,
            ),
        },
        headers={"User-Agent": "Mozilla/5.0", "X-Forwarded-For": "203.0.113.10"},
    )
    body = r.json()
    custody = body.get("upload_custody") or {}
    assert custody.get("submission_method") in ("magic-link", "desktop")
    assert custody.get("source_ip") == "203.0.113.10"


def test_qr_route_submission_method(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("qr.pdf")],
        data={
            "email": "qr@example.com",
            "upload_manifest": _manifest(route="/ui/founding-beta?qr=1"),
        },
    )
    assert r.status_code == 200
    assert (r.json().get("upload_custody") or {}).get("submission_method") == "qr"


def test_cockpit_html_has_custody_markers():
    text = Path("ui/control.html").read_text(encoding="utf-8")
    assert "fb-queue-custody" in text
    assert "file_lifecycle_table" in text


def test_founding_beta_html_custody_summary():
    text = Path("ui/founding-beta.html").read_text(encoding="utf-8")
    assert "fbCustodySummary" in text


def test_cote_upload_severity_on_mismatch(fb_env, anon_client: TestClient, client: TestClient):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("only.pdf")],
        data={"email": "sev@example.com", "expected_file_count": "2"},
    )
    topo = client.get("/api/cognitive-topology").json()
    up = topo["subsystems"]["upload_pipeline"]
    assert up.get("upload_node_severity") in ("amber", "red")
    assert up.get("latest_custody_status") in ("partial_upload", "rejected_files", "integrity_failure", "")

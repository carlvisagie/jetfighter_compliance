"""Automated tests — all inventory sources must agree."""
from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str) -> tuple:
    return ("files", (name, io.BytesIO(b"%PDF-1.4 inventory"), "application/pdf"))


def test_inventory_agreement_after_single_upload(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("inv-one.pdf")],
        data={"email": "inv@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proof_gate_passed"] is True

    diag = client.get("/api/operator/intake/diagnostics").json()
    assert diag["live_scan_status"] == "healthy"
    assert diag["inventory_agreement"]["ok"] is True

    d = diag["diagnostics"]
    rs = d["retention_scan"]
    inv = d["inventory"]
    assert rs["intake_directories"] == inv["intake_directories"]
    assert rs["upload_files"] == inv["upload_files"]
    assert d["intake_directories_found"] == inv["intake_directories"]
    assert d["upload_files_on_disk"] == inv["upload_files"]
    assert diag["queue_depth"] == inv["pending_review_count"]

    scan = client.get("/api/operator/intake/raw-disk-scan").json()
    assert scan["intake_directories"] == inv["intake_directories"]
    assert scan["upload_files"] == inv["upload_files"]

    live = client.get("/api/ops/boot-status/live").json()
    assert live["live_scan_status"] == "healthy"
    assert live["intake_directories"] == inv["intake_directories"]
    assert live["upload_files"] == inv["upload_files"]
    assert live["queue_depth"] == diag["queue_depth"]


def test_inventory_agreement_thirteen_files(fb_env, anon_client: TestClient, client: TestClient):
    names = [f"inv{i:02d}.pdf" for i in range(13)]
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf(n) for n in names],
        data={
            "email": "inv13@example.com",
            "expected_file_count": "13",
            "expected_file_names": json.dumps(names),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["proof_gate_passed"] is True
    assert r.json()["verified_file_count"] == 13

    diag = client.get("/api/operator/intake/diagnostics").json()
    assert diag["live_scan_status"] == "healthy"
    inv = diag["diagnostics"]["inventory"]
    assert inv["upload_files"] >= 13
    assert diag["queue_depth"] == inv["pending_review_count"]


def test_retention_scan_not_stale_startup_snapshot(fb_env, anon_client: TestClient, client: TestClient):
    """retention_scan must reflect live disk, not cached boot dirs=0."""
    anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("live-scan.pdf")],
        data={"email": "live@example.com", "expected_file_count": "1"},
    )
    diag = client.get("/api/operator/intake/diagnostics").json()
    rs = diag["diagnostics"]["retention_scan"]
    assert rs.get("scan_type") == "live"
    assert int(rs.get("intake_directories") or 0) >= 1
    assert int(rs.get("upload_files") or 0) >= 1
    startup = diag["diagnostics"].get("startup_retention_snapshot")
    if startup and int(startup.get("intake_directories") or 0) == 0:
        assert rs["intake_directories"] != startup["intake_directories"] or rs["upload_files"] > 0


def test_no_degraded_when_proof_gate_passed(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("nogate.pdf")],
        data={"email": "nogate@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200
    assert r.json()["proof_gate_passed"] is True

    live = client.get("/api/ops/boot-status/live").json()
    assert live["live_scan_status"] == "healthy"
    assert live["status"] == "healthy"


def test_queue_depth_equals_pending_review(fb_env, anon_client: TestClient, client: TestClient):
    for i in range(2):
        anon_client.post(
            "/api/founding-beta/upload",
            files=[_pdf(f"q{i}.pdf")],
            data={"email": f"q{i}@example.com", "expected_file_count": "1"},
        )
    diag = client.get("/api/operator/intake/diagnostics").json()
    inv = diag["diagnostics"]["inventory"]
    assert diag["queue_depth"] == inv["pending_review_count"]
    assert diag["queue_depth"] >= 2

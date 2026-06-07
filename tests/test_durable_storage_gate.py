"""Production durable storage gate for founding pilot client paperwork."""
from __future__ import annotations

import io

import pytest

from services.durable_storage import (
    founding_pilot_upload_allowed,
    get_storage_status,
    intake_upload_allowed,
    is_durable_storage_configured,
    require_intake_upload_allowed,
)
from services.intake.storage import intakes_root


def test_production_rejects_upload_without_kyc_data(prod_env, anon_client, monkeypatch, tmp_path):
    monkeypatch.delenv("KYC_DATA", raising=False)
    monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
    assert founding_pilot_upload_allowed() is False
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("policy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        data={"email": "client@example.com"},
    )
    assert r.status_code == 503
    assert "not available" in (r.json().get("detail") or "").lower()
    assert not list(intakes_root().glob("FB-*"))


def test_production_accepts_upload_with_kyc_data(prod_env, anon_client, monkeypatch, tmp_path):
    monkeypatch.setenv("KYC_DATA", str(tmp_path))
    monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
    assert is_durable_storage_configured() is True
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("doc.txt", io.BytesIO(b"questionnaire"), "text/plain"))],
        data={"email": "live@client.com"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    assert (intakes_root() / iid / "intake.json").is_file()


def test_queue_reads_from_durable_kyc_data(prod_env, anon_client, client, monkeypatch, tmp_path):
    monkeypatch.setenv("KYC_DATA", str(tmp_path))
    monkeypatch.setenv("OPS_API_KEY", "gate-test-key")
    monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
    anon_client.post(
        "/api/intake/upload",
        files=[("files", ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
        data={"phone": "+15551234567"},
    )
    ops_headers = {"X-Ops-Key": "gate-test-key"}
    q = client.get("/api/operator/intake/queue", headers=ops_headers).json()
    assert q["queue_depth"] >= 1
    st = client.get("/api/operator/storage-status", headers=ops_headers).json()
    assert st["durable_storage_configured"] is True
    assert st["kyc_data_path"] == str(tmp_path.resolve())
    assert st["durable_storage_configured"] is True


def test_storage_status_endpoint(client, monkeypatch, tmp_path):
    monkeypatch.setenv("KYC_DATA", str(tmp_path))
    monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
    r = client.get("/api/operator/storage-status")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "data_root" in body
    assert body["founding_pilot_intake_enabled"] is True


def test_production_rejects_demo_kickoff(prod_env, client, monkeypatch):
    monkeypatch.setenv("OPS_API_KEY", "gate-test-key")
    r = client.post(
        "/api/test-webhook",
        json={
            "order_id": "CP-DEMO-123",
            "email": "demo@example.com",
            "name": "Demo",
            "skus": ["CMMC-L1"],
        },
        headers={"X-Ops-Key": "gate-test-key"},
    )
    assert r.status_code == 403


def test_no_ephemeral_fallback_writes_in_production(prod_env, anon_client, monkeypatch, tmp_path):
    """Upload attempt must not create intake dirs when KYC_DATA is unset."""
    monkeypatch.delenv("KYC_DATA", raising=False)
    monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
    status = get_storage_status()
    assert status["data_root_ephemeral_in_production"] is True
    assert status["founding_pilot_uploads_enabled"] is False
    anon_client.post(
        "/api/intake/upload",
        files=[("files", ("x.txt", io.BytesIO(b"x"), "text/plain"))],
        data={"email": "x@y.com"},
    )
    intakes = tmp_path / "intakes"
    if intakes.is_dir():
        assert list(intakes.iterdir()) == []


def test_require_intake_upload_allowed_exported():
    """Regression: intake.py imports this at module load; startup recovery must not ImportError."""
    assert callable(require_intake_upload_allowed)
    assert intake_upload_allowed() is False or intake_upload_allowed() is True


def test_startup_recovery_completes_without_import_error(fb_env, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="services.intake.retention")
    from services.intake.retention import scan_retention_at_startup

    report = scan_retention_at_startup(force=True)
    recovery = report.get("startup_recovery") or {}
    assert "error" not in recovery, recovery.get("error")
    assert recovery.get("ok") is True
    assert any(
        "[retention] startup recovery completed" in rec.message for rec in caplog.records
    )

"""SEV-1 upload durability regression — fsync path and vacuous-green elimination."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.intake.file_durability import durable_write_upload_payload, write_upload_with_durability_markers
from services.intake.forensic_reconcile import build_integrity_proof
from services.intake.inventory import verify_inventory_agreement
from services.intake.retention import audit_hashes_match, audit_receipt_path, hash_uploads_on_disk, retention_check
from services.intake.storage import intake_dir, intake_json_path


def _pdf(name: str, content: bytes = b"%PDF-1.4 sev1-durability") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def test_upload_success_requires_fsync_path(fb_env, anon_client: TestClient, monkeypatch):
    fsync_calls: list[str] = []

    import os

    real_fsync = os.fsync

    def track_fsync(fd):
        fsync_calls.append("fsync")
        return real_fsync(fd)

    monkeypatch.setattr("os.fsync", track_fsync)
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("fsync-required.pdf")],
        data={"email": "fsync@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proof_gate_passed"] is True
    assert len(fsync_calls) >= 2, "upload must fsync temp and final payload before success"


def test_durable_write_upload_payload_reopens_and_rehashes(fb_env):
    dest = intake_dir("FB-testdurability001") / "uploads" / "payload.pdf"
    data = b"%PDF-1.4 durable reopen test"
    result = durable_write_upload_payload(dest, data)
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert dest.is_file()
    assert dest.read_bytes() == data


def test_empty_uploads_with_expected_files_fails_retention(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("expected-missing.pdf")],
        data={"email": "expected@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    iid = r.json()["intake_id"]
    (intake_dir(iid) / "uploads" / "expected-missing.pdf").unlink(missing_ok=True)

    retention = retention_check(iid)
    assert retention["upload_file_count"] == 0
    assert retention["ok"] is False
    assert retention["file_hashes_match"] is False
    assert retention["ghost_intake"] is True


def test_metadata_shell_without_payload_fails_inventory(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("shell-fail.pdf")],
        data={"email": "shell@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    (intake_dir(iid) / "uploads" / "shell-fail.pdf").unlink(missing_ok=True)
    audit_receipt_path(iid).unlink(missing_ok=True)
    intake_json_path(iid).write_text(
        json.dumps(
            {
                "intake_id": iid,
                "review_status": "pending_review",
                "file_count": 1,
                "files": [{"name": "shell-fail.pdf", "size": 24}],
                "upload_integrity": {"verified_file_count": 1, "persisted_file_count": 1},
            }
        ),
        encoding="utf-8",
    )

    agreement = verify_inventory_agreement()
    assert agreement["ok"] is False
    assert agreement["live_scan_status"] == "critical"
    assert agreement["ghost_intake_count"] >= 1


def test_file_hashes_match_false_when_expected_files_absent(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("hash-fail.pdf")],
        data={"email": "hash@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    (intake_dir(iid) / "uploads" / "hash-fail.pdf").unlink(missing_ok=True)

    on_disk = hash_uploads_on_disk(iid)
    assert on_disk == {}
    assert audit_hashes_match(iid, on_disk=on_disk) is False


def test_forensic_proof_false_when_total_files_zero_expected_positive(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("proof-fail.pdf")],
        data={"email": "proof@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    (intake_dir(iid) / "uploads" / "proof-fail.pdf").unlink(missing_ok=True)

    proof = build_integrity_proof(limit=50, use_cache=False)
    assert proof.get("expected_files_fleet", 0) >= 1
    assert proof.get("ok") is False
    assert proof.get("ghost_intake_count", 0) >= 1


def test_restart_simulation_same_sha256_after_recovery(fb_env, anon_client: TestClient, client: TestClient):
    content = b"%PDF-1.4 restart sha256 proof"
    expected_sha = hashlib.sha256(content).hexdigest()
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("restart-sha.pdf", io.BytesIO(content), "application/pdf"))],
        data={"email": "restartsha@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    iid = r.json()["intake_id"]

    from services.intake.retention import scan_retention_at_startup

    scan_retention_at_startup(force=True)

    dl = client.get(f"/api/operator/intake/{iid}/files/restart-sha.pdf/download")
    assert dl.status_code == 200
    assert hashlib.sha256(dl.content).hexdigest() == expected_sha

    view = client.get(f"/api/operator/intake/{iid}/files/restart-sha.pdf/view")
    assert view.status_code == 200
    assert hashlib.sha256(view.content).hexdigest() == expected_sha

    retention = retention_check(iid)
    assert retention["ok"] is True
    assert retention["file_hashes_match"] is True

"""Ghost intake and durability gate tests — SEV-1 upload persistence."""
from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from services.intake.forensic_reconcile import build_integrity_proof
from services.intake.inventory import detect_ghost_intakes, verify_inventory_agreement
from services.intake.retention import audit_receipt_path, retention_check
from services.intake.storage import intake_dir, intake_json_path


def _pdf(name: str) -> tuple:
    return ("files", (name, io.BytesIO(b"%PDF-1.4 ghost-test"), "application/pdf"))


def test_ghost_intake_detected_when_metadata_without_files(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("ghost-detect.pdf")],
        data={"email": "ghost@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    iid = r.json()["intake_id"]
    (intake_dir(iid) / "uploads" / "ghost-detect.pdf").unlink(missing_ok=True)
    audit_receipt_path(iid).unlink(missing_ok=True)

    ghosts = detect_ghost_intakes()
    assert any(g["intake_id"] == iid for g in ghosts)

    retention = retention_check(iid)
    assert retention["ghost_intake"] is True
    assert retention["ok"] is False
    assert retention["file_hashes_match"] is False

    agreement = verify_inventory_agreement()
    assert agreement["ghost_intake_count"] >= 1
    assert agreement["ok"] is False
    assert agreement["live_scan_status"] == "critical"

    proof = build_integrity_proof(limit=50, use_cache=False)
    assert proof.get("ok") is False
    assert proof.get("ghost_intake_count", 0) >= 1


def test_retention_no_false_positive_without_receipt(fb_env):
    from services.intake.retention import audit_hashes_match, hash_uploads_on_disk

    iid = "FB-000000000001"
    d = intake_dir(iid)
    d.mkdir(parents=True, exist_ok=True)
    intake_json_path(iid).write_text(
        json.dumps({"intake_id": iid, "review_status": "pending_review", "files": [], "file_count": 0}),
        encoding="utf-8",
    )
    assert audit_hashes_match(iid, on_disk=hash_uploads_on_disk(iid)) is True


def test_ghost_detected_via_hash_ledger_when_metadata_stripped(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("ledger-ghost.pdf")],
        data={"email": "ledger@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    iid = r.json()["intake_id"]
    uploads = intake_dir(iid) / "uploads"
    (uploads / "ledger-ghost.pdf").unlink(missing_ok=True)
    audit_receipt_path(iid).unlink(missing_ok=True)
    intake_json_path(iid).write_text(
        json.dumps(
            {
                "intake_id": iid,
                "review_status": "pending_review",
                "files": [],
                "file_count": 0,
            }
        ),
        encoding="utf-8",
    )

    ghosts = detect_ghost_intakes()
    assert any(g["intake_id"] == iid for g in ghosts)
    retention = retention_check(iid)
    assert retention["ghost_intake"] is True
    assert retention["ok"] is False


def test_fresh_intake_without_upload_not_ghost(fb_env):
    from services.intake.intake import create_intake

    rec = create_intake(email="fresh@example.com")
    iid = rec["intake_id"]
    ghosts = detect_ghost_intakes()
    assert all(g["intake_id"] != iid for g in ghosts)


def test_retention_fails_when_receipt_missing_files(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("receipt-miss.pdf")],
        data={"email": "receipt@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    (intake_dir(iid) / "uploads" / "receipt-miss.pdf").unlink(missing_ok=True)

    retention = retention_check(iid)
    assert retention["audit_receipt_exists"] is True
    assert retention["upload_file_count"] == 0
    assert retention["file_hashes_match"] is False
    assert retention["ok"] is False

"""Upload immutability proof gate — full destructive test matrix (SEV-1)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str, content: bytes = b"%PDF-1.4 immutability") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "immutability@example.com",
        "expected_file_count": str(len(names)),
        "expected_file_names": json.dumps(names),
        **extra,
    }
    r = client.post("/api/intake/upload", files=[_pdf(n) for n in names], data=data)
    return r


def _assert_visible_everywhere(client: TestClient, intake_id: str, names: list[str]) -> None:
    scan = client.get("/api/operator/intake/raw-disk-scan", params={"intake_id": intake_id}).json()
    row = (scan.get("intakes") or [{}])[0]
    assert int(row.get("upload_file_count") or 0) >= len(names)

    retention = client.get(f"/api/operator/intake/retention-check/{intake_id}").json()
    assert retention["upload_files_found"] is True
    assert retention["file_hashes_match"] is True
    assert int(retention["upload_file_count"]) >= len(names)

    files = client.get(f"/api/operator/intake/{intake_id}/files").json()
    assert files["file_count"] >= len(names)
    for doc in files["documents"]:
        assert doc.get("accessible") is True

    for name in names:
        dl = client.get(f"/api/operator/intake/{intake_id}/files/{name}/download")
        assert dl.status_code == 200, dl.text
        view = client.get(f"/api/operator/intake/{intake_id}/files/{name}/view")
        assert view.status_code == 200, view.text

    q = client.get("/api/operator/intake/queue").json()
    ids = {r.get("intake_id") for r in q.get("queue") or []}
    assert intake_id in ids


def test_upload_one_file_visible_everywhere(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["single.pdf"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proof_gate_passed"] is True
    assert body["live_scan_confirmed"] is True
    assert body["customer_may_show_success"] is True
    _assert_visible_everywhere(client, body["intake_id"], ["single.pdf"])


def test_upload_thirteen_files_visible_everywhere(fb_env, anon_client: TestClient, client: TestClient):
    names = [f"batch{i:02d}.pdf" for i in range(13)]
    r = _upload(anon_client, names)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proof_gate_passed"] is True
    assert body["verified_file_count"] == 13
    assert body["customer_may_show_success"] is True
    _assert_visible_everywhere(client, body["intake_id"], names)


def test_index_write_fail_no_success(fb_env, anon_client: TestClient, monkeypatch):
    create = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("setup.pdf")],
        data={"email": "idxfail@example.com", "expected_file_count": "1"},
    )
    assert create.status_code == 200, create.text
    iid = create.json()["intake_id"]
    token = create.json()["token"]

    def fail_index(*_a, **_k):
        raise OSError("simulated index write failure")

    monkeypatch.setattr("services.intake.intake.upsert_index_row", fail_index)
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("idxfail.pdf")],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["setup.pdf", "idxfail.pdf"]),
        },
    )
    assert r.status_code == 500


def test_queue_cannot_see_no_success(fb_env, anon_client: TestClient, monkeypatch):
    def empty_queue(**_kwargs):
        return {"ok": True, "queue": [], "queue_depth": 0}

    monkeypatch.setattr("services.intake.queue.get_operator_review_queue", empty_queue)
    r = _upload(anon_client, ["queuefail.pdf"])
    assert r.status_code == 500
    assert "upload_proof_gate_failed" in (r.headers.get("x-kyc-error-code") or "")


def test_retention_cannot_see_no_success(fb_env, anon_client: TestClient, monkeypatch):
    def bad_retention(_iid):
        return {
            "ok": True,
            "upload_files_found": False,
            "file_hashes_match": False,
            "upload_file_count": 0,
        }

    monkeypatch.setattr("services.intake.retention.retention_check", bad_retention)
    r = _upload(anon_client, ["retentionfail.pdf"])
    assert r.status_code == 500


def test_file_list_cannot_resolve_no_success(fb_env, anon_client: TestClient, monkeypatch):
    def bad_list(_iid):
        return {"ok": True, "file_count": 0, "documents": []}

    monkeypatch.setattr("services.intake.operator_files.list_intake_files_for_operator", bad_list)
    r = _upload(anon_client, ["listfail.pdf"])
    assert r.status_code == 500


def test_restart_after_upload_keeps_files(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["restart.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.retention import scan_retention_at_startup

    report = scan_retention_at_startup(force=True)
    assert report["upload_files"] >= 1
    _assert_visible_everywhere(client, iid, ["restart.pdf"])


def test_simulated_redeploy_keeps_files(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["redeploy_keep.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.storage import index_jsonl
    from services.intake.transactions import transaction_log_path

    tx = transaction_log_path(iid)
    if tx.is_file():
        lines = [ln for ln in tx.read_text(encoding="utf-8").splitlines() if '"index_committed"' not in ln]
        tx.write_text("\n".join(lines) + "\n", encoding="utf-8")
    idx = index_jsonl()
    if idx.is_file():
        lines = [ln for ln in idx.read_text(encoding="utf-8").splitlines() if iid not in ln]
        idx.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    from services.intake.reconcile import recover_uncommitted_intakes

    recover_uncommitted_intakes(limit=50)
    _assert_visible_everywhere(client, iid, ["redeploy_keep.pdf"])


def test_archive_keeps_files_accessible(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["archive_me.pdf"])
    iid = r.json()["intake_id"]
    arch = client.post(
        "/api/operator/intake/action",
        json={"intake_id": iid, "action": "archive", "operator_note": "test archive"},
    )
    assert arch.status_code == 200, arch.text
    scan = client.get("/api/operator/intake/raw-disk-scan", params={"intake_id": iid}).json()
    assert int((scan.get("intakes") or [{}])[0].get("upload_file_count") or 0) >= 1
    dl = client.get(f"/api/operator/intake/{iid}/files/archive_me.pdf/download")
    assert dl.status_code == 200


def test_corrupt_file_creates_incident(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["corrupt_imm.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "corrupt_imm.pdf").write_bytes(b"TAMPERED")
    client.get("/api/operator/integrity/reconcile")
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False
    from services.intake.forensic_reconcile import load_integrity_incidents

    assert any(i.get("intake_id") == iid for i in load_integrity_incidents(tail=200))


def test_delete_intake_json_reconstructs(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["reconstruct.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.storage import intake_json_path

    intake_json_path(iid).unlink(missing_ok=True)
    recover = client.post(f"/api/operator/integrity/recover/{iid}")
    assert recover.status_code == 200
    assert intake_json_path(iid).is_file()
    _assert_visible_everywhere(client, iid, ["reconstruct.pdf"])


def test_delete_index_reconstructs(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["index_recon.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.storage import index_jsonl

    idx = index_jsonl()
    if idx.is_file():
        lines = [ln for ln in idx.read_text(encoding="utf-8").splitlines() if iid not in ln]
        idx.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    recover = client.post(f"/api/operator/integrity/recover/{iid}")
    assert recover.status_code == 200
    from services.intake.storage import latest_index_row

    assert latest_index_row(iid) is not None


def test_delete_audit_receipt_creates_incident(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["no_audit_imm.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.retention import audit_receipt_path

    audit_receipt_path(iid).unlink(missing_ok=True)
    client.get("/api/operator/integrity/reconcile")
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False
    from services.intake.forensic_reconcile import load_integrity_incidents

    assert any(i.get("intake_id") == iid for i in load_integrity_incidents(tail=200))


def test_delete_uploaded_file_creates_incident(fb_env, anon_client: TestClient, client: TestClient):
    r = _upload(anon_client, ["gone_imm.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "gone_imm.pdf").unlink(missing_ok=True)
    client.get("/api/operator/integrity/reconcile")
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False


def test_wrong_kyc_data_root_fails_loudly(monkeypatch, fb_data, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    other = fb_data / "other"
    other.mkdir()
    monkeypatch.setattr("services.intake.retention.resolved_read_root", lambda: other.resolve())
    r = _upload(anon_client, ["wrongroot.pdf"])
    assert r.status_code in (500, 503)


def test_safe_mode_cannot_hide_uploads(fb_env, anon_client: TestClient, client: TestClient, monkeypatch):
    monkeypatch.setenv("KYC_SAFE_MODE", "true")
    r = _upload(anon_client, ["safemode.pdf"])
    assert r.status_code == 200, r.text
    iid = r.json()["intake_id"]
    scan = client.get("/api/operator/intake/raw-disk-scan", params={"intake_id": iid}).json()
    assert int((scan.get("intakes") or [{}])[0].get("upload_file_count") or 0) >= 1


def test_cockpit_zero_while_pending_on_disk_sev1(fb_env, anon_client: TestClient, monkeypatch):
    r = _upload(anon_client, ["cockpit.pdf"])
    assert r.status_code == 200
    from services.intake.proof_gate import detect_cockpit_zero_after_recent_success

    def empty_queue(**_kwargs):
        return {"ok": True, "queue": [], "queue_depth": 0}

    monkeypatch.setattr("services.intake.queue.get_operator_review_queue", empty_queue)
    detail = detect_cockpit_zero_after_recent_success()
    assert detail is not None
    assert detail.get("pending_on_disk", 0) >= 1


def test_live_boot_scan_reflects_post_boot_uploads(fb_env, anon_client: TestClient, client: TestClient):
    before = client.get("/api/ops/boot-status/live").json()
    before_files = int(before.get("upload_files") or 0)
    r = _upload(anon_client, ["postboot.pdf"])
    assert r.status_code == 200
    after = client.get("/api/ops/boot-status/live").json()
    assert int(after.get("upload_files") or 0) >= before_files + 1
    assert after.get("scan_type") == "live"


def test_unreviewed_upload_delete_forbidden(fb_env, anon_client: TestClient):
    r = _upload(anon_client, ["nodelete.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.delete_protection import UploadDeleteForbidden, assert_upload_file_delete_allowed

    with pytest.raises(UploadDeleteForbidden):
        assert_upload_file_delete_allowed(
            iid,
            "nodelete.pdf",
            operator_authorized=True,
            retention_policy="operator_approved_retention_expired",
            audit_event_written=True,
        )


def test_quarantine_mirror_created(fb_env, anon_client: TestClient):
    r = _upload(anon_client, ["quarantine.pdf"])
    iid = r.json()["intake_id"]
    from services.intake.quarantine import load_quarantine_manifest

    manifest = load_quarantine_manifest(iid)
    assert manifest is not None
    assert int(manifest.get("file_count") or 0) >= 1


def test_proof_gate_fields_in_success_response(fb_env, anon_client: TestClient):
    r = _upload(anon_client, ["fields.pdf"])
    body = r.json()
    for key in (
        "proof_gate_passed",
        "data_root",
        "write_path",
        "live_scan_confirmed",
        "queue_or_archive_visible",
        "retention_visible",
        "file_access_verified",
        "verified_file_count",
    ):
        assert key in body, f"missing {key}"
    assert body["proof_gate_passed"] is True

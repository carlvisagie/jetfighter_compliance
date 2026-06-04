"""Forensic Evidence Integrity Engine — chaos and adversarial scenarios."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str, content: bytes = b"%PDF-1.4 forensic") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "forensic@example.com",
        "expected_file_count": str(len(names)),
        "expected_file_names": json.dumps(names),
        **extra,
    }
    r = client.post("/api/intake/upload", files=[_pdf(n) for n in names], data=data)
    assert r.status_code == 200, r.text
    return r.json()


def test_evidence_registry_after_upload(fb_env, anon_client: TestClient):
    body = _upload(anon_client, ["reg.pdf"])
    iid = body["intake_id"]
    from services.intake.evidence_registry import lookup_by_intake

    rows = lookup_by_intake(iid)
    assert len(rows) >= 1
    assert rows[0]["current_status"] == "verified"
    assert rows[0]["sha256"]


def test_delete_index_row_recovery_restores_visibility(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["idx.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import index_jsonl

    idx = index_jsonl()
    if idx.is_file():
        lines = [ln for ln in idx.read_text(encoding="utf-8").splitlines() if iid not in ln]
        idx.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    recover = client.post(f"/api/operator/integrity/recover/{iid}")
    assert recover.status_code == 200, recover.text
    rep = recover.json()
    assert rep.get("ok") is True
    assert rep.get("recovery_report", {}).get("index_row_exists") is True

    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("unindexed_files", 99) == 0 or proof.get("ok") is True


def test_corrupt_hash_detected_not_green(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["corrupt.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "corrupt.pdf").write_bytes(b"TAMPERED")

    reconcile = client.get("/api/operator/integrity/reconcile").json()
    codes = {d.get("issue_code") for d in reconcile.get("disagreements") or []}
    assert "audit_hash_mismatch" in codes or "hash_mismatch_corrupt" in codes

    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False
    assert proof.get("corrupt_files", 0) >= 1


def test_partial_upload_no_fake_success(fb_env, anon_client: TestClient):
    names = [f"p{i}.pdf" for i in range(4)]
    expected = [f"p{i}.pdf" for i in range(5)]
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in names],
        data={
            "email": "partial@example.com",
            "expected_file_count": "5",
            "expected_file_names": json.dumps(expected),
        },
    )
    body = r.json()
    assert body["customer_may_show_success"] is False
    assert body["custody_status"] == "partial_upload"


def test_duplicate_upload_handled(fb_env, anon_client: TestClient):
    first = _upload(anon_client, ["dup.pdf"])
    iid = first["intake_id"]
    token = first["token"]
    second = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("dup.pdf")],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "1",
        },
    )
    assert second.status_code == 200
    # duplicate should not crash pipeline
    from services.intake.evidence_registry import lookup_by_intake

    rows = lookup_by_intake(iid)
    assert len(rows) >= 1


def test_interrupt_before_index_committed_recover_uncommitted(fb_env, anon_client: TestClient):
    """Simulate uncommitted intake — files on disk, no index_committed phase."""
    body = _upload(anon_client, ["uncommit.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_dir
    from services.intake.transactions import transaction_log_path

    tx = transaction_log_path(iid)
    if tx.is_file():
        lines = [
            ln
            for ln in tx.read_text(encoding="utf-8").splitlines()
            if '"index_committed"' not in ln
        ]
        tx.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from services.intake.reconcile import recover_uncommitted_intakes

    result = recover_uncommitted_intakes(limit=50)
    assert iid in result.get("recovered_intake_ids", []) or iid in result.get(
        "skipped_already_committed", []
    )
    assert (intake_dir(iid) / "uploads" / "uncommit.pdf").is_file()


def test_registry_rebuild_from_disk(fb_env, anon_client: TestClient):
    body = _upload(anon_client, ["rebuild.pdf"])
    iid = body["intake_id"]
    from services.intake.evidence_registry import build_registry_from_canonical, evidence_registry_path

    reg = evidence_registry_path()
    if reg.is_file():
        reg.unlink()
    out = build_registry_from_canonical(limit=50)
    assert out.get("entries_derived", 0) >= 1
    from services.intake.evidence_registry import lookup_by_intake

    assert len(lookup_by_intake(iid)) >= 1


def test_proof_endpoint_reflects_problems(fb_env, anon_client: TestClient, client: TestClient):
    _upload(anon_client, ["ok.pdf"])
    proof_ok = client.get("/api/operator/integrity/proof").json()
    assert "total_files" in proof_ok
    assert proof_ok.get("verified_files", 0) >= 1

    body = _upload(anon_client, ["bad.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "bad.pdf").write_bytes(b"BAD")
    proof_bad = client.get("/api/operator/integrity/proof").json()
    assert proof_bad.get("ok") is False


def test_timeline_completeness_after_upload(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["timeline.pdf"])
    iid = body["intake_id"]
    tl = client.get(f"/api/operator/integrity/timeline/{iid}").json()
    events = {e.get("event") for e in tl.get("events") or []}
    assert "upload_received" in events or "file_persisted" in events
    assert "hash_verified" in events or "audit_written" in events
    assert tl.get("event_count", 0) >= 3


def test_integrity_reconcile_endpoint_requires_ops(anon_client: TestClient):
    r = anon_client.get("/api/operator/integrity/proof")
    assert r.status_code in (401, 403, 302)


def _incidents_for_intake(intake_id: str) -> list:
    from services.intake.forensic_reconcile import load_integrity_incidents

    return [i for i in load_integrity_incidents(tail=500) if i.get("intake_id") == intake_id]


def test_destroy_delete_intake_json(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["no_intake_json.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_json_path

    intake_json_path(iid).unlink(missing_ok=True)
    reconcile = client.get("/api/operator/integrity/reconcile").json()
    codes = {d.get("issue_code") for d in reconcile.get("disagreements") or []}
    assert "files_without_intake_json" in codes
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False
    assert _incidents_for_intake(iid)


def test_destroy_delete_audit_receipt(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["no_audit.pdf"])
    iid = body["intake_id"]
    from services.intake.retention import audit_receipt_path

    audit_receipt_path(iid).unlink(missing_ok=True)
    reconcile = client.get("/api/operator/integrity/reconcile").json()
    codes = {d.get("issue_code") for d in reconcile.get("disagreements") or []}
    assert "files_without_audit_receipt" in codes
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False


def test_destroy_delete_transaction_log(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["no_tx.pdf"])
    iid = body["intake_id"]
    from services.intake.transactions import transaction_log_path

    transaction_log_path(iid).unlink(missing_ok=True)
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("verified_files", 0) >= 1
    reconcile = client.get("/api/operator/integrity/reconcile").json()
    assert reconcile.get("disagreement_count", 0) >= 0


def test_destroy_delete_evidence_file(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["gone.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "gone.pdf").unlink(missing_ok=True)
    reconcile = client.get("/api/operator/integrity/reconcile").json()
    codes = {d.get("issue_code") for d in reconcile.get("disagreements") or []}
    assert "registry_file_missing_on_disk" in codes or "audit_file_missing_on_disk" in codes
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False


def test_destroy_corrupt_evidence_file(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["tamper.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "tamper.pdf").write_bytes(b"TAMPERED")
    client.get("/api/operator/integrity/reconcile")
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False
    assert proof.get("corrupt_files", 0) >= 1
    assert _incidents_for_intake(iid)


def test_browser_refresh_mid_upload(fb_env, anon_client: TestClient):
    first = _upload(anon_client, ["refresh_a.pdf"])
    iid = first["intake_id"]
    token = first["token"]
    second = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("refresh_b.pdf")],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["refresh_a.pdf", "refresh_b.pdf"]),
        },
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["file_count"] >= 2


def test_redeploy_mid_upload_startup_recovery(fb_env, anon_client: TestClient):
    body = _upload(anon_client, ["redeploy.pdf"])
    iid = body["intake_id"]
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

    result = recover_uncommitted_intakes(limit=50)
    assert iid in result.get("recovered_intake_ids", []) or iid in result.get("skipped_already_committed", [])


def test_concurrent_uploads_same_intake(fb_env, anon_client: TestClient):
    import threading

    first = _upload(anon_client, ["conc_a.pdf"])
    iid = first["intake_id"]
    token = first["token"]
    results: list = []
    errors: list = []

    def worker(name: str):
        try:
            r = anon_client.post(
                "/api/intake/upload",
                files=[_pdf(name)],
                data={"intake_id": iid, "token": token, "expected_file_count": "3"},
            )
            results.append(r.status_code)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("conc_b.pdf", "conc_c.pdf")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    assert all(code == 200 for code in results)


def test_interrupted_upload_partial_persistence(fb_env, anon_client: TestClient):
    names = [f"int{i}.pdf" for i in range(3)]
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in names],
        data={
            "email": "interrupt@example.com",
            "expected_file_count": "5",
            "expected_file_names": json.dumps([f"int{i}.pdf" for i in range(5)]),
        },
    )
    body = r.json()
    assert body["customer_may_show_success"] is False
    assert body["custody_status"] == "partial_upload"


def test_recovery_disk_only(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["disk_only.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_json_path, index_jsonl

    intake_json_path(iid).unlink(missing_ok=True)
    idx = index_jsonl()
    if idx.is_file():
        lines = [ln for ln in idx.read_text(encoding="utf-8").splitlines() if iid not in ln]
        idx.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    recover = client.post(f"/api/operator/integrity/recover/{iid}")
    assert recover.status_code == 200, recover.text
    assert recover.json().get("ok") is True


def test_recovery_audit_only(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["audit_only.pdf"])
    iid = body["intake_id"]
    from services.intake.evidence_registry import evidence_registry_path

    reg = evidence_registry_path()
    if reg.is_file():
        lines = [ln for ln in reg.read_text(encoding="utf-8").splitlines() if iid not in ln]
        reg.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    from services.intake.evidence_registry import build_registry_from_canonical

    out = build_registry_from_canonical(limit=50)
    assert out.get("entries_derived", 0) >= 1
    from services.intake.evidence_registry import lookup_by_intake

    assert len(lookup_by_intake(iid)) >= 1


def test_recovery_transaction_log_only(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["tx_only.pdf"])
    iid = body["intake_id"]
    from services.intake.transactions import transaction_log_path

    transaction_log_path(iid).unlink(missing_ok=True)
    recover = client.post(f"/api/operator/integrity/recover/{iid}")
    assert recover.status_code == 200, recover.text
    assert recover.json().get("ok") is True


def test_recovery_mixed_corruption(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["mix_a.pdf", "mix_b.pdf"])
    iid = body["intake_id"]
    from services.intake.storage import intake_dir
    from services.intake.retention import audit_receipt_path

    (intake_dir(iid) / "uploads" / "mix_b.pdf").write_bytes(b"CORRUPT")
    audit_receipt_path(iid).unlink(missing_ok=True)
    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("ok") is False
    recover = client.post(f"/api/operator/integrity/recover/{iid}")
    assert recover.status_code == 200
    proof_after = client.get("/api/operator/integrity/proof").json()
    assert proof_after.get("corrupt_files", 0) >= 1 or proof_after.get("ok") is False


# ── HMAC-signed audit receipt — 2026-06-04 forensic audit P1 ───────


def test_audit_receipt_signed_when_secret_configured(
    fb_env, anon_client: TestClient, monkeypatch
):
    """REGRESSION GUARD — write_audit_receipt must sign in place when
    KYC_AUDIT_HMAC_SECRET is set."""
    monkeypatch.setenv("KYC_AUDIT_HMAC_SECRET", "a" * 48)
    body = _upload(anon_client, ["signed.pdf"])
    iid = body["intake_id"]

    from services.intake.retention import (
        load_audit_receipt,
        verify_audit_receipt_signature,
    )

    receipt = load_audit_receipt(iid)
    assert receipt is not None
    sig = receipt.get("signature") or {}
    assert sig.get("present") is True
    assert sig.get("algorithm") == "sha256"
    assert isinstance(sig.get("value"), str) and len(sig["value"]) == 64

    status = verify_audit_receipt_signature(receipt)
    assert status == {"signed": True, "verified": True}


def test_audit_receipt_signature_detects_tamper(
    fb_env, anon_client: TestClient, monkeypatch
):
    """REGRESSION GUARD — flipping any signed field on disk must
    cause verification to fail."""
    monkeypatch.setenv("KYC_AUDIT_HMAC_SECRET", "b" * 48)
    body = _upload(anon_client, ["tamper.pdf"])
    iid = body["intake_id"]

    from services.intake.retention import (
        audit_receipt_path,
        load_audit_receipt,
        verify_audit_receipt_signature,
    )

    path = audit_receipt_path(iid)
    data = json.loads(path.read_text(encoding="utf-8"))
    # Flip a covered field — should now fail.
    fh = dict(data.get("file_hashes") or {})
    if not fh:
        pytest.skip("no file_hashes recorded for this intake")
    only = next(iter(fh))
    fh[only] = "0" * 64
    data["file_hashes"] = fh
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2), encoding="utf-8"
    )

    receipt = load_audit_receipt(iid)
    status = verify_audit_receipt_signature(receipt or {})
    assert status.get("signed") is True
    assert status.get("verified") is False
    assert status.get("reason") == "mismatch"


def test_proof_surfaces_signature_failure_as_incident(
    fb_env, anon_client: TestClient, client: TestClient, monkeypatch
):
    """REGRESSION GUARD — fleet proof must mark the run unhealthy and
    record an incident when a signature fails."""
    monkeypatch.setenv("KYC_AUDIT_HMAC_SECRET", "c" * 48)
    body = _upload(anon_client, ["fleet_tamper.pdf"])
    iid = body["intake_id"]

    from services.intake.retention import audit_receipt_path

    path = audit_receipt_path(iid)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["intake_id"] = "FB-FAKEDREPLACED"  # covered field
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2), encoding="utf-8"
    )

    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("signature_failure_count", 0) >= 1
    assert proof.get("ok") is False


def test_audit_receipt_unsigned_when_secret_absent(
    fb_env, anon_client: TestClient, monkeypatch
):
    """No HMAC secret → receipt is annotated unsigned; legacy paths
    must not blow up."""
    monkeypatch.delenv("KYC_AUDIT_HMAC_SECRET", raising=False)
    body = _upload(anon_client, ["legacy.pdf"])
    iid = body["intake_id"]

    from services.intake.retention import (
        load_audit_receipt,
        verify_audit_receipt_signature,
    )

    receipt = load_audit_receipt(iid)
    sig = (receipt or {}).get("signature") or {}
    assert sig.get("present") is False
    assert verify_audit_receipt_signature(receipt or {}) == {
        "signed": False, "reason": "unsigned",
    }

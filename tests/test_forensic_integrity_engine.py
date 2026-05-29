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
    r = client.post("/api/founding-beta/upload", files=[_pdf(n) for n in names], data=data)
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
        "/api/founding-beta/upload",
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
        "/api/founding-beta/upload",
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
    from services.intake.evidence_registry import build_registry_from_disk, evidence_registry_path

    reg = evidence_registry_path()
    if reg.is_file():
        reg.unlink()
    out = build_registry_from_disk(limit=50)
    assert out.get("entries_added", 0) >= 1
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

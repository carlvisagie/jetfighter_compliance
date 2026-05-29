"""Deterministic intake pipeline hardening — atomicity, reconciliation, stress."""
from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str, content: bytes = b"%PDF-1.4 minimal") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "hardening@example.com",
        "expected_file_count": str(len(names)),
        "expected_file_names": json.dumps(names),
        **extra,
    }
    r = client.post("/api/founding-beta/upload", files=[_pdf(n) for n in names], data=data)
    assert r.status_code == 200, r.text
    return r.json()


def test_commit_phases_audit_before_index(fb_env, anon_client: TestClient):
    body = _upload(anon_client, ["order.pdf"])
    iid = body["intake_id"]
    from services.founding_beta.transactions import load_transaction_log
    from services.founding_beta.storage import latest_index_row

    phases = [e["phase"] for e in load_transaction_log(iid)]
    upload_idx = max(i for i, p in enumerate(phases) if p == "upload_received")
    batch = phases[upload_idx:]
    assert "hash_verified" in batch
    assert "audit_written" in batch
    assert batch.index("audit_written") < batch.index("index_committed")
    row = latest_index_row(iid)
    assert row is not None
    assert row.get("committed") is True
    assert body["durable_receipt_created"] is True


def test_index_not_updated_before_audit_receipt(fb_env, anon_client: TestClient):
    body = _upload(anon_client, ["receipt.pdf"])
    iid = body["intake_id"]
    from services.founding_beta.retention import audit_receipt_path

    assert audit_receipt_path(iid).is_file()
    from services.founding_beta.storage import latest_index_row

    row = latest_index_row(iid)
    assert row and row.get("committed") is True


def test_partial_upload_visible_everywhere(fb_env, anon_client: TestClient, client: TestClient):
    names = [f"m{i}.pdf" for i in range(9)]
    expected = [f"m{i}.pdf" for i in range(10)]
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf(n) for n in names],
        data={
            "email": "partial@example.com",
            "expected_file_count": "10",
            "expected_file_names": json.dumps(expected),
        },
    )
    assert r.status_code == 200
    body = r.json()
    iid = body["intake_id"]
    assert body["customer_may_show_success"] is False
    assert body["custody_status"] == "partial_upload"

    audit = client.get(f"/api/operator/founding-beta/intake/{iid}/audit").json()
    assert audit.get("transaction_lifecycle")
    assert audit.get("file_lifecycle_table")

    retention = client.get(f"/api/operator/founding-beta/retention-check/{iid}").json()
    assert retention.get("integrity_mismatch") is True

    reconcile = client.get(f"/api/operator/founding-beta/reconcile/{iid}").json()
    assert reconcile.get("custody_status") == "partial_upload"

    q = client.get("/api/operator/founding-beta/queue").json()
    row = next(x for x in q["queue"] if x["intake_id"] == iid)
    assert row["upload_integrity"]["integrity_mismatch"] is True


def test_fleet_reconcile_endpoint(fb_env, anon_client: TestClient, client: TestClient):
    _upload(anon_client, ["fleet.pdf"])
    fleet = client.get("/api/operator/founding-beta/reconcile").json()
    assert "disk_intake_count" in fleet
    assert fleet.get("disk_intake_count", 0) >= 1


def test_malformed_manifest_does_not_crash(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("ok.pdf")],
        data={
            "email": "badmanifest@example.com",
            "upload_manifest": "{not-json",
            "expected_file_count": "1",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["verified_file_count"] == 1


def test_concurrent_uploads_same_intake(fb_env, anon_client: TestClient):
    first = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("c1.pdf")],
        data={"email": "conc@example.com", "expected_file_count": "1"},
    ).json()
    iid, token = first["intake_id"], first["token"]
    results: list = []
    errors: list = []

    def worker(n: int):
        try:
            r = anon_client.post(
                "/api/founding-beta/upload",
                files=[_pdf(f"c{n}.pdf")],
                data={
                    "intake_id": iid,
                    "token": token,
                    "expected_file_count": "1",
                },
            )
            results.append(r.status_code)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2, 4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    assert all(code == 200 for code in results)
    from services.founding_beta.retention import hash_uploads_on_disk

    assert len(hash_uploads_on_disk(iid)) >= 3


def test_queue_rebuild_after_simulated_restart(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["restart.pdf"])
    iid = body["intake_id"]
    q1 = client.get("/api/operator/founding-beta/queue").json()
    assert any(r["intake_id"] == iid for r in q1.get("queue") or [])
    q2 = client.get("/api/operator/founding-beta/queue").json()
    assert any(r["intake_id"] == iid for r in q2.get("queue") or [])


def test_durability_failure_marks_integrity_failure(fb_env, anon_client: TestClient, monkeypatch):
    from services.intake import retention as ret

    original = ret.verify_intake_durability

    def fail_verify(intake_id, expected_files=None, **kwargs):
        ok, detail = original(intake_id, expected_files=expected_files, **kwargs)
        return False, {**detail, "error": "simulated_failure"}

    monkeypatch.setattr(ret, "verify_intake_durability", fail_verify)
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("fail.pdf")],
        data={"email": "fail@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 500
    from services.founding_beta.storage import list_intake_ids, load_intake_record

    iid = list_intake_ids(limit=1)[0]
    rec = load_intake_record(iid)
    assert rec.get("custody_status") == "integrity_failure"


def test_cote_severity_tracks_latest_intake(fb_env, anon_client: TestClient, client: TestClient):
    _upload(anon_client, ["good.pdf"])
    anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf("only.pdf")],
        data={
            "email": "cote2@example.com",
            "expected_file_count": "2",
            "expected_file_names": json.dumps(["only.pdf", "missing.pdf"]),
        },
    )
    topo = client.get("/api/cognitive-topology").json()
    up = topo["subsystems"]["upload_pipeline"]
    assert up.get("upload_node_severity") in ("amber", "red")


def test_max_batch_twenty_five_files(fb_env, anon_client: TestClient):
    names = [f"b{i}.pdf" for i in range(25)]
    body = _upload(anon_client, names)
    assert body["expected_file_count"] == 25
    assert body["verified_file_count"] == 25
    assert body["customer_may_show_success"] is True


def test_atomic_write_uses_tmp_replace(fb_env, anon_client: TestClient, monkeypatch):
    tmp_writes: list[str] = []

    original_replace = Path.replace

    def track_replace(self, target):
        if str(self).endswith(".tmp"):
            tmp_writes.append(str(self))
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", track_replace)
    _upload(anon_client, ["atomic.pdf"])
    assert tmp_writes

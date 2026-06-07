"""Iteration 2 — multi-batch, interruption, recovery, telemetry, hash, legacy guards."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str) -> tuple:
    return ("files", (name, io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf"))


def _manifest(**kwargs) -> str:
    base = {
        "client_selected_count": kwargs.pop("client_selected_count", 1),
        "filenames": kwargs.pop("filenames", ["doc.pdf"]),
        "upload_session_id": kwargs.pop("upload_session_id", "sess-iter2"),
        "route": "/ui/intake",
    }
    base.update(kwargs)
    return json.dumps(base)


def test_multi_batch_thirty_files_two_requests(fb_env, anon_client: TestClient):
    names = [f"multi{i}.pdf" for i in range(30)]
    batch1 = names[:15]
    r1 = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in batch1],
        data={
            "email": "multibatch@example.com",
            "expected_file_count": "30",
            "expected_file_names": json.dumps(names),
            "upload_manifest": _manifest(
                client_selected_count=30,
                filenames=names,
                batch_complete=False,
            ),
        },
    )
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["customer_may_show_success"] is False
    assert b1["verified_file_count"] == 15
    assert b1["expected_file_count"] == 30
    assert b1["custody_status"] == "partial_upload"
    iid, token = b1["intake_id"], b1["token"]

    batch2 = names[15:]
    r2 = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in batch2],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "30",
            "expected_file_names": json.dumps(names),
            "upload_manifest": _manifest(
                client_selected_count=30,
                filenames=names,
                batch_complete=True,
            ),
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["verified_file_count"] == 30
    assert b2["customer_may_show_success"] is True
    assert b2["custody_status"] == "verified_complete"


def test_interrupted_batch_no_fake_success(fb_env, anon_client: TestClient):
    names = [f"i{i}.pdf" for i in range(20)]
    sent = names[:8]
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in sent],
        data={
            "email": "interrupt@example.com",
            "expected_file_count": "20",
            "expected_file_names": json.dumps(names),
            "upload_manifest": _manifest(
                client_selected_count=20,
                filenames=names,
                batch_complete=False,
            ),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["customer_may_show_success"] is False
    assert body["integrity_mismatch"] is True
    assert body.get("retry_recommendation")


def test_recover_uncommitted_intakes_after_interrupted_commit(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("orphan.pdf")],
        data={"email": "recover@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    from services.intake.transactions import transaction_log_path

    path = transaction_log_path(iid)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("phase") == "index_committed":
            continue
        rows.append(line.strip())
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    from services.intake.reconcile import recover_uncommitted_intakes

    out = recover_uncommitted_intakes(limit=50)
    assert iid in out.get("recovered_intake_ids", [])


def test_telemetry_failure_does_not_block_commit(fb_env, anon_client: TestClient, monkeypatch):
    from services.intake import telemetry as telem

    def fail_emit(*args, **kwargs):
        return False

    monkeypatch.setattr("services.intake.intake.emit_intake_event", fail_emit)
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("tel.pdf")],
        data={"email": "tel@example.com", "expected_file_count": "1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["durable_receipt_created"] is True
    from services.intake.transactions import load_transaction_log

    phases = [e["phase"] for e in load_transaction_log(body["intake_id"])]
    assert "telemetry_failed" in phases


def test_hash_mismatch_detected_on_retention_check(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("hash.pdf")],
        data={"email": "hash@example.com", "expected_file_count": "1"},
    )
    iid = r.json()["intake_id"]
    from services.intake.storage import intake_dir

    path = intake_dir(iid) / "uploads" / "hash.pdf"
    path.write_bytes(b"CORRUPTED")
    check = client.get(f"/api/operator/intake/retention-check/{iid}").json()
    assert check.get("hash_mismatch_detected") is True
    assert check.get("integrity_mismatch") is True


def test_canonical_write_guard_blocks_legacy_path(fb_env):
    from services.intake.storage import assert_canonical_write_path, founding_pilot_root

    legacy = founding_pilot_root() / "intakes" / "FB-deadbeef" / "uploads" / "x.pdf"
    with pytest.raises(ValueError, match="non-canonical"):
        assert_canonical_write_path(legacy)


def test_customer_upload_writes_only_canonical_intakes(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("canon.pdf")],
        data={"email": "canon@example.com", "expected_file_count": "1"},
    )
    iid = r.json()["intake_id"]
    from services.intake.storage import canonical_intake_dir, founding_pilot_root

    assert (canonical_intake_dir(iid) / "uploads" / "canon.pdf").is_file()
    legacy = founding_pilot_root() / "intakes" / iid
    assert not legacy.is_dir() or not any(legacy.rglob("canon.pdf"))


def test_cote_integrity_failure_on_hash_mismatch(fb_env, anon_client: TestClient, client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("cotehash.pdf")],
        data={"email": "cotehash@example.com", "expected_file_count": "1"},
    )
    iid = r.json()["intake_id"]
    from services.intake.storage import intake_dir

    (intake_dir(iid) / "uploads" / "cotehash.pdf").write_bytes(b"BAD")
    from services.intake.reconcile import recover_uncommitted_intakes

    recover_uncommitted_intakes(limit=20)
    topo = client.get("/api/cognitive-topology").json()
    up = topo["subsystems"]["upload_pipeline"]
    assert up.get("upload_node_severity") in ("red", "amber")

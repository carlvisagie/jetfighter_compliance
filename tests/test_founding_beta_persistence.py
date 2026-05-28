"""Founding beta intake persistence — upload path must match operator queue."""
from __future__ import annotations

import io
import json

import pytest

from services.founding_beta.queue import get_operator_review_queue
from services.founding_beta.storage import (
    all_intake_ids,
    intake_diagnostics,
    intake_json_path,
    intakes_root,
    load_intake_record,
    recover_intake_from_disk,
)


@pytest.fixture
def fb_data(monkeypatch, tmp_path):
    root = tmp_path.resolve()
    monkeypatch.setenv("KYC_DATA", str(root))
    monkeypatch.setenv("KYC_FOUNDING_BETA_MODE", "true")
    monkeypatch.setattr("services.config.DATA", root)
    return root


def test_upload_writes_intake_metadata(fb_data, anon_client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("policy.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"))],
        data={"email": "a@b.com"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    path = intake_json_path(iid)
    assert path.is_file()
    meta = json.loads(path.read_text(encoding="utf-8"))
    assert meta["review_status"] == "pending_review"
    assert meta["file_count"] >= 1
    assert (intakes_root() / iid / "uploads" / "policy.pdf").is_file()


def test_queue_reads_same_intake_metadata(fb_data, anon_client, client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("doc.txt", io.BytesIO(b"vendor questionnaire"), "text/plain"))],
        data={"email": "same@path.com"},
    )
    r = client.get("/api/operator/founding-beta/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["queue_depth"] >= 1
    assert len(body["queue"]) >= 1
    assert body["queue"][0]["review_status"] in (
        "pending_review",
        "needs_info",
        "high_value",
    )


def test_uploaded_intake_pending_review(fb_data, anon_client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("x.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
        data={"email": "pending@x.com"},
    )
    iid = r.json()["intake_id"]
    rec = load_intake_record(iid)
    assert rec["review_status"] == "pending_review"
    q = get_operator_review_queue()
    assert any(row["intake_id"] == iid for row in q["queue"])
    assert q["queue_depth"] >= 1


def test_cote_upload_pipeline_reflects_queue_depth(fb_data, anon_client, client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("a.csv", io.BytesIO(b"1,2"), "text/csv"))],
        data={"phone": "+15551234567"},
    )
    topo = client.get("/api/cognitive-topology").json()
    up = topo["subsystems"]["upload_pipeline"]
    assert up.get("pending_review", 0) >= 1 or up.get("queue_depth", 0) >= 1


def test_cockpit_queue_api_returns_pending(fb_data, anon_client, client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("b.txt", io.BytesIO(b"ssp content"), "text/plain"))],
        data={"email": "cockpit@x.com"},
    )
    iid = r.json()["intake_id"]
    q = client.get("/api/operator/founding-beta/queue").json()
    assert q["ok"] is True
    ids = [row["intake_id"] for row in q.get("queue") or []]
    assert iid in ids


def test_recover_metadata_from_files_without_intake_json(fb_data):
    iid = "FB-deadbeefcafe"
    idir = intakes_root() / iid
    (idir / "uploads").mkdir(parents=True, exist_ok=True)
    (idir / "uploads" / "recovered.pdf").write_bytes(b"%PDF")
    rec = recover_intake_from_disk(iid)
    assert rec["file_count"] == 1
    q = get_operator_review_queue()
    assert any(row["intake_id"] == iid for row in q["queue"])


def test_production_data_path_consistency(fb_data, monkeypatch):
    from services.config import _resolve_data_root

    monkeypatch.setenv("KYC_DATA", str(fb_data))
    assert _resolve_data_root() == fb_data.resolve()
    monkeypatch.setattr("services.config.DATA", fb_data.resolve())
    assert intakes_root().resolve() == (fb_data / "intakes").resolve()
    diag = intake_diagnostics()
    assert str(fb_data.resolve()) in diag["data_root"]


def test_diagnostics_endpoint(client, fb_data, anon_client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("d.txt", io.BytesIO(b"data"), "text/plain"))],
        data={"email": "d@x.com"},
    )
    r = client.get("/api/operator/founding-beta/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["diagnostics"]["intake_directories_found"] >= 1
    assert body["queue_depth"] >= 1


def test_queue_and_upload_share_data_root(fb_data, anon_client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("z.txt", io.BytesIO(b"z"), "text/plain"))],
        data={"email": "z@z.com"},
    )
    diag = intake_diagnostics()
    assert diag["intakes_root"].startswith(str(fb_data.resolve()))
    assert len(all_intake_ids()) >= 1

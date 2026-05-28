"""Founding Beta operational review pipeline — queue, classification, actions, COTE."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app
from services.founding_beta.classification import (
    DOC_SSP,
    DOC_UNKNOWN,
    classify_intake,
    classify_upload_file,
)
from services.founding_beta.queue import get_operator_review_queue
from services.founding_beta.operator_actions import apply_operator_action


@pytest.fixture
def fb_env(monkeypatch, tmp_path):
    root = tmp_path.resolve()
    (root / "intakes").mkdir(parents=True)
    mem = root / "memory"
    mem.mkdir(parents=True)
    monkeypatch.setenv("KYC_DATA", str(root))
    monkeypatch.setenv("KYC_FOUNDING_BETA_MODE", "true")
    monkeypatch.setattr("services.founding_beta.learning_hooks._LEARNING", mem / "learning_state.json")
    monkeypatch.setattr("services.config.DATA", root)
    return root


def test_classify_ssp_filename(tmp_path):
    p = tmp_path / "Acme_System_Security_Plan.pdf"
    p.write_bytes(b"%PDF-1.4")
    out = classify_upload_file(p, p.name)
    assert out["category"] == DOC_SSP
    assert out["confidence"] >= 0.55


def test_classify_unknown_exe_skipped_in_upload(fb_env, anon_client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("mystery.bin", io.BytesIO(b"data"), "application/octet-stream"))],
        data={"email": "x@y.com"},
    )
    assert r.status_code == 400


def test_queue_generation_and_sort(fb_env, anon_client, client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[
            ("files", ("company_ssp.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")),
            ("files", ("poam.xlsx", io.BytesIO(b"pk"), "application/vnd.ms-excel")),
        ],
        data={"email": "a@co.com", "company": "Alpha", "deadline": "ASAP"},
    )
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("notes.txt", io.BytesIO(b"vendor questionnaire"), "text/plain"))],
        data={"email": "b@co.com", "company": "Beta"},
    )
    r = client.get("/api/operator/founding-beta/queue")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    queue = body.get("queue") or []
    assert len(queue) >= 2
    assert queue[0].get("urgent_flag") is True
    assert "intake_id" in queue[0]
    assert "confidence_score" in queue[0]
    assert "suggested_next_action" in queue[0]
    iid = queue[0]["intake_id"]
    clf_path = fb_env / "intakes" / iid / "classification.json"
    assert clf_path.is_file()


def test_classification_persisted(fb_env, anon_client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("nist_800-171_self_assessment.csv", io.BytesIO(b"control,id\n"), "text/csv"))],
        data={"phone": "+15551234567"},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    clf = classify_intake(iid)
    assert clf.get("primary_category")
    assert (fb_env / "intakes" / iid / "classification.json").is_file()


def test_mixed_upload_malformed_and_ok(fb_env, anon_client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[
            ("files", ("bad.exe", io.BytesIO(b"MZ"), "application/octet-stream")),
            ("files", ("ok_vendor_form.txt", io.BytesIO(b"security questionnaire"), "text/plain")),
        ],
        data={"email": "mix@x.com"},
    )
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert r.json().get("file_count", 0) >= 1


def test_oversized_file_rejected(fb_env, anon_client):
    big = b"x" * (52_428_801)
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("huge.pdf", io.BytesIO(big), "application/pdf"))],
        data={"email": "big@x.com"},
    )
    assert r.status_code in (400, 200)
    if r.status_code == 200:
        assert not r.json().get("files_saved")


def test_operator_actions_and_learning(fb_env, anon_client, client):
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("ssp.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
        data={"email": "ops@co.com", "company": "OpsCo"},
    )
    iid = r.json()["intake_id"]
    ar = client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "approve_review"},
    )
    assert ar.status_code == 200
    assert ar.json().get("review_status") == "approved"
    learn_path = fb_env / "memory" / "learning_state.json"
    if learn_path.is_file():
        state = json.loads(learn_path.read_text(encoding="utf-8"))
        assert int(state.get("approvals_seen") or 0) >= 1


def test_telemetry_emitted_on_upload(monkeypatch, fb_env, anon_client):
    events = []

    monkeypatch.setattr(
        "services.organism_observability.emit.organism_emit",
        lambda sub, et, **kw: events.append((sub, et)),
    )
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("policy_handbook.txt", io.BytesIO(b"acceptable use policy"), "text/plain"))],
        data={"email": "tel@x.com"},
    )
    types = [e[1] for e in events]
    assert "intake_received" in types or "beta_upload_completed" in types


def test_cote_upload_and_learning_after_pipeline(client, fb_env, anon_client):
    for name in list(sys.modules):
        if name.startswith("services.acquisition.orchestration"):
            del sys.modules[name]
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("sprs_export.csv", io.BytesIO(b"sprs score"), "text/csv"))],
        data={"email": "cote@x.com", "company": "COTE Test"},
    )
    r = client.get("/api/cognitive-topology")
    assert r.status_code == 200
    up = r.json()["subsystems"]["upload_pipeline"]
    assert up.get("flow_active") or up.get("activity", 0) > 0
    learn = r.json()["subsystems"]["learning"]
    assert learn.get("learning_status") in ("warming_up", "healthy")
    assert "services.acquisition.orchestration" not in sys.modules


def test_mark_high_value_action(fb_env, anon_client, client):
    iid = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("asset_inventory.csv", io.BytesIO(b"asset,host"), "text/csv"))],
        data={"email": "hv@x.com"},
    ).json()["intake_id"]
    r = client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "mark_high_value"},
    )
    assert r.status_code == 200
    assert r.json()["review_status"] == "high_value"


def test_apply_operator_invalid_action(fb_env, anon_client, client):
    iid = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("a.txt", io.BytesIO(b"x"), "text/plain"))],
        data={"email": "inv@x.com"},
    ).json()["intake_id"]
    r = client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "not_a_real_action"},
    )
    assert r.status_code == 400

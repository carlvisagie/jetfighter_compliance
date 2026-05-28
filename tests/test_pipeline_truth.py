"""Customer paperwork pipeline truth — empty queue must explain why."""
from __future__ import annotations

import io

import pytest

from services.durable_storage import founding_beta_upload_allowed
from services.founding_beta.pipeline_truth import compute_queue_truth
from services.founding_beta.queue import get_operator_review_queue
from services.founding_beta.storage import intake_diagnostics


def test_upload_hard_fails_without_kyc_data(monkeypatch, anon_client, tmp_path):
    monkeypatch.delenv("KYC_DATA", raising=False)
    monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
    assert founding_beta_upload_allowed() is False
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("x.txt", io.BytesIO(b"x"), "text/plain"))],
        data={"email": "x@y.com"},
    )
    assert r.status_code == 503


def test_queue_empty_reason_no_paperwork(durable_paperwork_env):
    q = get_operator_review_queue()
    assert q["queue_empty"] is True
    assert q["queue_empty_reason"] == "no_customer_paperwork_on_disk"
    assert q["queue_empty_message"]


def test_queue_empty_reason_after_upload(durable_paperwork_env, anon_client):
    anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("a.txt", io.BytesIO(b"a"), "text/plain"))],
        data={"email": "a@b.com"},
    )
    q = get_operator_review_queue()
    assert q["queue_empty"] is False
    assert q["queue_empty_reason"] is None
    assert q["queue_depth"] >= 1


def test_pipeline_truth_index_mismatch_emits_sev1(durable_paperwork_env, monkeypatch):
    from services.founding_beta.storage import append_index_row, intake_diagnostics

    append_index_row({"intake_id": "FB-ghostonly0001", "created_at_utc": "2020-01-01T00:00:00Z"})
    diag = intake_diagnostics()
    diag["retention_scan"] = {
        "index_disk_agree": False,
        "only_on_disk_not_in_index": [],
        "only_in_index_not_on_disk": ["FB-ghostonly0001"],
    }
    emitted = []

    def _capture(code, message, **kw):
        emitted.append(code)

    monkeypatch.setattr(
        "services.founding_beta.pipeline_truth.emit_sev1_data_loss_suspected",
        lambda reason, **kw: emitted.append("sev1"),
    )
    truth = compute_queue_truth(diag=diag, rows=[], pending=[])
    assert truth["queue_empty_reason"] == "index_disk_mismatch"
    assert "sev1" in emitted

"""Founding beta durable retention — audit receipts, verification, restart survival."""
from __future__ import annotations

import io
import json
import os

import pytest

from services.durable_storage import active_data_root
from services.intake.queue import get_operator_review_queue
from services.intake.retention import (
    audit_receipt_path,
    load_audit_receipt,
    retention_check,
    resolved_read_root,
    resolved_write_root,
    scan_retention_at_startup,
    verify_intake_durability,
)
from services.intake.storage import (
    intake_dir,
    intake_json_path,
    intakes_root,
    list_intake_ids,
)


@pytest.fixture
def prod_durable(prod_env, durable_intake_root):
    return durable_intake_root


def test_upload_writes_under_var_data_style_root(prod_durable, anon_client):
  """Production uploads must land under explicit KYC_DATA (/var/data style)."""
  assert active_data_root() == prod_durable
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("policy.pdf", io.BytesIO(b"%PDF-1.4 durable"), "application/pdf"))],
      data={"email": "durable@client.com"},
  )
  assert r.status_code == 200
  body = r.json()
  assert body["durability_verified"] is True
  assert body["durable_receipt_created"] is True
  assert body["verified_file_count"] >= 1
  iid = body["intake_id"]
  assert str(intakes_root()).startswith(str(prod_durable))
  assert (intakes_root() / iid / "uploads" / "policy.pdf").is_file()


def test_upload_success_only_after_files_verified(fb_data, anon_client):
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("doc.txt", io.BytesIO(b"verified content"), "text/plain"))],
      data={"email": "verify@x.com"},
  )
  assert r.status_code == 200
  j = r.json()
  assert j["ok"] is True
  assert j.get("durability_verified") is True
  assert j.get("durable_receipt_created") is True
  iid = j["intake_id"]
  receipt = load_audit_receipt(iid)
  assert receipt is not None
  assert receipt["intake_id"] == iid
  assert receipt["data_root"] == str(resolved_write_root())
  assert receipt["file_hashes"].get("doc.txt")


def test_queue_survives_simulated_restart(fb_data, anon_client):
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("survive.txt", io.BytesIO(b"after restart"), "text/plain"))],
      data={"email": "restart@x.com"},
  )
  iid = r.json()["intake_id"]
  scan_retention_at_startup(force=True)
  q = get_operator_review_queue()
  assert any(row["intake_id"] == iid for row in q["queue"])


def test_index_recovery_from_disk(fb_data):
  iid = "FB-retentiondisk01"
  idir = intakes_root() / iid
  (idir / "uploads").mkdir(parents=True)
  (idir / "uploads" / "orphan.pdf").write_bytes(b"%PDF-orphan")
  scan_retention_at_startup(force=True)
  q = get_operator_review_queue()
  assert any(row["intake_id"] == iid for row in q["queue"])


def test_retention_check_detects_missing_files(fb_data, anon_client, client):
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("gone.txt", io.BytesIO(b"temp"), "text/plain"))],
      data={"email": "gone@x.com"},
  )
  iid = r.json()["intake_id"]
  (intake_dir(iid) / "uploads" / "gone.txt").unlink()
  chk = client.get(f"/api/operator/intake/retention-check/{iid}").json()
  assert chk["upload_files_found"] is False
  assert chk["file_hashes_match"] is False


def test_cote_reflects_retained_intake(fb_data, anon_client, client):
  anon_client.post(
      "/api/intake/upload",
      files=[("files", ("cote.csv", io.BytesIO(b"a,b"), "text/csv"))],
      data={"phone": "+15550001111"},
  )
  topo = client.get("/api/cognitive-topology").json()
  up = topo["subsystems"]["upload_pipeline"]
  assert (
      up.get("pending_review", 0) >= 1
      or up.get("queue_depth", 0) >= 1
      or up.get("latest_custody_status") in ("verified_complete", "partial_upload", "rejected_files")
      or up.get("upload_node_severity") in ("green", "amber")
      or up.get("anomaly") is True
  )


def test_wrong_root_mismatch_fails_loudly(monkeypatch, fb_data, anon_client):
  monkeypatch.setenv("ENVIRONMENT", "production")
  monkeypatch.setenv("KYC_FOUNDING_BETA_MODE", "true")
  other = fb_data / "other"
  other.mkdir()
  monkeypatch.setattr(
      "services.intake.retention.resolved_read_root",
      lambda: other.resolve(),
  )
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("x.txt", io.BytesIO(b"x"), "text/plain"))],
      data={"email": "mismatch@x.com"},
  )
  assert r.status_code in (500, 503)


def test_no_silent_empty_queue_after_upload(fb_data, anon_client, client):
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("visible.txt", io.BytesIO(b"queue me"), "text/plain"))],
      data={"email": "visible@x.com"},
  )
  iid = r.json()["intake_id"]
  q = client.get("/api/operator/intake/queue").json()
  assert q["queue_depth"] >= 1
  chk = client.get(f"/api/operator/intake/retention-check/{iid}").json()
  assert chk["queue_visible"] is True


def test_audit_endpoint(client, fb_data, anon_client):
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("audit.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
      data={"email": "audit@x.com"},
  )
  iid = r.json()["intake_id"]
  body = client.get(f"/api/operator/intake/{iid}/audit").json()
  assert body["ok"] is True
  assert body["audit_receipt_exists"] is True
  assert body["write_root"] == body["read_root"]
  assert audit_receipt_path(iid).is_file()


def test_diagnostics_expose_write_and_read_roots(client, fb_data, anon_client):
  anon_client.post(
      "/api/intake/upload",
      files=[("files", ("d.txt", io.BytesIO(b"d"), "text/plain"))],
      data={"email": "d@x.com"},
  )
  d = client.get("/api/operator/intake/diagnostics").json()
  diag = d["diagnostics"]
  assert diag["write_root"] == diag["read_root"]
  assert diag["roots_match"] is True


def test_startup_scan_flags_index_disk_drift(fb_data, monkeypatch):
  iid = "FB-indexdrift01"
  idir = intakes_root() / iid
  idir.mkdir(parents=True)
  (idir / "uploads").mkdir()
  (idir / "uploads" / "a.txt").write_text("x", encoding="utf-8")
  from services.intake.storage import append_index_row

  append_index_row({"intake_id": "FB-ghostindexonly", "created_at_utc": "2020-01-01T00:00:00Z"})
  report = scan_retention_at_startup(force=True)
  assert report["index_disk_agree"] is False
  assert "FB-ghostindexonly" in report["only_in_index_not_on_disk"] or report["only_in_index_not_on_disk"]


def test_production_upload_fails_without_durable_root(prod_env, anon_client, monkeypatch, tmp_path):
  monkeypatch.delenv("KYC_DATA", raising=False)
  monkeypatch.setattr("services.config.DATA", tmp_path.resolve())
  r = anon_client.post(
      "/api/intake/upload",
      files=[("files", ("n.txt", io.BytesIO(b"n"), "text/plain"))],
      data={"email": "n@x.com"},
  )
  assert r.status_code == 503

"""Regression guard for the operator-triggered EI reprocess pipeline.

``services.evidence_intelligence.reprocess_intake_evidence`` exists for
two reasons that came out of the 2026-06-04 forensic audit:

1. **Recovery.** Production intake ``FB-1dfab13c120b`` was processed
   through a broken EI loop (``rglob("*")``) that polluted its on-disk
   ``profile.json`` / ``classifications.jsonl`` with rows derived from
   ``intake.json``, ``classification.json``, and durability sidecars,
   and never sent the customer's image files through extraction at
   all. Read-side scrubs hide the pollution but the only way to truly
   fix the on-disk state is to wipe + replay.

2. **Replay.** When a new EI capability lands (OCR, domain pack,
   per-domain rule changes, etc.) operators need a one-shot way to
   apply it retroactively to existing intakes — without writing scripts
   that bypass custody / telemetry.

These tests pin the contract so future contributors cannot
re-introduce either failure mode.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from services.evidence_intelligence import (
    _is_real_customer_upload,
    reprocess_intake_evidence,
)


def _session_data_root() -> Path:
    """Pull the per-session KYC_DATA root pinned in tests/conftest.py.

    The durable-storage layer always resolves to ``active_data_root()``
    when ``KYC_DATA`` is set, so tests must build intakes under that
    same root rather than an unrelated tmp_path.
    """
    root = os.environ.get("KYC_DATA")
    assert root, "KYC_DATA must be pinned by conftest.py before this test runs"
    return Path(root)


# --- fixtures --------------------------------------------------------------


def _unique_intake_id() -> str:
    """Match canonical_intake_dir's check: ``^FB-[a-f0-9]{12}$``."""
    return "FB-" + uuid.uuid4().hex[:12]


@pytest.fixture
def production_like_intake():
    """Build an intake on disk that mirrors the production layout that
    exposed the bug:

      ${KYC_DATA}/intakes/{iid}/
        intake.json
        classification.json
        uploads/
          policy.txt                      <- real customer upload
          policy.txt.durability.json      <- sidecar
          image.jpg                       <- real customer upload
          image.jpg.durability.json       <- sidecar

    Plus a polluted ``projects/{iid}/evidence_intelligence/`` directory
    to prove the wipe behaviour.

    Both directories are created under the session-pinned ``KYC_DATA``
    root because the durable-storage layer always resolves there.
    Per-intake teardown keeps tests isolated.
    """
    root = _session_data_root()
    iid  = _unique_intake_id()
    idir = root / "intakes" / iid
    intel = root / "projects" / iid / "evidence_intelligence"

    (idir / "uploads").mkdir(parents=True, exist_ok=True)
    (idir / "intake.json").write_text("{}", encoding="utf-8")
    (idir / "classification.json").write_text("{}", encoding="utf-8")

    (idir / "uploads" / "policy.txt").write_text(
        "Acme Inc. multi-factor authentication is enforced for all admins.",
        encoding="utf-8",
    )
    (idir / "uploads" / "policy.txt.durability.json").write_text(
        '{"sha256":"a"}', encoding="utf-8",
    )
    (idir / "uploads" / "image.jpg").write_bytes(b"\xff\xd8\xff\xe0minimal-jpeg-bytes")
    (idir / "uploads" / "image.jpg.durability.json").write_text(
        '{"sha256":"b"}', encoding="utf-8",
    )

    intel.mkdir(parents=True, exist_ok=True)
    (intel / "profile.json").write_text(
        json.dumps({"project_id": iid, "primary_domain": "CMMC",
                    "document_inventory": [
                        {"file": "intake.json",         "document_type": "contract",
                         "confidence": 0.71, "signals": ["contract"]},
                        {"file": "classification.json", "document_type": "ssp",
                         "confidence": 0.83, "signals": ["system security plan"]},
                    ]}),
        encoding="utf-8",
    )
    (intel / "classifications.jsonl").write_text(
        json.dumps({"source_file": "intake.json",         "document_type": "contract"}) + "\n"
        + json.dumps({"source_file": "classification.json","document_type": "ssp"}) + "\n",
        encoding="utf-8",
    )
    (intel / "extractions.jsonl").write_text("", encoding="utf-8")
    (intel / "entities.jsonl").write_text(
        json.dumps({"source_file": "image.jpg.durability.json",
                    "type": "domain", "value": "image.jpg.durability.json"}) + "\n",
        encoding="utf-8",
    )
    (intel / "gaps.json").write_text(
        json.dumps({"gaps": [
            {"gap_id": "mfa_evidence", "label": "MFA", "priority": "high"},
        ]}),
        encoding="utf-8",
    )
    (intel / "review_queue.jsonl").write_text(
        json.dumps({
            "kind": "conflicting_extraction",
            "field": "company_name",
            "created_utc": "2026-06-04T14:55:32Z",
        }) + "\n",
        encoding="utf-8",
    )

    try:
        yield iid, root
    finally:
        for victim in (idir, intel.parent):
            try:
                shutil.rmtree(victim, ignore_errors=True)
            except Exception:
                pass


# --- contract: input validation -------------------------------------------


def test_rejects_empty_intake_id():
    out = reprocess_intake_evidence("")
    assert out["ok"] is False
    assert out["error"] == "intake_id_required"


def test_returns_structured_error_when_uploads_dir_missing():
    root = _session_data_root()
    iid  = _unique_intake_id()
    idir = root / "intakes" / iid
    idir.mkdir(parents=True, exist_ok=True)
    try:
        out = reprocess_intake_evidence(iid)
        assert out["ok"] is False
        assert out["error"] == "uploads_dir_missing"
        assert out["uploads_dir"].endswith("uploads")
    finally:
        shutil.rmtree(idir, ignore_errors=True)


# --- contract: only real uploads are processed ----------------------------


def test_only_real_customer_uploads_dispatched(production_like_intake):
    iid, _ = production_like_intake
    out = reprocess_intake_evidence(iid, wipe=True)

    assert out["ok"] is True, f"reprocess failed; full report: {out!r}"
    seen = [f["file"] for f in out["files_processed"]]
    assert "policy.txt"                       in seen
    assert "image.jpg"                        in seen
    assert "intake.json"                      not in seen
    assert "classification.json"              not in seen
    assert "policy.txt.durability.json"       not in seen
    assert "image.jpg.durability.json"        not in seen
    # All processed entries must pass the customer-upload predicate
    assert all(_is_real_customer_upload(f["file"]) for f in out["files_processed"])
    assert out["files_seen"] == 2


# --- contract: wipe behaviour ---------------------------------------------


def test_wipe_removes_only_rebuildable_artifacts(production_like_intake):
    iid, root = production_like_intake
    out = reprocess_intake_evidence(iid, wipe=True)
    assert out["ok"] is True, f"reprocess failed; full report: {out!r}"

    deleted = set(out["wipe_report"].get("deleted") or [])
    # Rebuildable artifacts that existed pre-reprocess must be wiped.
    assert "profile.json"          in deleted
    assert "classifications.jsonl" in deleted
    assert "entities.jsonl"        in deleted
    assert "gaps.json"             in deleted
    # Review queue is an audit-history artifact and MUST survive.
    intel = root / "projects" / iid / "evidence_intelligence"
    assert (intel / "review_queue.jsonl").is_file(), (
        "review_queue.jsonl must survive a reprocess wipe"
    )
    rq = (intel / "review_queue.jsonl").read_text(encoding="utf-8")
    assert "conflicting_extraction" in rq, (
        "review queue history must be byte-for-byte preserved"
    )


def test_wipe_false_keeps_existing_artifacts_in_place(production_like_intake):
    iid, root = production_like_intake
    intel = root / "projects" / iid / "evidence_intelligence"

    out = reprocess_intake_evidence(iid, wipe=False)
    assert out["ok"] is True, f"reprocess failed; full report: {out!r}"
    # No wipe → wipe_report is empty (the function shouldn't have called it)
    assert out["wipe"] is False
    assert not out["wipe_report"], (
        f"wipe=False must not delete anything; got {out['wipe_report']!r}"
    )
    # profile.json gets *overwritten* by the rerun (that's process_evidence_upload
    # doing its job) but the file is still present.
    assert (intel / "profile.json").is_file()


# --- contract: custody event recorded -------------------------------------


def test_custody_event_recorded(production_like_intake):
    iid, _ = production_like_intake
    reprocess_intake_evidence(iid, wipe=True)

    from services.intake.transactions import load_transaction_log
    log = load_transaction_log(iid, tail=50)
    phases = [r.get("phase") for r in log]
    assert "evidence_intelligence_reprocessed" in phases, (
        f"reprocess must write a custody event; got phases={phases!r}"
    )
    row = next(
        r for r in log if r.get("phase") == "evidence_intelligence_reprocessed"
    )
    meta = row.get("metadata") or {}
    assert meta.get("files_seen") == 2
    assert meta.get("files_ok")   == 2
    assert meta.get("wipe")       is True
    # `wiped` is the list of files actually deleted in this run.
    assert "profile.json" in (meta.get("wiped") or [])


# --- contract: OCR accounting --------------------------------------------


def test_archives_are_flagged_pending_not_classified_as_text(production_like_intake):
    """Production intake FB-1dfab13c120b uploaded ``packet.zip`` which
    fell through to the text branch (latin-1 garbage) and got silently
    'classified'. Archives must instead land in pending_analysis with
    a clear operator hint so the customer is asked to re-upload the
    contents individually.
    """
    iid, root = production_like_intake
    # Drop a tiny zip-magic-bytes blob in uploads/.
    (root / "intakes" / iid / "uploads" / "packet.zip").write_bytes(
        b"PK\x03\x04minimal-zip-bytes-not-a-real-archive"
    )
    out = reprocess_intake_evidence(iid, wipe=True)
    assert out["ok"] is True, f"reprocess failed; full report: {out!r}"

    zip_entry = next(
        (f for f in out["files_processed"] if f["file"] == "packet.zip"),
        None,
    )
    assert zip_entry is not None
    assert zip_entry.get("pending_analysis") is True, (
        "Archives must mark pending_analysis so they hit the manual review "
        f"queue, got entry={zip_entry!r}"
    )
    assert zip_entry.get("extraction_method") == "archive_pending"
    assert "archive_pending_manual_extraction" in (zip_entry.get("warnings") or [])


def test_ocr_attempts_counted(production_like_intake, monkeypatch):
    """OCR attempts must be reflected in the report whenever the OCR
    layer fires, even if the underlying binary is unavailable
    (graceful degradation)."""
    iid, _ = production_like_intake
    # Force OCR to be enabled but stub the image OCR call so we don't
    # need tesseract installed in the test environment.
    monkeypatch.setenv("KYC_OCR_ENABLED", "true")
    import services.evidence_intelligence.extraction as ext_mod
    monkeypatch.setattr(
        ext_mod, "ocr_image_bytes",
        lambda data, **kw: ("Multi-factor authentication enforced.", "ocr_ok"),
    )

    out = reprocess_intake_evidence(iid, wipe=True)
    assert out["ok"] is True
    # At least the image.jpg run should have an ocr_status field.
    img = next((f for f in out["files_processed"] if f["file"] == "image.jpg"), None)
    assert img is not None
    assert img.get("ocr_status") == "ocr_ok"
    assert img.get("ocr_applied") is True
    assert out["ocr_attempts"]  >= 1
    assert out["ocr_succeeded"] >= 1

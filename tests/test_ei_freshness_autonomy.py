"""Autonomy guardrail: the EI freshness sweep must auto-reprocess stale
intakes without operator input.

Doctrine: ``docs/KYC_ORGANISM_DOCTRINE.md`` → "Autonomy by default."

These tests pin the contract:

  · `compute_staleness_signals` fires `unindexed_upload` when a real
    customer file has no matching sha in `extractions.jsonl`.
  · It fires `ocr_now_available` when prior extractions ran without
    OCR but OCR is available now.
  · Fresh intakes return no signals.
  · `sweep_intakes_for_staleness` reprocesses stale intakes, records
    the firing signals in custody, and is bounded by ``max_reprocess``.
  · The autonomous reprocess phase has a custody-timeline mapping so
    the chain of custody renders it with a human-readable label.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from services.evidence_intelligence.freshness import (
    SIGNAL_OCR_NOW_AVAILABLE,
    SIGNAL_UNINDEXED_UPLOAD,
    compute_staleness_signals,
    sweep_intakes_for_staleness,
)


def _session_data_root() -> Path:
    root = os.environ.get("KYC_DATA")
    assert root, "KYC_DATA must be pinned by conftest.py before this test runs"
    return Path(root)


def _unique_intake_id() -> str:
    return "FB-" + uuid.uuid4().hex[:12]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def stale_intake_unindexed():
    """An intake with one upload that has no matching extraction row —
    classic 'unindexed_upload' shape."""
    root = _session_data_root()
    iid  = _unique_intake_id()
    idir = root / "intakes" / iid
    intel = root / "projects" / iid / "evidence_intelligence"

    (idir / "uploads").mkdir(parents=True, exist_ok=True)
    payload = b"acme policy: mfa is required for all admins"
    (idir / "uploads" / "policy.txt").write_bytes(payload)
    intel.mkdir(parents=True, exist_ok=True)
    # extractions.jsonl is EMPTY — there's an upload but no extraction
    # for its sha. That is the staleness signal we want fired.
    (intel / "extractions.jsonl").write_text("", encoding="utf-8")
    
    cog = root / "projects" / iid / "cognition"
    cog.mkdir(parents=True, exist_ok=True)
    (cog / "cognition_summary.json").write_text('{"status":"ok"}', encoding="utf-8")
    
    try:
        yield iid, payload
    finally:
        shutil.rmtree(idir, ignore_errors=True)
        shutil.rmtree(intel.parent, ignore_errors=True)


@pytest.fixture
def fresh_intake():
    """An intake where every customer upload has a matching extraction
    row — no staleness signals should fire."""
    root = _session_data_root()
    iid  = _unique_intake_id()
    idir = root / "intakes" / iid
    intel = root / "projects" / iid / "evidence_intelligence"

    (idir / "uploads").mkdir(parents=True, exist_ok=True)
    payload = b"acme policy v2: mfa enforced"
    (idir / "uploads" / "policy.txt").write_bytes(payload)

    intel.mkdir(parents=True, exist_ok=True)
    extraction = {
        "source_file":   "policy.txt",
        "sha256":         _sha256(payload),
        "ocr_status":    "ocr_not_needed",
        "completed_utc": "2026-06-05T10:00:00Z",
    }
    (intel / "extractions.jsonl").write_text(
        json.dumps(extraction) + "\n", encoding="utf-8",
    )
    
    cog = root / "projects" / iid / "cognition"
    cog.mkdir(parents=True, exist_ok=True)
    (cog / "cognition_summary.json").write_text('{"status":"ok"}', encoding="utf-8")
    
    try:
        yield iid
    finally:
        shutil.rmtree(idir, ignore_errors=True)
        shutil.rmtree(intel.parent, ignore_errors=True)


@pytest.fixture
def ocr_opportunity_intake():
    """Every upload IS indexed, but the extraction row says OCR did not
    run. If OCR is available now, the freshness sweep should fire
    `ocr_now_available`."""
    root = _session_data_root()
    iid  = _unique_intake_id()
    idir = root / "intakes" / iid
    intel = root / "projects" / iid / "evidence_intelligence"

    (idir / "uploads").mkdir(parents=True, exist_ok=True)
    payload = b"\xff\xd8\xff\xe0minimal-jpeg-bytes"
    (idir / "uploads" / "scan.jpg").write_bytes(payload)

    intel.mkdir(parents=True, exist_ok=True)
    extraction = {
        "source_file":   "scan.jpg",
        "sha256":         _sha256(payload),
        "ocr_status":    "ocr_binary_unavailable",
        "completed_utc": "2026-06-01T10:00:00Z",
    }
    (intel / "extractions.jsonl").write_text(
        json.dumps(extraction) + "\n", encoding="utf-8",
    )
    
    cog = root / "projects" / iid / "cognition"
    cog.mkdir(parents=True, exist_ok=True)
    (cog / "cognition_summary.json").write_text('{"status":"ok"}', encoding="utf-8")
    
    try:
        yield iid
    finally:
        shutil.rmtree(idir, ignore_errors=True)
        shutil.rmtree(intel.parent, ignore_errors=True)


# ── compute_staleness_signals ─────────────────────────────────────────


def test_unindexed_upload_fires_signal(stale_intake_unindexed):
    iid, _ = stale_intake_unindexed
    sigs = compute_staleness_signals(iid, ocr_runtime_available=False)
    assert SIGNAL_UNINDEXED_UPLOAD in sigs


def test_fresh_intake_fires_no_signals(fresh_intake):
    iid = fresh_intake
    sigs = compute_staleness_signals(iid, ocr_runtime_available=False)
    assert sigs == [], (
        f"a fresh intake must produce zero signals; got {sigs!r}"
    )


def test_ocr_opportunity_fires_when_ocr_runtime_available(ocr_opportunity_intake):
    iid = ocr_opportunity_intake
    # OCR available → signal fires.
    sigs = compute_staleness_signals(iid, ocr_runtime_available=True)
    assert SIGNAL_OCR_NOW_AVAILABLE in sigs
    # OCR not available → signal must NOT fire (no point reprocessing).
    sigs = compute_staleness_signals(iid, ocr_runtime_available=False)
    assert SIGNAL_OCR_NOW_AVAILABLE not in sigs


def test_signals_are_deterministic_and_unique(stale_intake_unindexed):
    iid, _ = stale_intake_unindexed
    a = compute_staleness_signals(iid, ocr_runtime_available=False)
    b = compute_staleness_signals(iid, ocr_runtime_available=False)
    assert a == b, "signal computation must be deterministic"
    assert len(set(a)) == len(a), "no duplicate signal names"


def test_empty_intake_id_returns_empty():
    assert compute_staleness_signals("") == []
    assert compute_staleness_signals(None) == []  # type: ignore[arg-type]


# ── sweep_intakes_for_staleness ───────────────────────────────────────


def test_sweep_dry_run_reports_stale_without_reprocessing(stale_intake_unindexed):
    iid, _ = stale_intake_unindexed
    summary = sweep_intakes_for_staleness(intake_ids=[iid], dry_run=True)

    assert summary["scanned"] == 1
    assert summary["fresh"] == 0
    assert len(summary["stale"]) == 1
    assert summary["stale"][0]["intake_id"] == iid
    assert SIGNAL_UNINDEXED_UPLOAD in summary["stale"][0]["signals"]
    # Dry-run: nothing reprocessed.
    assert summary["reprocessed"] == []
    assert summary["failed"] == []


def test_sweep_respects_max_reprocess_throttle(stale_intake_unindexed):
    """With max_reprocess=0, stale intakes go to `deferred` not
    `reprocessed`. This is the throttle the scheduler uses to keep one
    bad batch from starving the rest of the fleet."""
    iid, _ = stale_intake_unindexed
    summary = sweep_intakes_for_staleness(
        intake_ids=[iid], max_reprocess=0, dry_run=False,
    )
    assert len(summary["stale"]) == 1
    assert summary["reprocessed"] == []
    assert len(summary["deferred"]) == 1
    assert summary["deferred"][0]["intake_id"] == iid


def test_sweep_skips_fresh_intakes(fresh_intake):
    iid = fresh_intake
    summary = sweep_intakes_for_staleness(intake_ids=[iid], dry_run=True)
    assert summary["scanned"] == 1
    assert summary["fresh"] == 1
    assert summary["stale"] == []


def test_sweep_handles_unknown_intake_gracefully():
    """A non-existent intake ID must NOT abort the sweep — it should
    produce zero signals (no uploads to compare against) and count as
    'fresh' for the purposes of the sweep tally."""
    summary = sweep_intakes_for_staleness(
        intake_ids=["FB-doesnotexist00"], dry_run=True,
    )
    assert summary["scanned"] == 1
    # No uploads → no signals → counted as fresh.
    assert summary["fresh"] == 1
    assert summary["stale"] == []
    assert summary["failed"] == []


# ── custody timeline mapping (the autonomous event must be human-
#     readable in the chain of custody) ──────────────────────────────


def test_autonomous_phase_has_custody_label():
    """Every phase string that the freshness sweep writes via
    append_transaction_event must have a mapping in
    custody_timeline._PHASE_TO_EVENT — otherwise the row would render
    with its raw phase string and confuse the operator reading the
    chain a year later."""
    from services.intake.custody_timeline import _PHASE_TO_EVENT
    assert "evidence_intelligence_autonomous_reprocess" in _PHASE_TO_EVENT
    assert _PHASE_TO_EVENT["evidence_intelligence_autonomous_reprocess"] == (
        "evidence_intelligence_autonomous_reprocess"
    )


# ── scheduler wiring (job is registered + cadence is sane) ────────────


def test_ocr_runtime_available_does_not_raise_on_dataclass_return():
    """Regression for the 2026-06-05 production 500.

    ``check_ocr_availability()`` returns an ``OcrAvailability``
    dataclass (.available / .reason / .detail). The original freshness
    code treated it as a dict (.get("tesseract") / .get("poppler"))
    which raised AttributeError in the live container where OCR is
    enabled and the probe actually ran. That AttributeError propagated
    out of sweep_intakes_for_staleness and produced a 500 on
    /api/ops/ei-freshness.

    This test:
      · imports the real ocr module so we use the real dataclass
      · monkeypatches ocr_enabled → True so the probe path runs
      · asserts _ocr_runtime_available returns a bool, never raises
    """
    from services.evidence_intelligence import freshness as F
    from services.evidence_intelligence import ocr as O

    original = O.ocr_enabled
    try:
        O.ocr_enabled = lambda: True
        out = F._ocr_runtime_available()
        assert isinstance(out, bool), (
            "_ocr_runtime_available must return a bool — never raise "
            "even when the OCR probe path is exercised on a host with "
            "no binaries installed"
        )
    finally:
        O.ocr_enabled = original


def test_sweep_route_never_500s_on_helper_failure(monkeypatch):
    """Even if _list_intake_ids raises (corrupted FS, IO error,
    whatever), the sweep MUST return a structured payload, not bubble
    up an exception. /api/ops/ei-freshness has to stay reachable."""
    from services.evidence_intelligence import freshness as F

    def boom():
        raise RuntimeError("simulated FS catastrophe")

    monkeypatch.setattr(F, "_list_intake_ids", boom)
    summary = F.sweep_intakes_for_staleness(dry_run=True)
    assert summary["scanned"] == 0
    assert summary["fresh"] == 0
    assert summary["stale"] == []
    assert len(summary["failed"]) == 1
    assert "list_intakes_failed" in summary["failed"][0]["error"]


def test_freshness_reads_reprocess_report_with_correct_keys(stale_intake_unindexed):
    """Pin the contract between freshness.sweep and
    reprocess_intake_evidence's return shape.

    reprocess_intake_evidence returns:
        files_processed (list)
        files_failed    (list)
        files_seen      (int)
        ocr_succeeded   (int)
        ocr_attempts    (int)

    The freshness sweep originally read `processed` / `ocr_ok` —
    short keys that don't exist in the reprocess payload. Result:
    every autonomous report claimed `processed_count: 0` even when
    the reprocess actually did work, so the operator-visible report
    (and the custody event) lied about the autonomous activity.

    This test runs a REAL reprocess against a stale intake and
    asserts the freshness summary's reprocessed[0] row reports a
    non-zero processed_count + a non-zero files_seen. If the keys
    drift again this catches it immediately.
    """
    iid, _ = stale_intake_unindexed
    summary = sweep_intakes_for_staleness(
        intake_ids=[iid], max_reprocess=1, dry_run=False,
    )
    assert len(summary["reprocessed"]) == 1
    row = summary["reprocessed"][0]

    # The reprocess walked at least one file (the policy.txt we wrote
    # to the fixture's uploads dir). If processed_count is 0 here, the
    # key mismatch is back.
    assert row["files_seen"] >= 1, (
        f"freshness summary says files_seen=0 but the stale fixture "
        f"has a real upload; reprocess key mismatch is back. Full row: {row!r}"
    )
    assert row["processed_count"] >= 1, (
        f"freshness summary says processed_count=0 even though the "
        f"reprocess saw {row['files_seen']} file(s); key mismatch back. "
        f"Full row: {row!r}"
    )
    # The shape of the row must contain ALL the documented keys so
    # downstream consumers (custody event, telemetry, operator UI)
    # don't break on missing fields.
    for key in (
        "intake_id", "signals", "ok",
        "processed_count", "failed_count", "files_seen",
        "ocr_attempts", "ocr_ok",
    ):
        assert key in row, f"freshness reprocess row missing key {key!r}: {row!r}"


def test_scheduler_registers_ei_freshness_sweep_organ():
    """The scheduler MUST add an `ei_freshness_sweep` organ job at boot
    time so the autonomy story isn't just 'we built a helper, but
    nobody calls it.' We assert the job string is present in the
    engine source — robust against import-time side effects."""
    from pathlib import Path
    src = Path("services/engine.py").read_text(encoding="utf-8")
    assert '"ei_freshness_sweep"' in src, (
        "services/engine.py must register an `ei_freshness_sweep` organ "
        "via _add_job — otherwise the autonomous reprocess loop never "
        "actually runs"
    )
    assert "minutes=5" in src, (
        "the sweep cadence should remain 5 minutes (see comment in "
        "engine.py); changing it requires a doctrine note"
    )

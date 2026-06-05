"""Autonomous EI freshness — detect & resolve staleness without operator input.

Doctrine (`docs/KYC_ORGANISM_DOCTRINE.md` → "Autonomy by default"):
    "Anything that can be autonomous, must be."

EI reprocess WAS a manual operator action. That violated the autonomy
rule for the cases where the organism itself knows EI is stale:

  · A file was uploaded but its sha never landed in `extractions.jsonl`
    (race condition / partial failure / new upload after EI completed).
  · OCR became available after the original extraction ran with
    `ocr_disabled` / `ocr_binary_unavailable` (Tesseract/Poppler shipped
    in a later deploy, or KYC_OCR_ENABLED flipped on). The scanned PDF
    we said "metadata-only" for can now actually be read.

Both conditions are detectable from disk + env without operator input.
This module:

  · `compute_staleness_signals(intake_id)` — pure read; returns reasons
    EI is stale (an empty list means "fresh, nothing to do").
  · `sweep_intakes_for_staleness()` — walks every active intake, runs
    the check, and for those that are stale calls
    `reprocess_intake_evidence(wipe=True)` and records the firing
    signals in custody + telemetry. Returns a structured summary the
    scheduler can log.

The manual reprocess endpoint stays as an operator override (force a
rebuild even without a signal). It is no longer the default path.

Failure isolation: per-intake exceptions never abort the sweep. We
emit a `scheduler_ei_freshness_intake_failed` row for each broken
intake and move on.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

# Extraction statuses that indicate OCR did NOT run when it could have
# (or wasn't even attempted). If OCR is now available, these rows are
# stale and a reprocess will harvest text we don't currently have.
_OCR_OPPORTUNITY_STATUSES = frozenset({
    "ocr_disabled",
    "ocr_binary_unavailable",
    "ocr_not_attempted",
    "ocr_skipped",
})

# Sweep-level signals (each name is recorded in custody when it fires).
SIGNAL_UNINDEXED_UPLOAD     = "unindexed_upload"
SIGNAL_OCR_NOW_AVAILABLE    = "ocr_now_available"

# Bound the sweep so a giant fleet doesn't hammer the worker. Tunable
# via env for emergency throttling without a code deploy.
DEFAULT_MAX_REPROCESS_PER_SWEEP = 10


def _ocr_runtime_available() -> bool:
    """True iff OCR can actually run right now: app flag is on AND the
    binaries are installed in the container."""
    try:
        from services.evidence_intelligence.ocr import (
            check_ocr_availability,
            ocr_enabled,
        )
    except Exception:
        return False
    if not ocr_enabled():
        return False
    try:
        info = check_ocr_availability() or {}
    except Exception:
        return False
    return bool(info.get("tesseract") and info.get("poppler"))


def _list_intake_ids() -> List[str]:
    """All canonical intake IDs on disk (FB-*)."""
    try:
        from services.intake.storage import intakes_root
        root = intakes_root()
    except Exception:
        return []
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and p.name.startswith("FB-")
    )


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _real_customer_uploads(intake_id: str) -> List[Path]:
    """Uploads dir files that are real customer payloads (not durability
    sidecars or EI internal artifacts)."""
    try:
        from services.intake.file_durability import is_upload_payload_file
        from services.intake.storage import intake_dir
        from services.evidence_intelligence import _is_real_customer_upload
    except Exception:
        return []
    try:
        uploads = intake_dir(intake_id) / "uploads"
    except Exception:
        return []
    if not uploads.is_dir():
        return []
    return sorted(
        p for p in uploads.iterdir()
        if p.is_file()
        and is_upload_payload_file(p.name)
        and _is_real_customer_upload(p.name)
    )


def _completed_shas(intake_id: str) -> Set[str]:
    """sha256 of every extraction the organism has completed for this
    intake. Drives the `unindexed_upload` signal."""
    try:
        from services.evidence_intelligence import storage
    except Exception:
        return set()
    shas: Set[str] = set()
    try:
        rows = storage.load_jsonl(intake_id, "extractions.jsonl", limit=2000)
    except Exception:
        return shas
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        sha = (r.get("sha256") or "").strip()
        if sha:
            shas.add(sha)
    return shas


def _extractions_marked_as_ocr_skipped(intake_id: str) -> int:
    """Count rows whose ocr_status names a reason OCR did NOT run. If
    OCR is available NOW, every such row is a reprocess opportunity."""
    try:
        from services.evidence_intelligence import storage
    except Exception:
        return 0
    try:
        rows = storage.load_jsonl(intake_id, "extractions.jsonl", limit=2000)
    except Exception:
        return 0
    n = 0
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        status = (r.get("ocr_status") or "").strip().lower()
        if status in _OCR_OPPORTUNITY_STATUSES:
            n += 1
    return n


def compute_staleness_signals(
    intake_id: str,
    *,
    ocr_runtime_available: Optional[bool] = None,
) -> List[str]:
    """Return the list of staleness signals that fire for this intake.

    Empty list ⇒ EI is fresh, no reprocess needed. Each item in the
    returned list names ONE concrete reason a reprocess is justified.
    Order is deterministic for stable custody/telemetry messages.

    ``ocr_runtime_available`` is dependency-injected to keep this
    function unit-testable without monkeypatching env + binaries.
    """
    signals: List[str] = []
    iid = (intake_id or "").strip()
    if not iid:
        return signals

    uploads = _real_customer_uploads(iid)
    completed = _completed_shas(iid)

    # ── Signal 1: any real customer upload whose sha is not in the
    # completed set is unindexed. This catches: new files added after a
    # previous EI run, files that landed during a partial failure, and
    # any race where a file persisted but its extraction row didn't.
    for f in uploads:
        try:
            sha = _sha256_of(f)
        except OSError:
            continue
        if sha and sha not in completed:
            signals.append(SIGNAL_UNINDEXED_UPLOAD)
            break  # one is enough — a single reprocess walks them all

    # ── Signal 2: OCR is available NOW but at least one prior extraction
    # ran without it. The most common case: Tesseract/Poppler shipped in
    # a later deploy, or KYC_OCR_ENABLED flipped on. Reprocessing harvests
    # text the organism currently does not have.
    runtime_ok = (
        _ocr_runtime_available() if ocr_runtime_available is None
        else bool(ocr_runtime_available)
    )
    if runtime_ok and _extractions_marked_as_ocr_skipped(iid) > 0:
        signals.append(SIGNAL_OCR_NOW_AVAILABLE)

    return signals


def sweep_intakes_for_staleness(
    *,
    intake_ids: Optional[Iterable[str]] = None,
    max_reprocess: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Walk active intakes; reprocess any that signal stale. Returns a
    structured summary for the scheduler to log.

    ``intake_ids``    — iterable of intake IDs to limit the scan to.
                        Defaults to every FB-* directory on disk.
    ``max_reprocess`` — soft cap; once this many intakes have been
                        reprocessed in this sweep, remaining stale
                        intakes are deferred to the next tick. Default
                        from ``KYC_EI_FRESHNESS_MAX_REPROCESS`` env var
                        (fallback 10) so emergency throttling is a
                        single env tweak, no deploy.
    ``dry_run``       — compute signals but don't actually reprocess.
                        Used by tests + the diagnostic endpoint.
    """
    if max_reprocess is None:
        try:
            max_reprocess = int(
                os.getenv("KYC_EI_FRESHNESS_MAX_REPROCESS", "")
                or DEFAULT_MAX_REPROCESS_PER_SWEEP
            )
        except ValueError:
            max_reprocess = DEFAULT_MAX_REPROCESS_PER_SWEEP

    targets = list(intake_ids) if intake_ids is not None else _list_intake_ids()
    runtime_ok = _ocr_runtime_available()

    scanned = 0
    fresh = 0
    stale: List[Dict[str, Any]] = []
    reprocessed: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for iid in targets:
        scanned += 1
        try:
            signals = compute_staleness_signals(
                iid, ocr_runtime_available=runtime_ok
            )
        except Exception as exc:
            failed.append({
                "intake_id": iid,
                "error": f"signal_compute_failed:{type(exc).__name__}",
                "detail": str(exc)[:200],
            })
            continue

        if not signals:
            fresh += 1
            continue

        record = {"intake_id": iid, "signals": list(signals)}
        stale.append(record)

        if dry_run:
            continue
        if len(reprocessed) >= max_reprocess:
            deferred.append(record)
            continue

        try:
            from services.evidence_intelligence import reprocess_intake_evidence
            report = reprocess_intake_evidence(iid, wipe=True)
            reprocessed.append({
                **record,
                "ok": bool(report.get("ok")),
                "processed_count": len(report.get("processed", []) or []),
                "ocr_attempts": report.get("ocr_attempts", 0),
                "ocr_ok": report.get("ocr_ok", 0),
            })
            # Record the staleness reasons in custody so a year from now
            # the operator can see WHY the organism reprocessed by itself.
            _record_custody(iid, signals=signals, report=report)
        except Exception as exc:
            failed.append({
                **record,
                "error": f"reprocess_failed:{type(exc).__name__}",
                "detail": str(exc)[:200],
            })

    return {
        "scanned": scanned,
        "fresh": fresh,
        "stale": stale,
        "reprocessed": reprocessed,
        "deferred": deferred,
        "failed": failed,
        "ocr_runtime_available": runtime_ok,
        "max_reprocess": max_reprocess,
        "dry_run": dry_run,
    }


def _record_custody(
    intake_id: str,
    *,
    signals: List[str],
    report: Dict[str, Any],
) -> None:
    """Best-effort custody write so the autonomous reprocess is
    traceable in the chain. Never raises — custody capture must never
    take down the sweep."""
    try:
        from services.intake.transactions import append_transaction_event
    except Exception:
        return
    try:
        append_transaction_event(
            intake_id,
            phase="evidence_intelligence_autonomous_reprocess",
            ok=bool(report.get("ok")),
            metadata={
                "trigger": "freshness_sweep",
                "signals": list(signals),
                "processed_count": len(report.get("processed", []) or []),
                "failed_count": len(report.get("failed", []) or []),
                "ocr_attempts": report.get("ocr_attempts", 0),
                "ocr_ok": report.get("ocr_ok", 0),
            },
        )
    except Exception:
        pass

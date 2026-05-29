"""Forensic reconciliation — disk, registry, audit, index, queue, COTE, telemetry."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evidence_registry import (
    STATUS_CORRUPT,
    STATUS_MISSING,
    STATUS_ORPHANED,
    STATUS_RECOVERED,
    STATUS_VERIFIED,
    build_canonical_evidence_state,
    build_registry_from_canonical,
    compare_derived_to_canonical,
    derive_evidence_registry_for_intake,
    load_registry,
    lookup_by_intake,
)
from .retention import audit_hashes_match, audit_receipt_path, emit_sev1_data_loss_suspected, hash_uploads_on_disk, load_audit_receipt
from .storage import index_intake_ids, index_jsonl, intake_dir, intake_json_path, latest_index_row, list_intake_ids, load_intake_record
from .transactions import intake_commit_complete, load_transaction_log

logger = logging.getLogger(__name__)

_SEVERITY_CRITICAL = "critical"
_SEVERITY_HIGH = "high"
_SEVERITY_MEDIUM = "medium"
_SEVERITY_LOW = "low"

_STARTUP_RECONCILE: Optional[Dict[str, Any]] = None
_PROOF_CACHE: Optional[tuple[float, Dict[str, Any]]] = None
_PROOF_CACHE_TTL_SEC = 45.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def integrity_incidents_path() -> Path:
    from .storage import intakes_root

    p = intakes_root() / "integrity_incidents.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class IntegrityDisagreement:
    subsystem: str
    intake_id: Optional[str]
    evidence_id: Optional[str]
    issue_code: str
    detail: str
    detected_at: str
    severity: str = _SEVERITY_HIGH

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _emit_integrity_telemetry(disagreement: IntegrityDisagreement) -> None:
    try:
        from .telemetry import emit_intake_event

        emit_intake_event(
            "integrity_incident_detected",
            message=disagreement.issue_code,
            metadata=disagreement.to_dict(),
        )
    except Exception:
        pass


def append_integrity_incident(disagreement: IntegrityDisagreement) -> Dict[str, Any]:
    row = disagreement.to_dict()
    path = integrity_incidents_path()
    from .storage import assert_canonical_write_path

    assert_canonical_write_path(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    _emit_integrity_telemetry(disagreement)
    if disagreement.severity == _SEVERITY_CRITICAL:
        logger.critical(
            "[forensic] integrity incident %s intake=%s evidence=%s %s",
            disagreement.issue_code,
            disagreement.intake_id,
            disagreement.evidence_id,
            disagreement.detail,
        )
        try:
            from services.organism_observability.emit import organism_emit

            organism_emit(
                "intake",
                "forensic_integrity_incident",
                message=disagreement.issue_code,
                metadata=row,
                severity="critical",
            )
        except Exception:
            pass
    return row


def load_integrity_incidents(*, tail: int = 500) -> List[Dict[str, Any]]:
    path = integrity_incidents_path()
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in lines[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _queue_intake_ids(*, limit: int = 200) -> set[str]:
    try:
        from .queue import get_operator_review_queue

        q = get_operator_review_queue(limit=limit, persist_recovery=False)
        return {str(r.get("intake_id") or "") for r in q.get("queue") or [] if r.get("intake_id")}
    except Exception:
        return set()


def _cote_signal() -> Dict[str, Any]:
    try:
        from .intake import _latest_intake_custody_signal

        return _latest_intake_custody_signal()
    except Exception:
        return {}


def _reconcile_intake_files(intake_id: str) -> List[IntegrityDisagreement]:
    disagreements: List[IntegrityDisagreement] = []
    now = _utc_now()
    canonical = build_canonical_evidence_state(intake_id)
    on_disk = hash_uploads_on_disk(intake_id)
    registry_rows = lookup_by_intake(intake_id)
    registry_by_stored = {str(r.get("stored_filename") or ""): r for r in registry_rows}
    receipt = load_audit_receipt(intake_id)
    index_row = latest_index_row(intake_id)
    ij_exists = intake_json_path(intake_id).is_file()
    commit_complete = intake_commit_complete(intake_id)
    queue_ids = _queue_intake_ids()

    for mismatch in compare_derived_to_canonical(intake_id):
        code = str(mismatch.get("issue_code") or "registry_canonical_mismatch")
        d = IntegrityDisagreement(
            subsystem="evidence_registry",
            intake_id=intake_id,
            evidence_id=None,
            issue_code=code,
            detail=json.dumps(mismatch, ensure_ascii=False),
            detected_at=now,
            severity=_SEVERITY_CRITICAL,
        )
        disagreements.append(d)
        append_integrity_incident(d)

    for cf in canonical.get("files") or []:
        stored = str(cf.get("stored_filename") or "")
        sha = cf.get("sha256")
        if cf.get("current_status") == STATUS_CORRUPT:
            d = IntegrityDisagreement(
                subsystem="audit_receipt",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="hash_mismatch_corrupt",
                detail=f"Canonical corrupt hash for {stored}",
                detected_at=now,
                severity=_SEVERITY_CRITICAL,
            )
            disagreements.append(d)
            append_integrity_incident(d)
        elif cf.get("current_status") == STATUS_MISSING:
            d = IntegrityDisagreement(
                subsystem="filesystem",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="audit_file_missing_on_disk",
                detail=f"Audit receipt lists {stored} but file missing on disk",
                detected_at=now,
                severity=_SEVERITY_HIGH,
            )
            disagreements.append(d)
            append_integrity_incident(d)
        elif not registry_by_stored.get(stored):
            d = IntegrityDisagreement(
                subsystem="evidence_registry",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="disk_file_not_in_registry",
                detail=f"File {stored} on disk without derived registry entry",
                detected_at=now,
                severity=_SEVERITY_CRITICAL,
            )
            disagreements.append(d)
            append_integrity_incident(d)
        elif stored in on_disk and receipt:
            expected = (receipt.get("file_hashes") or {}).get(stored)
            if expected and sha and expected != sha:
                d = IntegrityDisagreement(
                    subsystem="audit_receipt",
                    intake_id=intake_id,
                    evidence_id=str(registry_by_stored.get(stored, {}).get("evidence_id") or ""),
                    issue_code="hash_mismatch_corrupt",
                    detail=f"Audit hash mismatch for {stored}",
                    detected_at=now,
                    severity=_SEVERITY_CRITICAL,
                )
                disagreements.append(d)
                append_integrity_incident(d)

    for reg in registry_rows:
        stored = str(reg.get("stored_filename") or "")
        if stored and stored not in on_disk and reg.get("current_status") not in (STATUS_MISSING, STATUS_RECOVERED):
            d = IntegrityDisagreement(
                subsystem="filesystem",
                intake_id=intake_id,
                evidence_id=str(reg.get("evidence_id") or ""),
                issue_code="registry_file_missing_on_disk",
                detail=f"Registry entry for {stored} but file missing on disk",
                detected_at=now,
                severity=_SEVERITY_HIGH,
            )
            disagreements.append(d)
            append_integrity_incident(d)

    if on_disk and not receipt:
        d = IntegrityDisagreement(
            subsystem="audit_receipt",
            intake_id=intake_id,
            evidence_id=None,
            issue_code="files_without_audit_receipt",
            detail=f"{len(on_disk)} file(s) on disk without audit receipt",
            detected_at=now,
            severity=_SEVERITY_HIGH,
        )
        disagreements.append(d)
        append_integrity_incident(d)

    if on_disk and not ij_exists:
        d = IntegrityDisagreement(
            subsystem="intake_json",
            intake_id=intake_id,
            evidence_id=None,
            issue_code="files_without_intake_json",
            detail="Files on disk without intake.json",
            detected_at=now,
            severity=_SEVERITY_CRITICAL,
        )
        disagreements.append(d)
        append_integrity_incident(d)

    if on_disk and commit_complete and not index_row:
        d = IntegrityDisagreement(
            subsystem="index",
            intake_id=intake_id,
            evidence_id=None,
            issue_code="committed_not_in_index",
            detail="Commit complete but intake missing from index",
            detected_at=now,
            severity=_SEVERITY_HIGH,
        )
        disagreements.append(d)
        append_integrity_incident(d)

    if on_disk and ij_exists and intake_id not in queue_ids:
        try:
            rec = load_intake_record(intake_id, persist_recovery=False)
            from .storage import is_pending_review

            if is_pending_review(rec.get("review_status")) and commit_complete:
                disagreements.append(
                    IntegrityDisagreement(
                        subsystem="queue",
                        intake_id=intake_id,
                        evidence_id=None,
                        issue_code="intake_not_queue_visible",
                        detail="Committed pending intake not visible in operator queue",
                        detected_at=now,
                        severity=_SEVERITY_MEDIUM,
                    )
                )
        except Exception:
            pass

    if receipt and on_disk and not audit_hashes_match(intake_id, on_disk=on_disk):
        d = IntegrityDisagreement(
            subsystem="audit_receipt",
            intake_id=intake_id,
            evidence_id=None,
            issue_code="audit_hash_mismatch",
            detail="On-disk hashes do not match audit receipt",
            detected_at=now,
            severity=_SEVERITY_CRITICAL,
        )
        disagreements.append(d)
        append_integrity_incident(d)

    return disagreements


def run_forensic_reconciliation(*, limit: int = 200, rebuild_registry: bool = True) -> Dict[str, Any]:
    """
    Compare disk, audit, registry, index, queue, COTE — report only, no auto-repair.
    """
    global _STARTUP_RECONCILE, _PROOF_CACHE
    _PROOF_CACHE = None
    if rebuild_registry:
        build_registry_from_canonical(limit=limit)

    disk_ids = list_intake_ids(limit=limit)
    index_ids = set(index_intake_ids(tail_lines=max(limit, 500)))
    disagreements: List[IntegrityDisagreement] = []

    for iid in disk_ids:
        if iid not in index_ids:
            d = IntegrityDisagreement(
                subsystem="index",
                intake_id=iid,
                evidence_id=None,
                issue_code="disk_intake_not_in_index",
                detail="Intake directory on disk but not in index tail",
                detected_at=_utc_now(),
                severity=_SEVERITY_HIGH,
            )
            disagreements.append(d)
            append_integrity_incident(d)
        disagreements.extend(_reconcile_intake_files(iid))

    for iid in index_ids:
        if iid not in set(disk_ids):
            d = IntegrityDisagreement(
                subsystem="filesystem",
                intake_id=iid,
                evidence_id=None,
                issue_code="index_intake_missing_on_disk",
                detail="Index row without intake directory on disk",
                detected_at=_utc_now(),
                severity=_SEVERITY_CRITICAL,
            )
            disagreements.append(d)
            append_integrity_incident(d)
            emit_sev1_data_loss_suspected(
                f"Index intake {iid} missing on disk",
                detail={"intake_id": iid},
            )

    cote = _cote_signal()
    if cote.get("latest_integrity_mismatch"):
        disagreements.append(
            IntegrityDisagreement(
                subsystem="cote",
                intake_id=str(cote.get("latest_intake_id") or "") or None,
                evidence_id=None,
                issue_code="cote_integrity_mismatch",
                detail="COTE reports latest intake integrity mismatch",
                detected_at=_utc_now(),
                severity=_SEVERITY_MEDIUM,
            )
        )

    critical_count = sum(1 for d in disagreements if d.severity == _SEVERITY_CRITICAL)
    report = {
        "ok": len(disagreements) == 0,
        "disagreement_count": len(disagreements),
        "critical_count": critical_count,
        "disagreements": [d.to_dict() for d in disagreements[:100]],
        "disk_intake_count": len(disk_ids),
        "index_intake_count": len(index_ids),
        "registry_entry_count": len(load_registry()),
        "incident_log": str(integrity_incidents_path().resolve()),
        "index_jsonl": str(index_jsonl().resolve()),
        "reconciled_at_utc": _utc_now(),
    }
    _STARTUP_RECONCILE = report
    return report


def last_forensic_reconciliation() -> Optional[Dict[str, Any]]:
    return dict(_STARTUP_RECONCILE) if _STARTUP_RECONCILE else None


def _proof_record_incident(
    intake_id: str,
    issue_code: str,
    detail: str,
    *,
    severity: str = _SEVERITY_HIGH,
    evidence_id: Optional[str] = None,
    subsystem: str = "proof",
) -> None:
    """Proof is read-only — incidents are recorded during reconcile, not on every proof poll."""
    del intake_id, issue_code, detail, severity, evidence_id, subsystem


def build_integrity_proof(
    *, limit: int = 500, sample_limit: int = 20, use_cache: bool = True
) -> Dict[str, Any]:
    """Fleet-wide visibility proof — ok only when canonical state has zero problems."""
    global _PROOF_CACHE
    now_mono = time.monotonic()
    if use_cache and _PROOF_CACHE is not None:
        cached_at, cached = _PROOF_CACHE
        if now_mono - cached_at < _PROOF_CACHE_TTL_SEC:
            return dict(cached)

    verified_files = 0
    missing_files = 0
    orphaned_files = 0
    corrupt_files = 0
    recovered_files = 0
    registered_files = 0
    pending_files = 0
    missing_audit_files = 0
    structural_problems = 0

    sample_verified: List[str] = []
    sample_missing: List[str] = []
    sample_orphaned: List[str] = []
    sample_corrupt: List[str] = []
    sample_recovered: List[str] = []
    sample_unindexed: List[str] = []

    unindexed_files = 0
    index_ids = set(index_intake_ids(tail_lines=max(limit, 500)))
    seen_disk: set[tuple[str, str]] = set()
    registry = load_registry(tail_lines=50000)
    registry_by_key: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in registry:
        key = (str(row.get("intake_id") or ""), str(row.get("stored_filename") or ""))
        registry_by_key[key] = row

    for intake_id in list_intake_ids(limit=limit):
        canonical = build_canonical_evidence_state(intake_id)
        on_disk = hash_uploads_on_disk(intake_id)
        commit_complete = intake_commit_complete(intake_id)
        ij_exists = intake_json_path(intake_id).is_file()

        if on_disk and not canonical.get("audit_receipt_exists"):
            missing_audit_files += len(on_disk)
            _proof_record_incident(
                intake_id,
                "files_without_audit_receipt",
                f"{len(on_disk)} file(s) on disk without audit receipt",
                subsystem="audit_receipt",
            )

        if on_disk and not ij_exists:
            structural_problems += 1
            _proof_record_incident(
                intake_id,
                "files_without_intake_json",
                "Files on disk without intake.json",
                severity=_SEVERITY_CRITICAL,
                subsystem="intake_json",
            )

        if on_disk and commit_complete and intake_id not in index_ids:
            unindexed_files += len(on_disk)
            if len(sample_unindexed) < sample_limit:
                sample_unindexed.append(intake_id)
            _proof_record_incident(
                intake_id,
                "committed_not_in_index",
                "Commit complete but intake missing from index",
                subsystem="index",
            )

        for cf in canonical.get("files") or []:
            stored = str(cf.get("stored_filename") or "")
            if not stored:
                continue
            key = (intake_id, stored)
            if cf.get("on_disk"):
                seen_disk.add(key)
            status = str(cf.get("current_status") or "")
            reg = registry_by_key.get(key)
            if status == STATUS_CORRUPT:
                corrupt_files += 1
                if len(sample_corrupt) < sample_limit:
                    sample_corrupt.append(f"{intake_id}:{stored}")
                _proof_record_incident(
                    intake_id,
                    "hash_mismatch_corrupt",
                    f"Canonical corrupt hash for {stored}",
                    severity=_SEVERITY_CRITICAL,
                    subsystem="audit_receipt",
                )
            elif status == STATUS_MISSING:
                missing_files += 1
                if len(sample_missing) < sample_limit:
                    sample_missing.append(f"{intake_id}:{stored}")
                _proof_record_incident(
                    intake_id,
                    "audit_file_missing_on_disk",
                    f"Audit lists {stored} but file missing on disk",
                    subsystem="filesystem",
                )
            elif status == STATUS_VERIFIED:
                verified_files += 1
                if len(sample_verified) < sample_limit:
                    sample_verified.append(f"{intake_id}:{stored}")
            elif not reg:
                orphaned_files += 1
                if len(sample_orphaned) < sample_limit:
                    sample_orphaned.append(f"{intake_id}:{stored}")
                _proof_record_incident(
                    intake_id,
                    "disk_file_not_in_registry",
                    f"File {stored} on disk without derived registry entry",
                    severity=_SEVERITY_CRITICAL,
                    subsystem="evidence_registry",
                )
            elif reg.get("current_status") == STATUS_RECOVERED:
                recovered_files += 1
                if len(sample_recovered) < sample_limit:
                    sample_recovered.append(f"{intake_id}:{stored}")
            else:
                registered_files += 1
                pending_files += 1

        for mismatch in compare_derived_to_canonical(intake_id):
            orphaned_files += 1
            stored = str(mismatch.get("stored_filename") or "")
            if len(sample_orphaned) < sample_limit and stored:
                sample_orphaned.append(f"{intake_id}:{stored}")
            _proof_record_incident(
                intake_id,
                str(mismatch.get("issue_code") or "registry_canonical_mismatch"),
                json.dumps(mismatch, ensure_ascii=False),
                severity=_SEVERITY_CRITICAL,
                subsystem="evidence_registry",
            )

    for row in registry:
        key = (str(row.get("intake_id") or ""), str(row.get("stored_filename") or ""))
        if key not in seen_disk and row.get("current_status") not in (STATUS_RECOVERED, STATUS_MISSING):
            missing_files += 1
            if len(sample_missing) < sample_limit:
                sample_missing.append(f"{key[0]}:{key[1]}")
            _proof_record_incident(
                key[0],
                "registry_file_missing_on_disk",
                f"Registry entry for {key[1]} but file missing on disk",
                subsystem="filesystem",
            )

    total_files = len(seen_disk) + missing_files
    problem = (
        missing_files
        + orphaned_files
        + unindexed_files
        + corrupt_files
        + missing_audit_files
        + structural_problems
    )
    incidents = load_integrity_incidents(tail=500)
    incident_count = len(incidents)

    ok = problem == 0
    result = {
        "ok": ok,
        "total_files": total_files,
        "verified_files": verified_files,
        "registered_files": registered_files,
        "pending_files": pending_files,
        "missing_files": missing_files,
        "orphaned_files": orphaned_files,
        "unindexed_files": unindexed_files,
        "corrupt_files": corrupt_files,
        "recovered_files": recovered_files,
        "missing_audit_files": missing_audit_files,
        "integrity_incident_count": incident_count,
        "samples": {
            "verified": sample_verified,
            "missing": sample_missing,
            "orphaned": sample_orphaned,
            "unindexed": sample_unindexed,
            "corrupt": sample_corrupt,
            "recovered": sample_recovered,
        },
        "proof_at_utc": _utc_now(),
    }
    if ok:
        _PROOF_CACHE = (now_mono, result)
    else:
        _PROOF_CACHE = None
    return result


def guard_disk_file_visibility(intake_id: str, stored_filename: str, *, context: str = "upload") -> None:
    """Guardrail — disk file without registry/index/queue visibility."""
    registry = lookup_by_intake(intake_id)
    has_registry = any(str(r.get("stored_filename") or "") == stored_filename for r in registry)
    index_row = latest_index_row(intake_id)
    queue_ids = _queue_intake_ids()
    if has_registry and index_row and intake_id in queue_ids:
        return
    detail = (
        f"Disk file {stored_filename} may disappear from operator view "
        f"(registry={has_registry} index={bool(index_row)} queue={intake_id in queue_ids} context={context})"
    )
    d = IntegrityDisagreement(
        subsystem="guardrail",
        intake_id=intake_id,
        evidence_id=None,
        issue_code="file_visibility_risk",
        detail=detail,
        detected_at=_utc_now(),
        severity=_SEVERITY_CRITICAL,
    )
    append_integrity_incident(d)

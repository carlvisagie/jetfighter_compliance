"""Forensic reconciliation — disk, registry, audit, index, queue, COTE, telemetry."""
from __future__ import annotations

import json
import logging
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
    build_registry_from_disk,
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


def append_integrity_incident(disagreement: IntegrityDisagreement) -> Dict[str, Any]:
    row = disagreement.to_dict()
    path = integrity_incidents_path()
    from .storage import assert_canonical_write_path

    assert_canonical_write_path(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
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

        q = get_operator_review_queue(limit=limit)
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
    idir = intake_dir(intake_id)
    uploads = idir / "uploads"
    on_disk = hash_uploads_on_disk(intake_id)
    registry_rows = lookup_by_intake(intake_id)
    registry_by_stored = {str(r.get("stored_filename") or ""): r for r in registry_rows}
    receipt = load_audit_receipt(intake_id)
    index_row = latest_index_row(intake_id)
    ij_exists = intake_json_path(intake_id).is_file()
    commit_complete = intake_commit_complete(intake_id)
    queue_ids = _queue_intake_ids()

    for stored, sha in on_disk.items():
        reg = registry_by_stored.get(stored)
        if not reg:
            d = IntegrityDisagreement(
                subsystem="evidence_registry",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="disk_file_not_in_registry",
                detail=f"File {stored} on disk without registry entry",
                detected_at=now,
                severity=_SEVERITY_CRITICAL,
            )
            disagreements.append(d)
            append_integrity_incident(d)
        elif reg.get("current_status") == STATUS_VERIFIED and receipt:
            expected = (receipt.get("file_hashes") or {}).get(stored)
            if expected and expected != sha:
                d = IntegrityDisagreement(
                    subsystem="audit_receipt",
                    intake_id=intake_id,
                    evidence_id=str(reg.get("evidence_id") or ""),
                    issue_code="hash_mismatch_corrupt",
                    detail=f"Audit hash mismatch for {stored}",
                    detected_at=now,
                    severity=_SEVERITY_CRITICAL,
                )
                disagreements.append(d)
                append_integrity_incident(d)

    for reg in registry_rows:
        stored = str(reg.get("stored_filename") or "")
        if stored and stored not in on_disk:
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
        disagreements.append(
            IntegrityDisagreement(
                subsystem="audit_receipt",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="files_without_audit_receipt",
                detail=f"{len(on_disk)} file(s) on disk without audit receipt",
                detected_at=now,
                severity=_SEVERITY_HIGH,
            )
        )

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
        disagreements.append(
            IntegrityDisagreement(
                subsystem="index",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="committed_not_in_index",
                detail="Commit complete but intake missing from index",
                detected_at=now,
                severity=_SEVERITY_HIGH,
            )
        )

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
        disagreements.append(
            IntegrityDisagreement(
                subsystem="audit_receipt",
                intake_id=intake_id,
                evidence_id=None,
                issue_code="audit_hash_mismatch",
                detail="On-disk hashes do not match audit receipt",
                detected_at=now,
                severity=_SEVERITY_CRITICAL,
            )
        )

    return disagreements


def run_forensic_reconciliation(*, limit: int = 200, rebuild_registry: bool = True) -> Dict[str, Any]:
    """
    Compare disk, audit, registry, index, queue, COTE — report only, no auto-repair.
    """
    global _STARTUP_RECONCILE
    if rebuild_registry:
        build_registry_from_disk(limit=limit)

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


def build_integrity_proof(*, limit: int = 500, sample_limit: int = 20) -> Dict[str, Any]:
    """Fleet-wide visibility proof — ok only when all problem counts are zero."""
    registry = load_registry(tail_lines=50000)
    registry_by_key: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in registry:
        key = (str(row.get("intake_id") or ""), str(row.get("stored_filename") or ""))
        registry_by_key[key] = row

    verified_files = 0
    missing_files = 0
    orphaned_files = 0
    corrupt_files = 0
    recovered_files = 0
    registered_files = 0
    pending_files = 0

    sample_verified: List[str] = []
    sample_missing: List[str] = []
    sample_orphaned: List[str] = []
    sample_corrupt: List[str] = []
    sample_recovered: List[str] = []
    sample_unindexed: List[str] = []

    unindexed_files = 0
    index_ids = set(index_intake_ids(tail_lines=max(limit, 500)))
    seen_disk: set[tuple[str, str]] = set()

    for intake_id in list_intake_ids(limit=limit):
        uploads = intake_dir(intake_id) / "uploads"
        if not uploads.is_dir():
            continue
        on_disk = hash_uploads_on_disk(intake_id)
        receipt = load_audit_receipt(intake_id)
        commit_complete = intake_commit_complete(intake_id)
        if on_disk and commit_complete and intake_id not in index_ids:
            unindexed_files += len(on_disk)
            if len(sample_unindexed) < sample_limit:
                sample_unindexed.append(intake_id)

        for stored, sha in on_disk.items():
            seen_disk.add((intake_id, stored))
            reg = registry_by_key.get((intake_id, stored))
            expected = (receipt or {}).get("file_hashes", {}).get(stored) if receipt else None
            corrupt = bool(expected and expected != sha)
            if not reg:
                orphaned_files += 1
                if len(sample_orphaned) < sample_limit:
                    sample_orphaned.append(f"{intake_id}:{stored}")
            elif reg.get("current_status") == STATUS_RECOVERED:
                recovered_files += 1
                if len(sample_recovered) < sample_limit:
                    sample_recovered.append(f"{intake_id}:{stored}")
            elif corrupt or reg.get("current_status") == STATUS_CORRUPT:
                corrupt_files += 1
                if len(sample_corrupt) < sample_limit:
                    sample_corrupt.append(f"{intake_id}:{stored}")
            elif reg.get("current_status") == STATUS_VERIFIED:
                verified_files += 1
                if len(sample_verified) < sample_limit:
                    sample_verified.append(f"{intake_id}:{stored}")
            elif reg.get("current_status") == STATUS_MISSING:
                missing_files += 1
                if len(sample_missing) < sample_limit:
                    sample_missing.append(f"{intake_id}:{stored}")
            elif reg.get("current_status") == STATUS_ORPHANED:
                orphaned_files += 1
                if len(sample_orphaned) < sample_limit:
                    sample_orphaned.append(f"{intake_id}:{stored}")
            else:
                registered_files += 1
                pending_files += 1

    for row in registry:
        key = (str(row.get("intake_id") or ""), str(row.get("stored_filename") or ""))
        if key not in seen_disk and row.get("current_status") not in (STATUS_RECOVERED,):
            missing_files += 1
            iid = key[0]
            if len(sample_missing) < sample_limit:
                sample_missing.append(f"{iid}:{key[1]}")

    total_files = len(seen_disk) + sum(
        1 for r in registry if (str(r.get("intake_id") or ""), str(r.get("stored_filename") or "")) not in seen_disk
    )
    problem = (
        missing_files + orphaned_files + unindexed_files + corrupt_files
    )
    incidents = load_integrity_incidents(tail=200)
    incident_count = len(incidents)

    ok = problem == 0 and incident_count == 0
    return {
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

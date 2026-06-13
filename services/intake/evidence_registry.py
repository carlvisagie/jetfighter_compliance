"""Derived evidence registry — rebuilt from canonical disk + audit + transaction state."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .retention import audit_receipt_path, hash_uploads_on_disk, load_audit_receipt, sha256_file
from .storage import assert_canonical_write_path, intake_dir, intakes_root, load_intake_record
from .transactions import intake_commit_complete, load_transaction_log
from services.defensive_wiring import safe_write_text, safe_write_json, safe_append_jsonl

logger = logging.getLogger(__name__)

STATUS_REGISTERED = "registered"
STATUS_VERIFIED = "verified"
STATUS_MISSING = "missing"
STATUS_ORPHANED = "orphaned"
STATUS_CORRUPT = "corrupt"
STATUS_RECOVERED = "recovered"

VALID_STATUSES = frozenset(
    {
        STATUS_REGISTERED,
        STATUS_VERIFIED,
        STATUS_MISSING,
        STATUS_ORPHANED,
        STATUS_CORRUPT,
        STATUS_RECOVERED,
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evidence_registry_path() -> Path:
    p = intakes_root() / "evidence_registry.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _append_registry_row(row: Dict[str, Any]) -> Dict[str, Any]:
    path = evidence_registry_path()
    assert_canonical_write_path(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_registry(*, tail_lines: int = 50000) -> List[Dict[str, Any]]:
    """Latest row per evidence_id."""
    path = evidence_registry_path()
    if not path.is_file():
        return []
    from ..lazy_io import iter_jsonl_lines

    by_id: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl_lines(path, tail_lines=tail_lines):
        eid = str(row.get("evidence_id") or "")
        if eid:
            by_id[eid] = row
    return list(by_id.values())


def lookup_by_intake(intake_id: str, *, tail_lines: int = 50000) -> List[Dict[str, Any]]:
    return [r for r in load_registry(tail_lines=tail_lines) if r.get("intake_id") == intake_id]


def lookup_by_evidence_id(evidence_id: str, *, tail_lines: int = 50000) -> Optional[Dict[str, Any]]:
    for row in reversed(load_registry(tail_lines=tail_lines)):
        if str(row.get("evidence_id") or "") == evidence_id:
            return row
    return None


def build_canonical_evidence_state(intake_id: str) -> Dict[str, Any]:
    """
    Authoritative evidence view from disk, audit receipt, transaction log, intake.json.
  Never reads evidence_registry.jsonl.
    """
    idir = intake_dir(intake_id)
    uploads = idir / "uploads"
    on_disk = hash_uploads_on_disk(intake_id)
    receipt = load_audit_receipt(intake_id)
    audit_hashes = (receipt or {}).get("file_hashes") or {}
    tx_log = load_transaction_log(intake_id, tail=500)
    tx_phases = [str(r.get("phase") or "") for r in tx_log]

    intake_files: List[Dict[str, Any]] = []
    try:
        rec = load_intake_record(intake_id, persist_recovery=False)
        intake_files = list(rec.get("files") or [])
    except Exception:
        pass

    files: List[Dict[str, Any]] = []
    for stored, sha in sorted(on_disk.items()):
        dest = uploads / stored
        expected = audit_hashes.get(stored)
        corrupt = bool(expected and expected != sha)
        original = stored
        for f in intake_files:
            if str(f.get("name") or "") == stored:
                original = str(f.get("original_name") or stored)
                break
        status = STATUS_CORRUPT if corrupt else STATUS_VERIFIED
        if receipt and not expected and stored in audit_hashes:
            status = STATUS_CORRUPT
        files.append(
            {
                "stored_filename": stored,
                "original_filename": original,
                "sha256": sha,
                "expected_sha256": expected,
                "storage_location": str(dest.resolve()),
                "current_status": status,
                "on_disk": True,
            }
        )

    for name, expected in audit_hashes.items():
        if name not in on_disk:
            files.append(
                {
                    "stored_filename": name,
                    "original_filename": name,
                    "sha256": None,
                    "expected_sha256": expected,
                    "storage_location": str((uploads / name).resolve()),
                    "current_status": STATUS_MISSING,
                    "on_disk": False,
                }
            )

    return {
        "intake_id": intake_id,
        "files": files,
        "on_disk_count": len(on_disk),
        "audit_receipt_exists": receipt is not None,
        "audit_receipt_ref": str(audit_receipt_path(intake_id).resolve()) if receipt else None,
        "commit_complete": intake_commit_complete(intake_id),
        "transaction_phases": tx_phases,
        "built_at_utc": _utc_now(),
    }


def _stable_evidence_id(intake_id: str, stored_filename: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kyc-evidence:{intake_id}:{stored_filename}"))


def _canonical_to_registry_rows(canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    intake_id = str(canonical.get("intake_id") or "")
    now = _utc_now()
    receipt_ref = canonical.get("audit_receipt_ref")
    rows: List[Dict[str, Any]] = []
    for f in canonical.get("files") or []:
        stored = str(f.get("stored_filename") or "")
        if not stored:
            continue
        status = str(f.get("current_status") or STATUS_REGISTERED)
        if status not in VALID_STATUSES:
            status = STATUS_REGISTERED
        rows.append(
            {
                "evidence_id": _stable_evidence_id(intake_id, stored),
                "intake_id": intake_id,
                "sha256": f.get("sha256") or f.get("expected_sha256") or "",
                "original_filename": str(f.get("original_filename") or stored),
                "stored_filename": stored,
                "received_timestamp": now,
                "verified_timestamp": now if status == STATUS_VERIFIED else None,
                "storage_location": str(f.get("storage_location") or ""),
                "audit_receipt_ref": receipt_ref,
                "current_status": status,
                "derived_at_utc": now,
                "derived_from": "canonical",
            }
        )
    return rows


def _rewrite_intake_registry_rows(intake_id: str, rows: List[Dict[str, Any]]) -> int:
    """Replace derived rows for one intake in fleet registry — derived write only."""
    path = evidence_registry_path()
    assert_canonical_write_path(path)
    kept: List[str] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("intake_id") or "") == intake_id:
                continue
            kept.append(line)
    for row in rows:
        kept.append(json.dumps(row, ensure_ascii=False))
    safe_write_text(path, "\n".join(kept) + ("\n" if kept else ""), component="intake_evidence", context="evidence registry")
    return len(rows)


def compare_derived_to_canonical(intake_id: str) -> List[Dict[str, Any]]:
    """Return mismatch records when persisted registry disagrees with canonical state."""
    canonical = build_canonical_evidence_state(intake_id)
    canonical_by_stored = {
        str(f.get("stored_filename") or ""): f for f in canonical.get("files") or []
    }
    derived_rows = lookup_by_intake(intake_id)
    derived_by_stored = {str(r.get("stored_filename") or ""): r for r in derived_rows}
    mismatches: List[Dict[str, Any]] = []

    for stored, cf in canonical_by_stored.items():
        dr = derived_by_stored.get(stored)
        if not dr:
            mismatches.append(
                {
                    "issue_code": "canonical_not_in_derived_registry",
                    "stored_filename": stored,
                    "canonical_status": cf.get("current_status"),
                }
            )
            continue
        if str(dr.get("current_status") or "") != str(cf.get("current_status") or ""):
            mismatches.append(
                {
                    "issue_code": "registry_status_mismatch",
                    "stored_filename": stored,
                    "canonical_status": cf.get("current_status"),
                    "derived_status": dr.get("current_status"),
                }
            )
        canon_sha = cf.get("sha256") or cf.get("expected_sha256") or ""
        deriv_sha = str(dr.get("sha256") or "")
        if canon_sha and deriv_sha and canon_sha != deriv_sha:
            mismatches.append(
                {
                    "issue_code": "registry_hash_mismatch",
                    "stored_filename": stored,
                    "canonical_sha256": canon_sha,
                    "derived_sha256": deriv_sha,
                }
            )

    for stored, dr in derived_by_stored.items():
        if stored not in canonical_by_stored:
            mismatches.append(
                {
                    "issue_code": "derived_registry_orphan",
                    "stored_filename": stored,
                    "derived_status": dr.get("current_status"),
                }
            )
    return mismatches


def derive_evidence_registry_for_intake(intake_id: str, *, write: bool = True) -> Dict[str, Any]:
    """Rebuild derived registry slice for one intake from canonical sources."""
    canonical = build_canonical_evidence_state(intake_id)
    rows = _canonical_to_registry_rows(canonical)
    mismatches_before = compare_derived_to_canonical(intake_id) if not write else []
    written = 0
    if write and rows:
        written = _rewrite_intake_registry_rows(intake_id, rows)
    elif write and not rows:
        written = _rewrite_intake_registry_rows(intake_id, [])
    mismatches_after = compare_derived_to_canonical(intake_id) if write else mismatches_before
    return {
        "intake_id": intake_id,
        "canonical_file_count": len(canonical.get("files") or []),
        "derived_rows_written": written,
        "mismatches": mismatches_after,
        "canonical": canonical,
    }


def build_registry_from_canonical(*, limit: int = 500) -> Dict[str, Any]:
    """Fleet-wide derived registry rebuild from canonical intake state."""
    from .storage import list_intake_ids

    total = 0
    mismatch_count = 0
    for intake_id in list_intake_ids(limit=limit):
        out = derive_evidence_registry_for_intake(intake_id, write=True)
        total += int(out.get("derived_rows_written") or 0)
        mismatch_count += len(out.get("mismatches") or [])
    return {
        "ok": mismatch_count == 0,
        "entries_derived": total,
        "mismatch_count": mismatch_count,
        "registry_size": len(load_registry()),
    }


# Backward-compat names used by forensic_reconcile startup hook
build_registry_from_disk = build_registry_from_canonical


def register_verified_files_for_intake(
    intake_id: str,
    *,
    saved_files: List[Dict[str, Any]] | None = None,
    audit_receipt_ref: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Derive hook — refresh derived registry from canonical state (not primary at upload)."""
    del saved_files, audit_receipt_ref  # canonical sources are authoritative
    out = derive_evidence_registry_for_intake(intake_id, write=True)
    return lookup_by_intake(intake_id)


def update_evidence_status(
    evidence_id: str,
    status: str,
    *,
    detail: Optional[str] = None,
    sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Append status transition on derived registry — prefer derive_evidence_registry_for_intake."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid evidence status: {status}")
    prior = lookup_by_evidence_id(evidence_id)
    if not prior:
        raise KeyError(evidence_id)
    intake_id = str(prior.get("intake_id") or "")
    derive_evidence_registry_for_intake(intake_id, write=True)
    refreshed = lookup_by_evidence_id(evidence_id) or prior
    now = _utc_now()
    row = dict(refreshed)
    row["current_status"] = status
    row["status_updated_at_utc"] = now
    if detail:
        row["status_detail"] = detail
    if sha256:
        row["sha256"] = sha256
    if status == STATUS_VERIFIED:
        row["verified_timestamp"] = now
    elif status == STATUS_RECOVERED:
        row["recovered_at_utc"] = now
    row["derived_at_utc"] = now
    return _append_registry_row(row)

"""Canonical evidence registry — append-only fleet-wide file custody index."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .retention import audit_receipt_path, hash_uploads_on_disk, load_audit_receipt, sha256_file
from .storage import assert_canonical_write_path, intake_dir, intakes_root

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


def register_evidence(
    *,
    intake_id: str,
    sha256: str,
    original_filename: str,
    stored_filename: str,
    storage_location: str,
    audit_receipt_ref: Optional[str] = None,
    current_status: str = STATUS_REGISTERED,
    evidence_id: Optional[str] = None,
    received_timestamp: Optional[str] = None,
    verified_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a new evidence row — latest row per evidence_id wins on read."""
    status = current_status if current_status in VALID_STATUSES else STATUS_REGISTERED
    now = _utc_now()
    row: Dict[str, Any] = {
        "evidence_id": evidence_id or str(uuid.uuid4()),
        "intake_id": intake_id,
        "sha256": sha256,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "received_timestamp": received_timestamp or now,
        "verified_timestamp": verified_timestamp or (now if status == STATUS_VERIFIED else None),
        "storage_location": storage_location,
        "audit_receipt_ref": audit_receipt_ref,
        "current_status": status,
        "registered_at_utc": now,
    }
    return _append_registry_row(row)


def update_evidence_status(
    evidence_id: str,
    status: str,
    *,
    detail: Optional[str] = None,
    sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Append status transition — registry is append-only."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid evidence status: {status}")
    prior = lookup_by_evidence_id(evidence_id)
    if not prior:
        raise KeyError(evidence_id)
    now = _utc_now()
    row = dict(prior)
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
    return _append_registry_row(row)


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


def _existing_stored_keys(*, tail_lines: int = 50000) -> set[tuple[str, str]]:
    return {
        (str(r.get("intake_id") or ""), str(r.get("stored_filename") or ""))
        for r in load_registry(tail_lines=tail_lines)
    }


def register_verified_files_for_intake(
    intake_id: str,
    *,
    saved_files: List[Dict[str, Any]],
    audit_receipt_ref: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Register each verified on-disk file after hash verify — idempotent per stored name."""
    idir = intake_dir(intake_id)
    receipt_path = audit_receipt_ref or str(audit_receipt_path(intake_id).resolve())
    on_disk = hash_uploads_on_disk(intake_id)
    existing = _existing_stored_keys()
    registered: List[Dict[str, Any]] = []
    for entry in saved_files:
        stored = str(entry.get("name") or entry.get("stored_name") or "")
        if not stored:
            continue
        key = (intake_id, stored)
        if key in existing:
            continue
        dest = idir / "uploads" / stored
        if not dest.is_file():
            continue
        sha = str(entry.get("sha256") or on_disk.get(stored) or sha256_file(dest))
        row = register_evidence(
            intake_id=intake_id,
            sha256=sha,
            original_filename=str(entry.get("original_name") or stored),
            stored_filename=stored,
            storage_location=str(dest.resolve()),
            audit_receipt_ref=receipt_path,
            current_status=STATUS_VERIFIED,
            received_timestamp=entry.get("uploaded_at_utc"),
            verified_timestamp=_utc_now(),
        )
        existing.add(key)
        registered.append(row)
    return registered


def build_registry_from_disk(*, limit: int = 500) -> Dict[str, Any]:
    """Rebuild missing registry entries from disk + audit receipts."""
    from .storage import list_intake_ids

    existing = _existing_stored_keys()
    added = 0
    for intake_id in list_intake_ids(limit=limit):
        uploads = intake_dir(intake_id) / "uploads"
        if not uploads.is_dir():
            continue
        receipt = load_audit_receipt(intake_id)
        receipt_ref = str(audit_receipt_path(intake_id).resolve()) if receipt else None
        on_disk = hash_uploads_on_disk(intake_id)
        audit_hashes = (receipt or {}).get("file_hashes") or {}
        for name, sha in on_disk.items():
            key = (intake_id, name)
            if key in existing:
                continue
            dest = uploads / name
            expected = audit_hashes.get(name)
            status = STATUS_VERIFIED
            if expected and expected != sha:
                status = STATUS_CORRUPT
            register_evidence(
                intake_id=intake_id,
                sha256=sha,
                original_filename=name,
                stored_filename=name,
                storage_location=str(dest.resolve()),
                audit_receipt_ref=receipt_ref,
                current_status=status,
            )
            existing.add(key)
            added += 1
    return {"ok": True, "entries_added": added, "registry_size": len(load_registry())}

"""Upload contract integrity — per-file lifecycle and count reconciliation."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

STATE_SELECTED = "selected"
STATE_RECEIVED = "received"
STATE_PERSISTED = "persisted"
STATE_VERIFIED = "verified"
STATE_REJECTED = "rejected"
STATE_DUPLICATE = "duplicate"
STATE_FAILED = "failed"

REASON_UNSUPPORTED_EXTENSION = "unsupported_extension"
REASON_FILE_TOO_LARGE = "file_too_large"
REASON_TOTAL_SIZE_LIMIT = "total_size_limit"
REASON_NOT_RECEIVED = "not_received"
REASON_DUPLICATE_RENAMED = "duplicate_renamed"
REASON_PERSIST_FAILED = "persist_failed"
REASON_VERIFY_FAILED = "verify_failed"
REASON_HASH_MISMATCH = "hash_mismatch"

RETRY_RECOMMENDATION = (
    "Ask the customer to re-submit missing files using their magic upload link. "
    "Do not mark intake approved until verified_file_count matches expected_file_count."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_expected_file_names(raw: str) -> List[str]:
    if not (raw or "").strip():
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return []


def new_lifecycle_entry(
    original_name: str,
    *,
    state: str,
    stored_name: Optional[str] = None,
    reason_code: Optional[str] = None,
    reason_detail: Optional[str] = None,
    size: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "original_name": original_name,
        "stored_name": stored_name or original_name,
        "state": state,
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "size": size,
        "at_utc": _utc_now(),
    }


def reconcile_missing_filenames(
    expected_names: List[str],
    received_original_names: List[str],
) -> List[str]:
    """Names the client selected but the server never received in the multipart body."""
    received_set = {n for n in received_original_names if n}
    missing: List[str] = []
    for name in expected_names:
        if name and name not in received_set:
            missing.append(name)
    return missing


def build_integrity_report(
    *,
    expected_file_count: int,
    expected_file_names: List[str],
    lifecycle: List[Dict[str, Any]],
    received_file_count: int,
) -> Dict[str, Any]:
    persisted = [e for e in lifecycle if e.get("state") in (STATE_PERSISTED, STATE_VERIFIED, STATE_DUPLICATE)]
    verified = [e for e in lifecycle if e.get("state") == STATE_VERIFIED]
    rejected = [e for e in lifecycle if e.get("state") == STATE_REJECTED]
    failed = [e for e in lifecycle if e.get("state") == STATE_FAILED]

    received_originals = [
        e.get("original_name")
        for e in lifecycle
        if e.get("state") != STATE_SELECTED and e.get("original_name")
    ]
    missing_names = reconcile_missing_filenames(expected_file_names, received_originals)
    if expected_file_count > received_file_count:
        gap = expected_file_count - received_file_count
        for i in range(gap):
            label = (
                missing_names[i]
                if i < len(missing_names)
                else f"__missing_{len(missing_names) + i + 1}__"
            )
            if label not in missing_names:
                missing_names.append(label)
            lifecycle.append(
                new_lifecycle_entry(
                    label,
                    state=STATE_FAILED,
                    reason_code=REASON_NOT_RECEIVED,
                    reason_detail="Expected by client but not received in upload request",
                )
            )

    persisted_count = sum(
        1
        for e in lifecycle
        if e.get("state") in (STATE_PERSISTED, STATE_VERIFIED, STATE_DUPLICATE)
    )
    verified_count = sum(1 for e in lifecycle if e.get("state") == STATE_VERIFIED)
    expected = max(0, int(expected_file_count or 0)) or received_file_count

    integrity_ok = (
        expected == received_file_count == persisted_count
        and not rejected
        and not failed
        and not missing_names
        and (verified_count == 0 or verified_count == persisted_count == expected)
    )

    missing_files = list(
        dict.fromkeys(
            missing_names
            + [
                str(e.get("original_name") or "")
                for e in lifecycle
                if e.get("state") in (STATE_FAILED, STATE_REJECTED)
                and e.get("reason_code") in (REASON_NOT_RECEIVED, REASON_VERIFY_FAILED, REASON_PERSIST_FAILED)
            ]
        )
    )
    missing_files = [m for m in missing_files if m and not m.startswith("__missing_")]

    rejected_files = [
        {
            "original_name": e.get("original_name"),
            "reason_code": e.get("reason_code"),
            "reason_detail": e.get("reason_detail"),
        }
        for e in lifecycle
        if e.get("state") in (STATE_REJECTED, STATE_FAILED)
    ]

    verified_files = [
        {
            "original_name": e.get("original_name"),
            "stored_name": e.get("stored_name"),
            "sha256": e.get("sha256"),
        }
        for e in lifecycle
        if e.get("state") == STATE_VERIFIED
    ]

    expected_files = [
        {"name": n, "state": STATE_SELECTED}
        for n in (expected_file_names or received_originals[:expected])
    ]

    return {
        "expected_file_count": expected,
        "received_file_count": received_file_count,
        "persisted_file_count": persisted_count,
        "verified_file_count": verified_count,
        "integrity_ok": integrity_ok,
        "integrity_mismatch": not integrity_ok,
        "missing_files": missing_files,
        "rejected_files": rejected_files,
        "expected_files": expected_files,
        "verified_files": verified_files,
        "file_lifecycle": lifecycle,
        "reason_codes": sorted({str(e.get("reason_code")) for e in lifecycle if e.get("reason_code")}),
        "retry_recommendation": None if integrity_ok else RETRY_RECOMMENDATION,
    }


def mark_lifecycle_verified(
    lifecycle: List[Dict[str, Any]],
    saved_files: List[Dict[str, Any]],
    *,
    on_disk_hashes: Dict[str, str],
) -> int:
    """Upgrade persisted entries to verified when hash matches on disk."""
    saved_by_name = {str(f.get("name") or ""): f for f in saved_files}
    verified = 0
    for entry in lifecycle:
        if entry.get("state") not in (STATE_PERSISTED, STATE_DUPLICATE):
            continue
        stored = str(entry.get("stored_name") or entry.get("original_name") or "")
        if not stored or stored not in on_disk_hashes:
            entry["state"] = STATE_FAILED
            entry["reason_code"] = REASON_VERIFY_FAILED
            entry["reason_detail"] = "File not found on durable disk after write"
            continue
        entry["sha256"] = on_disk_hashes[stored]
        saved_by_name.get(stored, {})["sha256"] = on_disk_hashes[stored]
        entry["state"] = STATE_VERIFIED
        verified += 1
    return verified


def intake_has_integrity_mismatch(record: Dict[str, Any]) -> bool:
    ui = record.get("upload_integrity") or {}
    if ui.get("integrity_mismatch"):
        return True
    status = str(record.get("review_status") or record.get("status") or "").lower()
    return status == "partial_upload"


def integrity_summary_for_operator(record: Dict[str, Any]) -> Dict[str, Any]:
    ui = record.get("upload_integrity") or {}
    return {
        "integrity_mismatch": bool(ui.get("integrity_mismatch")),
        "expected_file_count": int(ui.get("expected_file_count") or 0),
        "received_file_count": int(ui.get("received_file_count") or 0),
        "persisted_file_count": int(ui.get("persisted_file_count") or 0),
        "verified_file_count": int(ui.get("verified_file_count") or 0),
        "missing_files": list(ui.get("missing_files") or []),
        "rejected_files": list(ui.get("rejected_files") or []),
        "reason_codes": list(ui.get("reason_codes") or []),
        "retry_recommendation": ui.get("retry_recommendation"),
        "file_lifecycle": list(ui.get("file_lifecycle") or []),
    }

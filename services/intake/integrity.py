"""Upload contract integrity — per-file lifecycle and count reconciliation."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_SELECTED = "selected"
STATE_RECEIVED = "received"
STATE_PERSISTED = "persisted"
STATE_VERIFIED = "verified"
STATE_REJECTED = "rejected"
STATE_DUPLICATE = "duplicate"
STATE_FAILED = "failed"

STATUS_VERIFIED_COMPLETE = "verified_complete"
STATUS_PARTIAL_UPLOAD = "partial_upload"
STATUS_ABANDONED_UPLOAD = "abandoned_upload"
STATUS_REJECTED_FILES = "rejected_files"
STATUS_INTEGRITY_FAILURE = "integrity_failure"
STATUS_PENDING_REVIEW = "pending_review"

REASON_UNSUPPORTED_EXTENSION = "unsupported_extension"
REASON_FILE_TOO_LARGE = "file_too_large"
REASON_TOTAL_SIZE_LIMIT = "total_size_limit"
REASON_NOT_RECEIVED = "not_received"
REASON_DUPLICATE_RENAMED = "duplicate_renamed"
REASON_PERSIST_FAILED = "persist_failed"
REASON_VERIFY_FAILED = "verify_failed"
REASON_HASH_MISMATCH = "hash_mismatch"

_INTEGRITY_FAILURE_REASONS = frozenset(
    {
        REASON_PERSIST_FAILED,
        REASON_VERIFY_FAILED,
        REASON_HASH_MISMATCH,
    }
)

RETRY_RECOMMENDATION = (
    "Ask the customer to re-submit missing files using their magic upload link. "
    "Do not mark intake approved until verified_file_count matches expected_file_count."
)

ABANDONED_RETRY_RECOMMENDATION = (
    "Upload session started but not all selected files were received. "
    "Customer should reopen their magic link and re-submit remaining files."
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


def parse_upload_manifest(raw: str) -> Dict[str, Any]:
    """Client upload_manifest JSON from founding-beta.js."""
    if not (raw or "").strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        logger.warning("upload_manifest JSON parse failed")
    return {}


def summarize_user_agent(user_agent: str) -> str:
    ua = (user_agent or "").strip()
    if not ua:
        return "unknown"
    if len(ua) <= 72:
        return ua
    return ua[:69] + "..."


def detect_submission_method(
    manifest: Optional[Dict[str, Any]],
    *,
    user_agent: str = "",
    has_resume_token: bool = False,
    has_magic_token: bool = False,
) -> str:
    """desktop | mobile | resume | magic-link | QR."""
    m = manifest or {}
    explicit = str(m.get("submission_method") or "").strip().lower()
    if explicit in ("desktop", "mobile", "resume", "magic-link", "qr"):
        return "qr" if explicit == "qr" else explicit

    route = str(m.get("route") or "").lower()
    if m.get("qr_scan") or "qr=1" in route:
        return "qr"
    if m.get("resume_token_used") or has_resume_token:
        return "resume"
    if has_magic_token or ("token=" in route and "qr=1" not in route):
        return "magic-link"

    ua = (user_agent or str(m.get("client_user_agent") or "")).lower()
    if re.search(r"mobi|android|iphone|ipad", ua):
        return "mobile"
    return "desktop"


def client_ip_from_headers(
    *,
    x_forwarded_for: str = "",
    client_host: str = "",
) -> str:
    if (x_forwarded_for or "").strip():
        return x_forwarded_for.split(",")[0].strip()
    return (client_host or "").strip()


def new_lifecycle_entry(
    original_name: str,
    *,
    state: str,
    stored_name: Optional[str] = None,
    reason_code: Optional[str] = None,
    reason_detail: Optional[str] = None,
    size: Optional[int] = None,
    source_session_id: Optional[str] = None,
    duplicate_of: Optional[str] = None,
    media_type: Optional[str] = None,
) -> Dict[str, Any]:
    sanitized = stored_name or original_name
    ext = Path(sanitized).suffix.lower()
    now = _utc_now()
    entry: Dict[str, Any] = {
        "original_name": original_name,
        "original_filename": original_name,
        "stored_name": sanitized,
        "sanitized_filename": sanitized,
        "state": state,
        "lifecycle_state": state,
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "rejected_reason": reason_code if state == STATE_REJECTED else None,
        "failure_reason": reason_code if state == STATE_FAILED else None,
        "size": size,
        "size_bytes": size,
        "extension": ext,
        "media_type": media_type,
        "duplicate_of": duplicate_of,
        "source_session_id": source_session_id,
        "at_utc": now,
    }
    if state == STATE_RECEIVED:
        entry["received_at"] = now
    if state in (STATE_PERSISTED, STATE_DUPLICATE):
        entry["persisted_at"] = now
    if state == STATE_VERIFIED:
        entry["verified_at"] = now
    if state == STATE_REJECTED:
        entry["rejected_at"] = now
    return entry


def lifecycle_to_custody_row(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Operator/customer lifecycle table row."""
    state = str(entry.get("lifecycle_state") or entry.get("state") or "")
    reason = entry.get("reason_code")
    return {
        "original_filename": entry.get("original_filename") or entry.get("original_name"),
        "sanitized_filename": entry.get("sanitized_filename") or entry.get("stored_name"),
        "size_bytes": entry.get("size_bytes") if entry.get("size_bytes") is not None else entry.get("size"),
        "media_type": entry.get("media_type"),
        "extension": entry.get("extension") or Path(str(entry.get("stored_name") or "")).suffix.lower(),
        "sha256": entry.get("sha256"),
        "lifecycle_state": state,
        "received_at": entry.get("received_at"),
        "persisted_at": entry.get("persisted_at"),
        "verified_at": entry.get("verified_at"),
        "rejected_reason": entry.get("rejected_reason")
        or (reason if state == STATE_REJECTED else None),
        "failure_reason": entry.get("failure_reason")
        or (reason if state == STATE_FAILED else None),
        "duplicate_of": entry.get("duplicate_of"),
        "source_session_id": entry.get("source_session_id"),
        "reason_detail": entry.get("reason_detail"),
    }


def _count_lifecycle_states(lifecycle: List[Dict[str, Any]]) -> Dict[str, int]:
    rejected = duplicate = failed = 0
    for e in lifecycle:
        st = str(e.get("state") or "")
        if st == STATE_REJECTED:
            rejected += 1
        elif st == STATE_DUPLICATE:
            duplicate += 1
        elif st == STATE_FAILED:
            failed += 1
    return {
        "rejected_file_count": rejected,
        "duplicate_file_count": duplicate,
        "failed_file_count": failed,
    }


def merge_batch_lifecycle(
    prior: List[Dict[str, Any]],
    new_batch: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge prior intake lifecycle with current batch — current batch wins on name collision."""
    by_key: Dict[str, Dict[str, Any]] = {}
    for entry in prior:
        key = str(entry.get("stored_name") or entry.get("original_name") or "")
        if key:
            by_key[key] = dict(entry)
    for entry in new_batch:
        key = str(entry.get("stored_name") or entry.get("original_name") or "")
        if key:
            by_key[key] = dict(entry)
        else:
            by_key[f"__anon_{len(by_key)}"] = dict(entry)
    return list(by_key.values())


def derive_intake_status(
    integrity: Dict[str, Any],
    *,
    durability_ok: bool = True,
    operator_acknowledged_partial: bool = False,
    batch_complete: bool = True,
    abandoned: bool = False,
) -> str:
    """
    Custody status for intake record.
    Priority: INTEGRITY_FAILURE > PARTIAL_UPLOAD > REJECTED_FILES > VERIFIED_COMPLETE.
    """
    expected = int(integrity.get("expected_file_count") or 0)
    received = int(integrity.get("received_file_count") or 0)
    persisted = int(integrity.get("persisted_file_count") or 0)
    verified = int(integrity.get("verified_file_count") or 0)
    failed = int(integrity.get("failed_file_count") or 0)
    rejected = int(integrity.get("rejected_file_count") or 0)
    lifecycle = list(integrity.get("file_lifecycle") or [])

    integrity_failure = not durability_ok or any(
        e.get("state") == STATE_FAILED
        and e.get("reason_code") in _INTEGRITY_FAILURE_REASONS
        for e in lifecycle
    )
    if integrity_failure:
        return STATUS_INTEGRITY_FAILURE

    if abandoned or (not batch_complete and expected > verified and verified == 0 and received == 0):
        return STATUS_ABANDONED_UPLOAD

    counts_match = (
        expected == received == persisted == verified and failed == 0
    )
    if not batch_complete and expected > verified:
        return STATUS_PARTIAL_UPLOAD
    if not counts_match or failed > 0:
        return STATUS_PARTIAL_UPLOAD
    if rejected > 0:
        return STATUS_REJECTED_FILES
    if counts_match:
        return STATUS_VERIFIED_COMPLETE
    return STATUS_PARTIAL_UPLOAD


def review_status_from_custody(
    custody_status: str,
    *,
    operator_acknowledged_partial: bool = False,
) -> str:
    """Operator queue review_status derived from custody."""
    if custody_status == STATUS_INTEGRITY_FAILURE:
        return STATUS_INTEGRITY_FAILURE
    if custody_status == STATUS_PARTIAL_UPLOAD:
        return STATUS_PENDING_REVIEW if operator_acknowledged_partial else STATUS_PARTIAL_UPLOAD
    if custody_status in (STATUS_VERIFIED_COMPLETE, STATUS_REJECTED_FILES):
        return STATUS_PENDING_REVIEW
    return STATUS_PENDING_REVIEW


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
    batch_complete: bool = True,
) -> Dict[str, Any]:
    persisted = [
        e
        for e in lifecycle
        if e.get("state") in (STATE_PERSISTED, STATE_VERIFIED, STATE_DUPLICATE)
    ]
    verified = [e for e in lifecycle if e.get("state") == STATE_VERIFIED]
    rejected = [e for e in lifecycle if e.get("state") == STATE_REJECTED]
    failed = [e for e in lifecycle if e.get("state") == STATE_FAILED]

    received_originals = [
        e.get("original_name")
        for e in lifecycle
        if e.get("state") != STATE_SELECTED and e.get("original_name")
    ]
    missing_names = reconcile_missing_filenames(expected_file_names, received_originals)
    if batch_complete and expected_file_count > received_file_count:
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
    state_counts = _count_lifecycle_states(lifecycle)
    rejected_count = state_counts["rejected_file_count"]
    duplicate_count = state_counts["duplicate_file_count"]
    failed_count = state_counts["failed_file_count"]

    # Over-delivery (received > expected, all verified) is not an integrity failure.
    # integrity_ok requires every received file to be verified with nothing missing/rejected.
    integrity_ok = (
        batch_complete
        and received_file_count >= expected
        and persisted_count >= expected
        and not rejected
        and failed_count == 0
        and not missing_names
        and verified_count >= expected
        and verified_count == persisted_count
    )

    retry = None if integrity_ok else RETRY_RECOMMENDATION
    if not batch_complete and expected > received_file_count:
        retry = ABANDONED_RETRY_RECOMMENDATION

    missing_files = list(
        dict.fromkeys(
            missing_names
            + [
                str(e.get("original_name") or "")
                for e in lifecycle
                if e.get("state") in (STATE_FAILED, STATE_REJECTED)
                and e.get("reason_code")
                in (REASON_NOT_RECEIVED, REASON_VERIFY_FAILED, REASON_PERSIST_FAILED)
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

    lifecycle_table = [lifecycle_to_custody_row(e) for e in lifecycle]

    report: Dict[str, Any] = {
        "expected_file_count": expected,
        "received_file_count": received_file_count,
        "persisted_file_count": persisted_count,
        "verified_file_count": verified_count,
        "rejected_file_count": rejected_count,
        "duplicate_file_count": duplicate_count,
        "failed_file_count": failed_count,
        "integrity_ok": integrity_ok,
        # Only flag mismatch when files are UNDER-delivered or unverified,
        # not when more files arrived than declared and all are verified.
        "integrity_mismatch": not integrity_ok
        or (not batch_complete and expected > verified_count)
        or (batch_complete and expected > verified_count),
        "missing_files": missing_files,
        "rejected_files": rejected_files,
        "expected_files": expected_files,
        "verified_files": verified_files,
        "file_lifecycle": lifecycle,
        "file_lifecycle_table": lifecycle_table,
        "reason_codes": sorted({str(e.get("reason_code")) for e in lifecycle if e.get("reason_code")}),
        "retry_recommendation": retry,
        "batch_complete": batch_complete,
    }
    report["custody_status"] = derive_intake_status(
        report,
        durability_ok=True,
        batch_complete=batch_complete,
    )
    return report


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
        if entry.get("state") == STATE_VERIFIED:
            verified += 1
            continue
        if entry.get("state") not in (STATE_PERSISTED, STATE_DUPLICATE):
            continue
        stored = str(entry.get("stored_name") or entry.get("original_name") or "")
        if not stored or stored not in on_disk_hashes:
            entry["state"] = STATE_FAILED
            entry["lifecycle_state"] = STATE_FAILED
            entry["reason_code"] = REASON_VERIFY_FAILED
            entry["failure_reason"] = REASON_VERIFY_FAILED
            entry["reason_detail"] = "File not found on durable disk after write"
            continue
        entry["sha256"] = on_disk_hashes[stored]
        saved_by_name.get(stored, {})["sha256"] = on_disk_hashes[stored]
        entry["state"] = STATE_VERIFIED
        entry["lifecycle_state"] = STATE_VERIFIED
        entry["verified_at"] = _utc_now()
        verified += 1
    return verified


def intake_has_integrity_mismatch(record: Dict[str, Any]) -> bool:
    ui = record.get("upload_integrity") or {}
    if ui.get("integrity_mismatch"):
        return True
    status = str(record.get("custody_status") or record.get("review_status") or record.get("status") or "").lower()
    return status in (STATUS_PARTIAL_UPLOAD, STATUS_INTEGRITY_FAILURE)


def integrity_summary_for_operator(record: Dict[str, Any]) -> Dict[str, Any]:
    ui = record.get("upload_integrity") or {}
    custody = record.get("upload_custody") or {}
    return {
        "integrity_mismatch": bool(ui.get("integrity_mismatch")),
        "custody_status": record.get("custody_status") or ui.get("custody_status"),
        "expected_file_count": int(ui.get("expected_file_count") or 0),
        "received_file_count": int(ui.get("received_file_count") or 0),
        "persisted_file_count": int(ui.get("persisted_file_count") or 0),
        "verified_file_count": int(ui.get("verified_file_count") or 0),
        "rejected_file_count": int(ui.get("rejected_file_count") or 0),
        "duplicate_file_count": int(ui.get("duplicate_file_count") or 0),
        "failed_file_count": int(ui.get("failed_file_count") or 0),
        "missing_files": list(ui.get("missing_files") or []),
        "rejected_files": list(ui.get("rejected_files") or []),
        "reason_codes": list(ui.get("reason_codes") or []),
        "retry_recommendation": ui.get("retry_recommendation"),
        "file_lifecycle": list(ui.get("file_lifecycle") or []),
        "file_lifecycle_table": list(ui.get("file_lifecycle_table") or []),
        "source_ip": custody.get("source_ip"),
        "user_agent_summary": custody.get("user_agent_summary"),
        "upload_session_id": custody.get("upload_session_id"),
        "submission_method": custody.get("submission_method"),
        "originating_route": custody.get("originating_route"),
        "newest_upload_at_utc": custody.get("newest_upload_at_utc"),
    }


def latest_integrity_mismatch_from_records(records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Most recent intake with custody mismatch — for operator diagnostics."""
    for rec in records:
        if intake_has_integrity_mismatch(rec):
            ui = rec.get("upload_integrity") or {}
            return {
                "intake_id": rec.get("intake_id"),
                "custody_status": rec.get("custody_status") or ui.get("custody_status"),
                "expected_file_count": ui.get("expected_file_count"),
                "received_file_count": ui.get("received_file_count"),
                "persisted_file_count": ui.get("persisted_file_count"),
                "verified_file_count": ui.get("verified_file_count"),
                "failed_file_count": ui.get("failed_file_count"),
                "missing_files": ui.get("missing_files"),
            }
    return None

"""Customer paperwork intake — upload-first, no login wall."""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile

from services.production import safe_upload_filename
from services.public_url import get_public_base_url
from services.security import make_founding_beta_token, parse_founding_beta_token

from .storage import (
    all_intake_ids,
    atomic_write_bytes,
    atomic_write_json,
    canonical_intake_dir,
    count_upload_files,
    ensure_canonical_intake_dir,
    index_jsonl,
    intake_dir,
    intake_json_path,
    intakes_root,
    load_intake_record,
    normalize_intake_record,
    upsert_index_row,
)
from .telemetry import emit_intake_event
from services.durable_storage import require_intake_upload_allowed

logger = logging.getLogger(__name__)

_INTAKE_COMMIT_LOCKS: Dict[str, threading.Lock] = {}
_INTAKE_LOCK_GUARD = threading.Lock()


def _intake_commit_lock(intake_id: str) -> threading.Lock:
    with _INTAKE_LOCK_GUARD:
        lock = _INTAKE_COMMIT_LOCKS.get(intake_id)
        if lock is None:
            lock = threading.Lock()
            _INTAKE_COMMIT_LOCKS[intake_id] = lock
        return lock


MAX_FILE_BYTES = 52_428_800
MAX_FILES_PER_REQUEST = 25
MAX_TOTAL_INTAKE_BYTES = 250 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".xlsx",
        ".zip",
        ".png",
        ".jpg",
        ".jpeg",
        ".csv",
        ".txt",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _intake_dir(intake_id: str) -> Path:
    try:
        return ensure_canonical_intake_dir(intake_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid intake_id") from e


def _validate_extension(safe_name: str) -> None:
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed: {ext or '(none)'}. "
            "Use PDF, DOCX, XLSX, ZIP, PNG, JPG, CSV, or TXT.",
        )


def _contact_ok(email: str, phone: str) -> bool:
    email = (email or "").strip()
    phone = (phone or "").strip()
    if email and "@" in email and "." in email.split("@")[-1]:
        return True
    if phone and sum(c.isdigit() for c in phone) >= 7:
        return True
    return False


def _load_intake(intake_id: str) -> Dict[str, Any]:
    try:
        return load_intake_record(intake_id, persist_recovery=True)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Intake not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid intake_id") from e


def _save_intake(intake_id: str, data: Dict[str, Any]) -> None:
    data["updated_at_utc"] = _utc_now()
    rec = normalize_intake_record(data, intake_id=intake_id)
    atomic_write_json(intake_json_path(intake_id), rec)


def _append_index(row: Dict[str, Any]) -> None:
    row = dict(row)
    row.setdefault("committed_at_utc", _utc_now())
    try:
        upsert_index_row(row)
    except OSError as exc:
        logger.critical("index write failed intake=%s: %s", row.get("intake_id"), exc)
        raise HTTPException(
            status_code=500,
            detail="Your files could not be indexed for operator review. Please try again.",
            headers={"X-KYC-Error-Code": "index_write_failed"},
        ) from exc


def _commit_intake_state(
    intake_id: str,
    record: Dict[str, Any],
    *,
    integrity: Dict[str, Any],
    committed: bool,
) -> None:
    """Single publish point — intake.json then index, only after audit when files exist."""
    from .transactions import (
        PHASE_INDEX_COMMITTED,
        PHASE_INTAKE_COMMITTED,
        append_transaction_event,
    )

    _save_intake(intake_id, record)
    append_transaction_event(
        intake_id,
        PHASE_INTAKE_COMMITTED,
        metadata={
            "custody_status": record.get("custody_status"),
            "file_count": record.get("file_count"),
        },
    )
    _append_index(
        {
            "intake_id": intake_id,
            "created_at_utc": record.get("created_at_utc") or _utc_now(),
            "status": record.get("review_status"),
            "company": record.get("company"),
            "email": record.get("email"),
            "urgent": record.get("urgent"),
            "file_count": record.get("file_count", 0),
            "updated": True,
            "committed": committed,
            "integrity_mismatch": bool(integrity.get("integrity_mismatch")),
            "custody_status": record.get("custody_status"),
        }
    )
    append_transaction_event(
        intake_id,
        PHASE_INDEX_COMMITTED,
        metadata={"committed": committed},
    )


def validate_intake_access(intake_id: str, token: str) -> Dict[str, Any]:
    try:
        info = parse_founding_beta_token(token)
    except ValueError as e:
        code = str(e)
        if code == "intake_token_expired":
            raise HTTPException(status_code=401, detail="Upload link expired") from e
        raise HTTPException(status_code=401, detail="Invalid upload link") from e
    if info.get("i") != intake_id:
        raise HTTPException(status_code=403, detail="Token does not match intake")
    return _load_intake(intake_id)


def _intake_total_bytes(intake_id: str) -> int:
    uploads = _intake_dir(intake_id) / "uploads"
    if not uploads.is_dir():
        return 0
    total = 0
    for p in uploads.iterdir():
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def create_intake(
    *,
    email: str = "",
    phone: str = "",
    company: str = "",
    context: str = "",
    deadline: str = "",
) -> Dict[str, Any]:
    if not _contact_ok(email, phone):
        raise HTTPException(status_code=400, detail="Email or phone required")
    intakes_root()
    intake_id = f"FB-{uuid.uuid4().hex[:12]}"
    idir = _intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    (idir / "uploads").mkdir(exist_ok=True)
    urgent = bool((deadline or "").strip())
    # Sanitise the company name at the boundary — if a customer pasted a URL
    # into the form by mistake, store the apex domain instead of garbage.
    # The same sanitiser is applied at display time inside VIO; doing it here
    # too means we never accumulate dirty data in the index going forward.
    from services.vio_overview import _clean_company_name as _cln
    clean_company = _cln((company or "").strip()[:200])
    if clean_company == "Unknown":
        clean_company = ""  # preserve empty intent rather than the literal word
    record = {
        "intake_id": intake_id,
        "created_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
        "status": "pending_review",
        "review_status": "pending_review",
        "company": clean_company[:200],
        "email": (email or "").strip().lower()[:200],
        "phone": (phone or "").strip()[:40],
        "context": (context or "").strip()[:2000],
        "deadline": (deadline or "").strip()[:120],
        "urgent": urgent,
        "files": [],
        "file_count": 0,
        "total_bytes": 0,
    }
    _save_intake(intake_id, record)
    from .transactions import PHASE_INDEX_COMMITTED, PHASE_INTAKE_COMMITTED, append_transaction_event

    append_transaction_event(intake_id, PHASE_INTAKE_COMMITTED, metadata={"file_count": 0})
    _append_index(
        {
            "intake_id": intake_id,
            "created_at_utc": record["created_at_utc"],
            "status": "pending_review",
            "company": clean_company,
            "email": record["email"],
            "urgent": urgent,
            "file_count": 0,
            "committed": True,
        }
    )
    append_transaction_event(intake_id, PHASE_INDEX_COMMITTED, metadata={"committed": True})
    logger.info(
        "Founding beta intake created %s at %s",
        intake_id,
        intake_json_path(intake_id).parent,
    )
    emit_intake_event(
        "intake_received",
        message=f"Intake {intake_id} created",
        metadata={"intake_id": intake_id, "urgent": urgent},
    )
    try:
        from .learning_hooks import record_intake_learning

        record_intake_learning("intake_received", intake_id=intake_id)
    except Exception:
        pass
    return record


def _magic_link(intake_id: str, token: str) -> str:
    base = get_public_base_url().rstrip("/")
    return f"{base}/ui/intake?intake_id={intake_id}&token={token}"


def _qr_png(link: str) -> bytes:
    from services.customer_friction import generate_qr_png

    return generate_qr_png(link)


def _apply_custody_status(record: Dict[str, Any], integrity: Dict[str, Any], *, durability_ok: bool) -> None:
    from .integrity import derive_intake_status, review_status_from_custody

    integrity = dict(integrity)
    batch_complete = bool(integrity.get("batch_complete", True))
    integrity["custody_status"] = derive_intake_status(
        integrity,
        durability_ok=durability_ok,
        operator_acknowledged_partial=bool(record.get("operator_acknowledged_partial")),
        batch_complete=batch_complete,
        abandoned=bool(record.get("upload_abandoned")),
    )
    custody_status = integrity["custody_status"]
    record["custody_status"] = custody_status
    record["upload_integrity"] = integrity
    record["review_status"] = review_status_from_custody(
        custody_status,
        operator_acknowledged_partial=bool(record.get("operator_acknowledged_partial")),
    )
    record["status"] = record["review_status"]
    record["urgent"] = bool(record.get("urgent")) or custody_status in (
        "partial_upload",
        "integrity_failure",
        "rejected_files",
        "abandoned_upload",
    )


def _safe_emit_intake_event(
    intake_id: str,
    event_type: str,
    *,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    custody: Optional[Dict[str, Any]] = None,
) -> bool:
    from .transactions import PHASE_TELEMETRY_FAILED, append_transaction_event

    ok = emit_intake_event(event_type, message=message, metadata=metadata)
    if not ok:
        append_transaction_event(
            intake_id,
            PHASE_TELEMETRY_FAILED,
            ok=False,
            metadata={"event_type": event_type},
        )
        if custody is not None:
            custody["telemetry_degraded"] = True
    return ok


def _link_intake_to_lead(intake_id: str, record: Dict[str, Any]) -> None:
    """When an intake has a lead_id, update that lead's status and emit an acquisition_conversion alert."""
    lead_id = record.get("lead_id") or ""
    if not lead_id:
        return
    try:
        from services.acquisition.storage import leads_dir, load_all_leads, rewrite_leads_csv, LEAD_JSONL
        from services.acquisition.models import utc_now as lead_utc_now
        import json

        leads, _ = load_all_leads()
        changed = False
        for lead in leads:
            if lead.lead_id == lead_id and lead.status not in ("intake_completed", "rejected", "do_not_contact"):
                lead.status = "intake_completed"
                lead.updated_utc = lead_utc_now()
                changed = True
                break
        if changed:
            rewrite_leads_csv(leads)
            # Rewrite the JSONL in-place with updated lead
            path = leads_dir() / LEAD_JSONL
            with path.open("w", encoding="utf-8") as f:
                for lead in leads:
                    f.write(json.dumps(lead.to_dict(), ensure_ascii=False) + "\n")

        # Emit conversion alert regardless of whether status changed
        from services.alerts.engine import alert_acquisition_conversion
        alert_acquisition_conversion(lead_id=lead_id, intake_id=intake_id)
    except Exception as exc:
        logger.warning("_link_intake_to_lead skipped: %s", exc)


async def process_upload(
    files: List[UploadFile],
    *,
    intake_id: str = "",
    token: str = "",
    email: str = "",
    phone: str = "",
    company: str = "",
    context: str = "",
    deadline: str = "",
    ref: str = "",
    expected_file_count: int = 0,
    expected_file_names: Optional[List[str]] = None,
    upload_manifest: Optional[Dict[str, Any]] = None,
    request_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    require_intake_upload_allowed()
    if not files:
        raise HTTPException(status_code=400, detail="At least one file required")

    if intake_id and token:
        record = validate_intake_access(intake_id, token)
        if company:
            record["company"] = company.strip()[:200]
        if email:
            record["email"] = email.strip().lower()[:200]
        if phone:
            record["phone"] = phone.strip()[:40]
        if context:
            record["context"] = context.strip()[:2000]
        if deadline:
            record["deadline"] = deadline.strip()[:120]
            record["urgent"] = True
    else:
        record = create_intake(
            email=email,
            phone=phone,
            company=company,
            context=context,
            deadline=deadline,
        )
        intake_id = record["intake_id"]
        token = make_founding_beta_token(intake_id)

    # Acquisition attribution: store lead_id when a ref=LD-xxx param was passed
    if ref and str(ref).startswith("LD-") and not record.get("lead_id"):
        record["lead_id"] = str(ref).strip()[:64]

    commit_lock = _intake_commit_lock(intake_id)
    commit_lock.acquire()
    try:
        return await _process_upload_locked(
            files=files,
            intake_id=intake_id,
            token=token,
            record=record,
            expected_file_count=expected_file_count,
            expected_file_names=expected_file_names,
            upload_manifest=upload_manifest,
            request_metadata=request_metadata,
        )
    finally:
        commit_lock.release()


async def _process_upload_locked(
    *,
    files: List[UploadFile],
    intake_id: str,
    token: str,
    record: Dict[str, Any],
    expected_file_count: int,
    expected_file_names: Optional[List[str]],
    upload_manifest: Optional[Dict[str, Any]],
    request_metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    uploads_dir = _intake_dir(intake_id) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    total_before = _intake_total_bytes(intake_id)
    saved: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    from .integrity import (
        REASON_DUPLICATE_RENAMED,
        REASON_FILE_TOO_LARGE,
        REASON_PERSIST_FAILED,
        REASON_TOTAL_SIZE_LIMIT,
        REASON_UNSUPPORTED_EXTENSION,
        STATE_DUPLICATE,
        STATE_PERSISTED,
        STATE_RECEIVED,
        STATE_REJECTED,
        build_integrity_report,
        new_lifecycle_entry,
    )

    manifest = dict(upload_manifest or {})
    meta = dict(request_metadata or {})
    session_id = str(manifest.get("upload_session_id") or meta.get("upload_session_id") or "")
    if manifest.get("client_selected_count") and not expected_file_count:
        expected_file_count = int(manifest.get("client_selected_count") or 0)
    if manifest.get("filenames") and not expected_file_names:
        expected_file_names = [str(x) for x in manifest.get("filenames") or [] if str(x).strip()]

    prior_ui = dict(record.get("upload_integrity") or {})
    prior_lifecycle = list(prior_ui.get("file_lifecycle") or [])

    received_count = len(files)
    expected_count = int(expected_file_count or 0) or received_count
    expected_names = list(expected_file_names or [])

    batch_complete = manifest.get("batch_complete")
    if batch_complete is None:
        if manifest.get("batch_complete") is False:
            batch_complete = False
        elif prior_lifecycle and expected_count > received_count:
            batch_complete = False
        else:
            batch_complete = True
    else:
        batch_complete = bool(batch_complete)

    lifecycle: List[Dict[str, Any]] = []
    upload_started_at = _utc_now()
    custody_early = dict(record.get("upload_custody") or {})
    record["upload_custody"] = custody_early

    _safe_emit_intake_event(
        intake_id,
        "beta_upload_started",
        message=f"Upload batch for {intake_id}",
        metadata={
            "intake_id": intake_id,
            "file_count": received_count,
            "expected_file_count": expected_count,
            "batch_complete": batch_complete,
        },
        custody=custody_early,
    )

    for uf in files[:MAX_FILES_PER_REQUEST]:
        original_name = uf.filename or "upload.bin"
        entry = new_lifecycle_entry(
            original_name,
            state=STATE_RECEIVED,
            source_session_id=session_id or None,
            media_type=uf.content_type,
        )
        lifecycle.append(entry)
        try:
            safe_name = safe_upload_filename(original_name)
            try:
                _validate_extension(safe_name)
            except HTTPException as he:
                entry["state"] = STATE_REJECTED
                entry["reason_code"] = REASON_UNSUPPORTED_EXTENSION
                entry["reason_detail"] = str(he.detail)
                errors.append({"filename": original_name, "error": str(he.detail)})
                continue
            content = await uf.read()
            size = len(content)
            if size > MAX_FILE_BYTES:
                entry["state"] = STATE_REJECTED
                entry["reason_code"] = REASON_FILE_TOO_LARGE
                entry["reason_detail"] = "File too large (max 50MB)"
                errors.append({"filename": safe_name, "error": entry["reason_detail"]})
                continue
            if total_before + size > MAX_TOTAL_INTAKE_BYTES:
                entry["state"] = STATE_REJECTED
                entry["reason_code"] = REASON_TOTAL_SIZE_LIMIT
                entry["reason_detail"] = "Intake total size limit reached"
                errors.append({"filename": safe_name, "error": entry["reason_detail"]})
                continue
            dest = uploads_dir / safe_name
            was_duplicate = False
            duplicate_of_name: Optional[str] = None
            if dest.exists():
                was_duplicate = True
                duplicate_of_name = safe_name
                entry["state"] = STATE_DUPLICATE
                entry["lifecycle_state"] = STATE_DUPLICATE
                entry["reason_code"] = REASON_DUPLICATE_RENAMED
                entry["reason_detail"] = "Duplicate filename — stored under renamed path"
                entry["duplicate_of"] = duplicate_of_name
                stem = Path(safe_name).stem
                ext = Path(safe_name).suffix
                safe_name = f"{stem}_{uuid.uuid4().hex[:6]}{ext}"
                dest = uploads_dir / safe_name
            from .file_durability import write_upload_with_durability_markers

            write_upload_with_durability_markers(dest, content, intake_id=intake_id)
            total_before += size
            file_entry = {
                "name": safe_name,
                "original_name": original_name,
                "size": size,
                "ext": Path(safe_name).suffix.lower(),
                "uploaded_at_utc": _utc_now(),
            }
            record.setdefault("files", []).append(file_entry)
            saved.append(file_entry)
            entry["stored_name"] = safe_name
            entry["sanitized_filename"] = safe_name
            entry["size"] = size
            entry["size_bytes"] = size
            entry["extension"] = Path(safe_name).suffix.lower()
            if was_duplicate:
                entry["state"] = STATE_DUPLICATE
                entry["lifecycle_state"] = STATE_DUPLICATE
                entry["persisted_at"] = _utc_now()
            else:
                entry["state"] = STATE_PERSISTED
                entry["lifecycle_state"] = STATE_PERSISTED
                entry["persisted_at"] = _utc_now()
        except HTTPException as he:
            entry["state"] = STATE_REJECTED
            entry["reason_code"] = REASON_UNSUPPORTED_EXTENSION
            entry["reason_detail"] = str(he.detail)
            errors.append({"filename": original_name, "error": str(he.detail)})
        except Exception as exc:
            logger.warning("Founding beta file save failed: %s", exc)
            entry["state"] = STATE_REJECTED
            entry["reason_code"] = REASON_PERSIST_FAILED
            entry["reason_detail"] = "Could not save file"
            errors.append({"filename": original_name, "error": "Could not save file"})

    if not saved and errors:
        raise HTTPException(status_code=400, detail=errors[0].get("error", "Upload failed"))

    from .integrity import merge_batch_lifecycle

    merged_lifecycle = merge_batch_lifecycle(prior_lifecycle, lifecycle)
    cumulative_received = int(prior_ui.get("received_file_count") or 0) + received_count

    integrity = build_integrity_report(
        expected_file_count=expected_count,
        expected_file_names=expected_names
        or [f.get("original_name") or f.get("name") for f in record.get("files") or []],
        lifecycle=merged_lifecycle,
        received_file_count=cumulative_received,
        batch_complete=batch_complete,
    )

    record["file_count"] = cumulative_received
    record["total_bytes"] = total_before

    from .integrity import (
        client_ip_from_headers,
        detect_submission_method,
        summarize_user_agent,
    )
    from .transactions import (
        PHASE_AUDIT_WRITTEN,
        PHASE_FILES_PERSISTED,
        PHASE_HASH_VERIFIED,
        PHASE_INTEGRITY_FAILURE,
        PHASE_UPLOAD_RECEIVED,
        append_transaction_event,
    )

    custody = dict(record.get("upload_custody") or {})
    custody.update(
        {
            "source_ip": meta.get("source_ip")
            or client_ip_from_headers(
                x_forwarded_for=str(meta.get("x_forwarded_for") or ""),
                client_host=str(meta.get("client_host") or ""),
            ),
            "user_agent_summary": summarize_user_agent(
                str(meta.get("user_agent") or manifest.get("client_user_agent") or "")
            ),
            "upload_session_id": session_id,
            "submission_method": detect_submission_method(
                manifest,
                user_agent=str(meta.get("user_agent") or ""),
                has_resume_token=bool(manifest.get("resume_token_used")),
                has_magic_token=bool(token),
            ),
            "originating_route": str(manifest.get("route") or meta.get("route") or "/ui/intake"),
            "newest_upload_at_utc": upload_started_at,
            "client_manifest": manifest,
            "batch_complete": batch_complete,
            "batch_received_count": received_count,
            "cumulative_received_count": cumulative_received,
            "total_expected_count": expected_count,
        }
    )
    record["upload_custody"] = custody

    append_transaction_event(
        intake_id,
        PHASE_UPLOAD_RECEIVED,
        metadata={
            "expected_file_count": expected_count,
            "received_file_count": received_count,
            "upload_session_id": session_id,
        },
    )
    append_transaction_event(
        intake_id,
        PHASE_FILES_PERSISTED,
        metadata={"persisted_file_count": len(saved), "rejected": len(errors)},
    )

    durability: Dict[str, Any] = {}
    if saved:
        from .retention import assert_read_write_roots_match, require_upload_durability_verified

        assert_read_write_roots_match()
        durability = require_upload_durability_verified(
            intake_id,
            saved_files=list(record.get("files") or []),
            integrity=integrity,
        )
        if durability.get("integrity"):
            integrity = durability["integrity"]
        if durability.get("durability_verified"):
            append_transaction_event(
                intake_id,
                PHASE_HASH_VERIFIED,
                metadata={"verified_file_count": durability.get("verified_file_count")},
            )
            append_transaction_event(intake_id, PHASE_AUDIT_WRITTEN, metadata={"audit": True})
            from .evidence_registry import derive_evidence_registry_for_intake

            derive_evidence_registry_for_intake(intake_id, write=True)
        else:
            append_transaction_event(
                intake_id,
                PHASE_INTEGRITY_FAILURE,
                ok=False,
                metadata={"detail": durability.get("detail")},
            )

    custody["newest_upload_at_utc"] = _utc_now()
    record["upload_custody"] = custody
    _apply_custody_status(
        record,
        integrity,
        durability_ok=bool(durability.get("durability_verified", not saved)),
    )
    integrity = record["upload_integrity"]

    committed = bool(durability.get("durability_verified")) if saved else True
    _commit_intake_state(intake_id, record, integrity=integrity, committed=committed)

    if saved and durability.get("durability_verified"):
        from .forensic_reconcile import guard_disk_file_visibility

        for f in record.get("files") or []:
            name = str(f.get("name") or "")
            if name:
                guard_disk_file_visibility(intake_id, name, context="post_commit")

    logger.info(
        "Founding beta upload committed %s files=%s path=%s committed=%s",
        intake_id,
        record["file_count"],
        intake_json_path(intake_id),
        committed,
    )

    if integrity.get("integrity_mismatch"):
        emit_intake_event(
            "upload_integrity_mismatch",
            message=f"{intake_id} expected={integrity.get('expected_file_count')} verified={integrity.get('verified_file_count')}",
            metadata={
                "intake_id": intake_id,
                **{k: integrity.get(k) for k in (
                    "expected_file_count",
                    "received_file_count",
                    "persisted_file_count",
                    "verified_file_count",
                    "missing_files",
                    "reason_codes",
                )},
            },
        )
        logger.critical(
            "upload_integrity_mismatch intake=%s expected=%s received=%s persisted=%s verified=%s",
            intake_id,
            integrity.get("expected_file_count"),
            integrity.get("received_file_count"),
            integrity.get("persisted_file_count"),
            integrity.get("verified_file_count"),
        )

    ext_counts: Dict[str, int] = {}
    for f in record.get("files") or []:
        e = f.get("ext") or "unknown"
        ext_counts[e] = ext_counts.get(e, 0) + 1

    emit_intake_event(
        "beta_upload_completed",
        message=f"{len(saved)} file(s) on {intake_id}",
        metadata={
            "intake_id": intake_id,
            "extensions": list(ext_counts.keys()),
            "file_count": record["file_count"],
            "urgent": record.get("urgent"),
            "committed": committed,
            "lead_id": record.get("lead_id") or "",
        },
    )
    emit_intake_event(
        "upload_file_types",
        message=intake_id,
        metadata={"intake_id": intake_id, "extensions": ext_counts},
    )

    # Notify operator on every intake upload (CRITICAL for first-ever submission)
    if committed and saved:
        try:
            from services.alerts import alert_first_paperwork_submission

            alert_first_paperwork_submission(
                email=record.get("email") or "",
                name=record.get("company") or record.get("email") or intake_id,
                project_id=intake_id,
                upload_count=len(saved),
                file_types=list(ext_counts.keys()),
                source="founding-beta-upload",
                lead_id=record.get("lead_id") or "",
            )
        except Exception as exc:
            logger.warning("Operator paperwork alert skipped: %s", exc)

    # Acquisition funnel attribution: mark conversion when intake came from a lead
    _link_intake_to_lead(intake_id, record)
    if record.get("urgent"):
        emit_intake_event(
            "operator_review_needed",
            message=f"Deadline flagged on {intake_id}",
            metadata={"intake_id": intake_id, "deadline": record.get("deadline")},
        )

    if saved and committed:
        try:
            from .classification import classify_intake
            from .learning_hooks import record_intake_learning
            from .transactions import PHASE_CLASSIFICATION

            clf = classify_intake(intake_id)
            append_transaction_event(
                intake_id,
                PHASE_CLASSIFICATION,
                metadata={"primary_category": clf.get("primary_category")},
            )
            emit_intake_event(
                "intake_classified",
                message=intake_id,
                metadata={
                    "intake_id": intake_id,
                    "primary_category": clf.get("primary_category"),
                    "confidence_score": clf.get("confidence_score"),
                },
            )
            record_intake_learning(
                "intake_classified",
                intake_id=intake_id,
                extra={"primary_category": clf.get("primary_category")},
            )
            if clf.get("missing_items"):
                emit_intake_event(
                    "missing_documents_detected",
                    message=intake_id,
                    metadata={
                        "intake_id": intake_id,
                        "missing_items": clf.get("missing_items"),
                    },
                )
                record_intake_learning(
                    "missing_documents_detected",
                    intake_id=intake_id,
                )

            # Autonomous payment link dispatch — gated off by default per
            # docs/FIRST_SALE_OPERATOR_SOP.md (operator must review the intake
            # before any PayPal link goes to the customer). Opt in by setting
            # KYC_AUTO_PAYMENT_LINK=true in the environment.
            if os.getenv("KYC_AUTO_PAYMENT_LINK", "false").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            ):
                try:
                    from .auto_payment import auto_send_payment_link

                    auto_result = auto_send_payment_link(intake_id, clf)
                    emit_intake_event(
                        "auto_payment_link_dispatched",
                        message=intake_id,
                        metadata={
                            "intake_id": intake_id,
                            "product_id": auto_result.get("product_id"),
                            "email_sent": auto_result.get("email_sent") or auto_result.get("email_result", {}).get("sent"),
                            "skipped": auto_result.get("skipped"),
                            "reason": auto_result.get("reason"),
                            "auto_triggered": True,
                        },
                    )
                except Exception as exc:
                    logger.warning("Auto payment link dispatch skipped: %s", exc)
            else:
                emit_intake_event(
                    "auto_payment_link_gated_off",
                    message=intake_id,
                    metadata={
                        "intake_id": intake_id,
                        "reason": "KYC_AUTO_PAYMENT_LINK env flag is off (default)",
                    },
                )

        except Exception as exc:
            logger.warning("Founding beta classification skipped: %s", exc)

    link = _magic_link(intake_id, token)
    qr_bytes = _qr_png(link)
    import base64

    qr_b64 = base64.standard_b64encode(qr_bytes).decode("ascii")

    if saved and not durability.get("durability_verified"):
        raise HTTPException(
            status_code=500,
            detail="Your files could not be verified on secure storage. Please try again.",
            headers={"X-KYC-Error-Code": "upload_durability_failed"},
        )

    proof_gate: Dict[str, Any] = {}
    verified_n = int(
        durability.get("verified_file_count")
        or integrity.get("verified_file_count")
        or len(saved)
    )
    upload_integrity_for_gate = record.get("upload_integrity") or integrity
    if (
        saved
        and durability.get("durability_verified")
        and bool(upload_integrity_for_gate.get("integrity_ok"))
    ):
        from .proof_gate import require_upload_proof_gate

        proof_gate = require_upload_proof_gate(
            intake_id,
            saved_files=list(record.get("files") or []),
            verified_file_count=verified_n,
        )

    integrity = record.get("upload_integrity") or {}
    upload_integrity_ok = bool(integrity.get("integrity_ok"))
    failed_n = int(integrity.get("failed_file_count") or 0)
    customer_may_show_success = (
        upload_integrity_ok
        and int(integrity.get("verified_file_count") or 0)
        == int(integrity.get("expected_file_count") or 0)
        and failed_n == 0
        and bool(durability.get("durability_verified", not saved))
        and bool(proof_gate.get("proof_gate_passed", not saved))
    )

    return {
        "ok": True,
        "intake_id": intake_id,
        "token": token,
        "upload_url": link,
        "magic_link": link,
        "qr_png_base64": qr_b64,
        "files_saved": saved,
        "errors": errors,
        "file_count": record["file_count"],
        "expected_file_count": int(integrity.get("expected_file_count") or expected_count),
        "received_file_count": int(integrity.get("received_file_count") or received_count),
        "persisted_file_count": int(integrity.get("persisted_file_count") or len(saved)),
        "verified_file_count": int(
            durability.get("verified_file_count")
            or integrity.get("verified_file_count")
            or len(saved)
        ),
        "rejected_file_count": int(integrity.get("rejected_file_count") or 0),
        "duplicate_file_count": int(integrity.get("duplicate_file_count") or 0),
        "failed_file_count": failed_n,
        "upload_integrity_ok": upload_integrity_ok,
        "integrity_mismatch": bool(integrity.get("integrity_mismatch")),
        "custody_status": record.get("custody_status") or integrity.get("custody_status"),
        "customer_may_show_success": customer_may_show_success,
        "proof_gate_passed": bool(proof_gate.get("proof_gate_passed", not saved)),
        "data_root": proof_gate.get("data_root"),
        "write_path": proof_gate.get("write_path"),
        "live_scan_confirmed": proof_gate.get("live_scan_confirmed"),
        "queue_or_archive_visible": proof_gate.get("queue_or_archive_visible"),
        "retention_visible": proof_gate.get("retention_visible"),
        "file_access_verified": proof_gate.get("file_access_verified"),
        "missing_files": list(integrity.get("missing_files") or []),
        "rejected_files": list(integrity.get("rejected_files") or []),
        "file_lifecycle_table": list(integrity.get("file_lifecycle_table") or []),
        "retry_recommendation": integrity.get("retry_recommendation"),
        "durable_receipt_created": bool(durability.get("durable_receipt_created")),
        "durability_verified": bool(durability.get("durability_verified", not saved)),
        "status": record["status"],
        "review_status": record.get("review_status"),
        "upload_custody": record.get("upload_custody"),
    }


def get_operator_intake_dashboard(limit: int = 20) -> Dict[str, Any]:
    """Lightweight operator panel — filesystem + index, same paths as upload."""
    from .storage import intake_diagnostics, is_pending_review, sync_index_from_filesystem

    sync_index_from_filesystem(max_rows=max(limit, 100))
    intake_ids = all_intake_ids(limit=max(limit, 80))
    pending_ids: List[str] = []
    doc_types: Dict[str, int] = {}
    urgent_ids: List[str] = []
    uploads_received = count_upload_files()

    for intake_id in intake_ids[: max(limit, 30)]:
        try:
            rec = load_intake_record(intake_id, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        if is_pending_review(rec.get("review_status")):
            pending_ids.append(intake_id)
        if rec.get("urgent"):
            urgent_ids.append(intake_id)
        for f in rec.get("files") or []:
            ext = f.get("ext") or "unknown"
            doc_types[ext] = doc_types.get(ext, 0) + 1

    newest = intake_ids[:limit]
    recent_rows: List[Dict[str, Any]] = []

    links = []
    for iid in newest[:8]:
        try:
            rec = load_intake_record(iid, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        recent_rows.append(
            {
                "intake_id": iid,
                "created_at_utc": rec.get("created_at_utc"),
                "status": rec.get("review_status"),
                "company": rec.get("company"),
                "file_count": rec.get("file_count", 0),
            }
        )
        tok = make_founding_beta_token(str(iid))
        links.append(
            {
                "intake_id": iid,
                "magic_link": _magic_link(str(iid), tok),
                "created_at_utc": rec.get("created_at_utc"),
                "urgent": rec.get("urgent"),
                "file_count": rec.get("file_count", 0),
            }
        )

    diag = intake_diagnostics()
    return {
        "ok": True,
        "uploads_received": uploads_received,
        "pending_review_count": len(pending_ids),
        "newest_intake_ids": newest[:10],
        "document_type_counts": doc_types,
        "urgent_intake_ids": urgent_ids[:10],
        "intake_links": links,
        "recent": recent_rows[:limit],
        "diagnostics": diag,
    }


def qr_png_for_intake(intake_id: str, token: str) -> Tuple[bytes, str]:
    validate_intake_access(intake_id, token)
    link = _magic_link(intake_id, token)
    return _qr_png(link), link


def _latest_intake_custody_signal() -> Dict[str, Any]:
    """Most recent intake custody — drives COTE upload node severity."""
    from .integrity import STATUS_INTEGRITY_FAILURE, STATUS_PARTIAL_UPLOAD, STATUS_REJECTED_FILES
    from .integrity import STATUS_VERIFIED_COMPLETE
    from .retention import audit_hashes_match
    from .storage import all_intake_ids, list_intake_ids, load_intake_record

    ids = list_intake_ids(limit=5) or all_intake_ids(limit=5)
    for iid in ids:
        try:
            rec = load_intake_record(iid, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        if not (rec.get("files") or rec.get("file_count")):
            continue
        ui = rec.get("upload_integrity") or {}
        status = str(rec.get("custody_status") or ui.get("custody_status") or "").lower()
        hash_ok = audit_hashes_match(iid)
        if not hash_ok:
            status = STATUS_INTEGRITY_FAILURE
        return {
            "latest_intake_id": iid,
            "latest_custody_status": status,
            "latest_integrity_mismatch": bool(ui.get("integrity_mismatch")) or not hash_ok,
        }
    return {
        "latest_intake_id": None,
        "latest_custody_status": "",
        "latest_integrity_mismatch": False,
    }


def _upload_node_severity(custody_status: str) -> str:
    """green | amber | red — no fake healthy on mismatch."""
    from .integrity import (
        STATUS_INTEGRITY_FAILURE,
        STATUS_PARTIAL_UPLOAD,
        STATUS_REJECTED_FILES,
        STATUS_VERIFIED_COMPLETE,
    )

    s = (custody_status or "").lower()
    if s == STATUS_INTEGRITY_FAILURE:
        return "red"
    if s in (STATUS_PARTIAL_UPLOAD, STATUS_REJECTED_FILES):
        return "amber"
    if s == STATUS_VERIFIED_COMPLETE:
        return "green"
    return "amber"


def intake_flow_metrics(*, lightweight: bool = False) -> Dict[str, Any]:
    """Signals for COTE upload_pipeline node."""
    from .integrity import STATUS_INTEGRITY_FAILURE, STATUS_PARTIAL_UPLOAD, STATUS_REJECTED_FILES

    dash = get_operator_intake_dashboard(limit=30)
    pending = dash.get("pending_review_count", 0)
    uploads = dash.get("uploads_received", 0)
    urgent = len(dash.get("urgent_intake_ids") or [])
    integrity_mismatch_count = 0
    qm: Dict[str, Any] = {}
    try:
        from .queue import queue_flow_metrics

        qm = queue_flow_metrics()
    except Exception:
        qm = {}
    pending = max(pending, int(qm.get("queue_depth") or 0))
    urgent = max(urgent, int(qm.get("urgent_count") or 0))
    integrity_mismatch_count = int(qm.get("integrity_mismatch_count") or 0)
    latest = _latest_intake_custody_signal()
    custody_status = str(latest.get("latest_custody_status") or "")
    forensic_proof: Dict[str, Any] = {}
    try:
        if lightweight:
            from .forensic_reconcile import load_integrity_incidents, summarize_integrity_proof_for_cote

            forensic_proof = summarize_integrity_proof_for_cote()
            incident_count = int(forensic_proof.get("integrity_incident_count") or 0)
        else:
            from .forensic_reconcile import build_integrity_proof, load_integrity_incidents

            forensic_proof = build_integrity_proof(limit=200)
            incident_count = len(load_integrity_incidents(tail=100))
        if not forensic_proof.get("ok") or incident_count > 0:
            integrity_mismatch_count = max(
                integrity_mismatch_count,
                int(forensic_proof.get("missing_files") or 0)
                + int(forensic_proof.get("orphaned_files") or 0)
                + int(forensic_proof.get("corrupt_files") or 0)
                + int(forensic_proof.get("unindexed_files") or 0)
                + int(forensic_proof.get("ghost_intake_count") or 0)
                + incident_count,
            )
    except Exception:
        forensic_proof = {}
    if latest.get("latest_integrity_mismatch"):
        integrity_mismatch_count = max(integrity_mismatch_count, 1)
    upload_severity = _upload_node_severity(custody_status)
    if forensic_proof and not forensic_proof.get("ok"):
        upload_severity = "red"
    activity = _clamp(
        max(uploads / 10.0 + (1.0 if pending else 0.0) * 0.2, float(qm.get("activity") or 0))
    )
    pressure = _clamp(max(pending / 5.0 + urgent / 3.0, float(qm.get("pressure") or 0)))
    if integrity_mismatch_count or upload_severity in ("amber", "red"):
        pressure = _clamp(max(pressure, 0.58 + integrity_mismatch_count * 0.08))
        urgent = max(urgent, integrity_mismatch_count)
    if upload_severity == "red":
        pressure = _clamp(max(pressure, 0.72))
    health = _clamp(0.65 + activity * 0.25 - pressure * 0.2)
    if upload_severity == "green" and custody_status:
        health = _clamp(max(health, 0.78))
    elif upload_severity == "red":
        health = _clamp(min(health, 0.38))
    elif upload_severity == "amber":
        health = _clamp(min(health, 0.58))
    return {
        "uploads_active": uploads > 0,
        "pending_review": pending,
        "urgent_count": urgent,
        "integrity_mismatch_count": integrity_mismatch_count,
        "activity": activity,
        "pressure": pressure,
        "health": health,
        "failed_recent": integrity_mismatch_count > 0
        or upload_severity == "red"
        or custody_status in (STATUS_PARTIAL_UPLOAD, STATUS_INTEGRITY_FAILURE, STATUS_REJECTED_FILES),
        "queue_depth": int(qm.get("queue_depth") or pending),
        "uploads_per_hour": float(qm.get("uploads_per_hour") or 0),
        "glow_intensity": float(qm.get("glow_intensity") or activity),
        "backlog_pressure": bool(qm.get("backlog_pressure")),
        "latest_intake_id": latest.get("latest_intake_id"),
        "latest_custody_status": custody_status,
        "upload_node_severity": upload_severity,
        "forensic_proof": forensic_proof,
        "forensic_proof_ok": bool(forensic_proof.get("ok", True)),
    }


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

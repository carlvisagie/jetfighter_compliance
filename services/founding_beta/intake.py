"""Founding Beta paperwork intake — upload-first, no login wall."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile

from services.config import DATA
from services.production import safe_upload_filename
from services.public_url import get_public_base_url
from services.security import make_founding_beta_token, parse_founding_beta_token

from .telemetry import emit_beta_event

logger = logging.getLogger(__name__)

INTAKES_ROOT = DATA / "founding_beta" / "intakes"
INDEX_JSONL = DATA / "founding_beta" / "intakes_index.jsonl"
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
    if not intake_id.startswith("FB-") or ".." in intake_id or "/" in intake_id:
        raise HTTPException(status_code=400, detail="Invalid intake_id")
    return INTAKES_ROOT / intake_id


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
    path = _intake_dir(intake_id) / "intake.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Intake not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_intake(intake_id: str, data: Dict[str, Any]) -> None:
    data["updated_at_utc"] = _utc_now()
    path = _intake_dir(intake_id) / "intake.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_index(row: Dict[str, Any]) -> None:
    INDEX_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_intake_access(intake_id: str, token: str) -> Dict[str, Any]:
    try:
        info = parse_founding_beta_token(token)
    except ValueError as e:
        code = str(e)
        if code == "founding_beta_expired":
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
    INTAKES_ROOT.mkdir(parents=True, exist_ok=True)
    intake_id = f"FB-{uuid.uuid4().hex[:12]}"
    idir = _intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    (idir / "uploads").mkdir(exist_ok=True)
    urgent = bool((deadline or "").strip())
    record = {
        "intake_id": intake_id,
        "created_at_utc": _utc_now(),
        "updated_at_utc": _utc_now(),
        "status": "pending_review",
        "review_status": "pending_review",
        "company": (company or "").strip()[:200],
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
    _append_index(
        {
            "intake_id": intake_id,
            "created_at_utc": record["created_at_utc"],
            "status": "pending_review",
            "company": record["company"],
            "email": record["email"],
            "urgent": urgent,
            "file_count": 0,
        }
    )
    emit_beta_event(
        "intake_received",
        message=f"Intake {intake_id} created",
        metadata={"intake_id": intake_id, "urgent": urgent},
    )
    try:
        from .learning_hooks import record_founding_beta_learning

        record_founding_beta_learning("intake_received", intake_id=intake_id)
    except Exception:
        pass
    return record


def _magic_link(intake_id: str, token: str) -> str:
    base = get_public_base_url().rstrip("/")
    return f"{base}/ui/founding-beta?intake_id={intake_id}&token={token}"


def _qr_png(link: str) -> bytes:
    from services.customer_friction import generate_qr_png

    return generate_qr_png(link)


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
) -> Dict[str, Any]:
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

    uploads_dir = _intake_dir(intake_id) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    total_before = _intake_total_bytes(intake_id)
    saved: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    emit_beta_event(
        "beta_upload_started",
        message=f"Upload batch for {intake_id}",
        metadata={"intake_id": intake_id, "file_count": len(files)},
    )

    for uf in files[:MAX_FILES_PER_REQUEST]:
        try:
            safe_name = safe_upload_filename(uf.filename or "upload.bin")
            _validate_extension(safe_name)
            content = await uf.read()
            size = len(content)
            if size > MAX_FILE_BYTES:
                errors.append({"filename": safe_name, "error": "File too large (max 50MB)"})
                continue
            if total_before + size > MAX_TOTAL_INTAKE_BYTES:
                errors.append({"filename": safe_name, "error": "Intake total size limit reached"})
                continue
            dest = uploads_dir / safe_name
            if dest.exists():
                stem = Path(safe_name).stem
                ext = Path(safe_name).suffix
                safe_name = f"{stem}_{uuid.uuid4().hex[:6]}{ext}"
                dest = uploads_dir / safe_name
            dest.write_bytes(content)
            total_before += size
            entry = {
                "name": safe_name,
                "size": size,
                "ext": Path(safe_name).suffix.lower(),
                "uploaded_at_utc": _utc_now(),
            }
            record.setdefault("files", []).append(entry)
            saved.append(entry)
        except HTTPException as he:
            errors.append({"filename": uf.filename or "?", "error": he.detail})
        except Exception as exc:
            logger.warning("Founding beta file save failed: %s", exc)
            errors.append({"filename": uf.filename or "?", "error": "Could not save file"})

    if not saved and errors:
        raise HTTPException(status_code=400, detail=errors[0].get("error", "Upload failed"))

    record["file_count"] = len(record.get("files") or [])
    record["total_bytes"] = total_before
    record["status"] = "pending_review"
    _save_intake(intake_id, record)

    ext_counts: Dict[str, int] = {}
    for f in record.get("files") or []:
        e = f.get("ext") or "unknown"
        ext_counts[e] = ext_counts.get(e, 0) + 1

    emit_beta_event(
        "beta_upload_completed",
        message=f"{len(saved)} file(s) on {intake_id}",
        metadata={
            "intake_id": intake_id,
            "extensions": list(ext_counts.keys()),
            "file_count": record["file_count"],
            "urgent": record.get("urgent"),
        },
    )
    emit_beta_event(
        "upload_file_types",
        message=intake_id,
        metadata={"intake_id": intake_id, "extensions": ext_counts},
    )
    if record.get("urgent"):
        emit_beta_event(
            "operator_review_needed",
            message=f"Deadline flagged on {intake_id}",
            metadata={"intake_id": intake_id, "deadline": record.get("deadline")},
        )

    if saved:
        try:
            from .classification import classify_intake
            from .learning_hooks import record_founding_beta_learning

            clf = classify_intake(intake_id)
            emit_beta_event(
                "intake_classified",
                message=intake_id,
                metadata={
                    "intake_id": intake_id,
                    "primary_category": clf.get("primary_category"),
                    "confidence_score": clf.get("confidence_score"),
                },
            )
            record_founding_beta_learning(
                "intake_classified",
                intake_id=intake_id,
                extra={"primary_category": clf.get("primary_category")},
            )
            if clf.get("missing_items"):
                emit_beta_event(
                    "missing_documents_detected",
                    message=intake_id,
                    metadata={
                        "intake_id": intake_id,
                        "missing_items": clf.get("missing_items"),
                    },
                )
                record_founding_beta_learning(
                    "missing_documents_detected",
                    intake_id=intake_id,
                )
        except Exception as exc:
            logger.warning("Founding beta classification skipped: %s", exc)

    link = _magic_link(intake_id, token)
    qr_bytes = _qr_png(link)
    import base64

    qr_b64 = base64.standard_b64encode(qr_bytes).decode("ascii")

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
        "status": record["status"],
        "review_status": "pending_review",
    }


def get_operator_intake_dashboard(limit: int = 20) -> Dict[str, Any]:
    """Lightweight operator panel — index tail + pending counts."""
    from ..lazy_io import iter_jsonl_lines

    rows = list(iter_jsonl_lines(INDEX_JSONL, tail_lines=max(limit, 50)))
    rows.reverse()
    pending = [r for r in rows if r.get("status") == "pending_review"]
    newest = rows[:limit]
    doc_types: Dict[str, int] = {}
    urgent_ids: List[str] = []

    for intake_id in [r.get("intake_id") for r in newest[:15] if r.get("intake_id")]:
        try:
            rec = _load_intake(str(intake_id))
        except HTTPException:
            continue
        if rec.get("urgent"):
            urgent_ids.append(str(intake_id))
        for f in rec.get("files") or []:
            ext = f.get("ext") or "unknown"
            doc_types[ext] = doc_types.get(ext, 0) + 1

    uploads_received = sum(r.get("file_count", 0) for r in rows)
    if not uploads_received:
        for intake_id in [r.get("intake_id") for r in rows[:30] if r.get("intake_id")]:
            try:
                rec = _load_intake(str(intake_id))
                uploads_received += len(rec.get("files") or [])
            except HTTPException:
                pass

    links = []
    for r in newest[:8]:
        iid = r.get("intake_id")
        if not iid:
            continue
        tok = make_founding_beta_token(str(iid))
        links.append(
            {
                "intake_id": iid,
                "magic_link": _magic_link(str(iid), tok),
                "created_at_utc": r.get("created_at_utc"),
                "urgent": r.get("urgent"),
                "file_count": r.get("file_count", 0),
            }
        )

    return {
        "ok": True,
        "uploads_received": uploads_received,
        "pending_review_count": len(pending),
        "newest_intake_ids": [r.get("intake_id") for r in newest[:10] if r.get("intake_id")],
        "document_type_counts": doc_types,
        "urgent_intake_ids": urgent_ids[:10],
        "intake_links": links,
        "recent": newest[:limit],
    }


def qr_png_for_intake(intake_id: str, token: str) -> Tuple[bytes, str]:
    validate_intake_access(intake_id, token)
    link = _magic_link(intake_id, token)
    return _qr_png(link), link


def intake_flow_metrics() -> Dict[str, Any]:
    """Signals for COTE upload_pipeline node."""
    dash = get_operator_intake_dashboard(limit=30)
    pending = dash.get("pending_review_count", 0)
    uploads = dash.get("uploads_received", 0)
    urgent = len(dash.get("urgent_intake_ids") or [])
    qm: Dict[str, Any] = {}
    try:
        from .queue import queue_flow_metrics

        qm = queue_flow_metrics()
    except Exception:
        qm = {}
    pending = max(pending, int(qm.get("queue_depth") or 0))
    urgent = max(urgent, int(qm.get("urgent_count") or 0))
    activity = _clamp(
        max(uploads / 10.0 + (1.0 if pending else 0.0) * 0.2, float(qm.get("activity") or 0))
    )
    pressure = _clamp(max(pending / 5.0 + urgent / 3.0, float(qm.get("pressure") or 0)))
    health = _clamp(0.65 + activity * 0.25 - pressure * 0.2)
    return {
        "uploads_active": uploads > 0,
        "pending_review": pending,
        "urgent_count": urgent,
        "activity": activity,
        "pressure": pressure,
        "health": health,
        "failed_recent": False,
        "queue_depth": int(qm.get("queue_depth") or pending),
        "uploads_per_hour": float(qm.get("uploads_per_hour") or 0),
        "glow_intensity": float(qm.get("glow_intensity") or activity),
        "backlog_pressure": bool(qm.get("backlog_pressure")),
    }


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

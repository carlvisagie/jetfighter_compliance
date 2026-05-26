"""Pre-contact upload sessions — paperwork before name/email."""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile

from services.config import DATA, PROJECTS
from services.ledger import register_artifact
from services.production import safe_upload_filename
from services.public_url import get_public_base_url
from services.security import make_session_token, parse_session_token

logger = logging.getLogger(__name__)

SESSIONS_ROOT = DATA / "customer_sessions"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600
MAX_FILE_BYTES = 52_428_800
ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".csv",
        ".txt",
        ".zip",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(event_type: str, *, session_id: str = "", project_id: str = "", metadata: Optional[Dict] = None) -> None:
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "customer_session",
            event_type,
            project_id=project_id,
            message=session_id,
            metadata={"session_id": session_id, **(metadata or {})},
        )
    except Exception as e:
        logger.debug("Session telemetry skipped: %s", e)


def _session_dir(session_id: str) -> Path:
    if not session_id.startswith("CS-") or ".." in session_id or "/" in session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return SESSIONS_ROOT / session_id


def _load_session(session_id: str) -> Dict[str, Any]:
    path = _session_dir(session_id) / "session.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Session not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "session.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_manifest(session_id: str) -> Dict[str, Any]:
    path = _session_dir(session_id) / "pending_manifest.json"
    if not path.is_file():
        return {"files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(session_id: str, manifest: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "pending_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def validate_session_access(session_id: str, session_token: str) -> Dict[str, Any]:
    try:
        info = parse_session_token(session_token)
    except ValueError as e:
        code = str(e)
        if code == "session_expired":
            _emit("upload_first_abandoned", session_id=session_id, metadata={"reason": "expired"})
            raise HTTPException(status_code=401, detail="Session expired") from e
        raise HTTPException(status_code=401, detail="Invalid session token") from e
    if info.get("s") != session_id:
        raise HTTPException(status_code=403, detail="Token does not match session")
    sess = _load_session(session_id)
    expires = sess.get("expires_at", "")
    if expires:
        try:
            exp_dt = datetime.strptime(expires, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                _emit("upload_first_abandoned", session_id=session_id, metadata={"reason": "expired"})
                raise HTTPException(status_code=410, detail="Session expired")
        except ValueError:
            pass
    if sess.get("status") == "completed":
        raise HTTPException(status_code=409, detail="Session already completed")
    return sess


def _guess_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return "image"
    if ext in (".pdf",):
        return "document"
    if ext in (".doc", ".docx", ".txt"):
        return "document"
    if ext in (".xls", ".xlsx", ".csv"):
        return "spreadsheet"
    return "document"


def _validate_extension(safe_name: str) -> None:
    ext = Path(safe_name).suffix.lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed: {ext}. Use PDF, images, Office docs, CSV, or ZIP.",
        )


def start_session() -> Dict[str, str]:
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    session_id = f"CS-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=SESSION_MAX_AGE_SECONDS)
    sdir = _session_dir(session_id)
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "uploads").mkdir(exist_ok=True)
    data = {
        "session_id": session_id,
        "created_at": _utc_now(),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "active",
        "project_id": None,
        "upload_count": 0,
    }
    _save_session(session_id, data)
    _save_manifest(session_id, {"files": []})
    token = make_session_token(session_id)
    _emit("customer_session_started", session_id=session_id)
    return {"ok": True, "session_id": session_id, "session_token": token}


async def upload_to_session(session_id: str, session_token: str, file: UploadFile) -> Dict[str, Any]:
    validate_session_access(session_id, session_token)
    safe_name = safe_upload_filename(file.filename or "upload.bin")
    _validate_extension(safe_name)
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    _emit("pre_contact_upload_started", session_id=session_id, metadata={"filename": safe_name})

    stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest = _session_dir(session_id) / "uploads" / stored_name
    dest.write_bytes(content)

    manifest = _load_manifest(session_id)
    manifest["files"].append(
        {
            "safe_name": safe_name,
            "stored_name": stored_name,
            "size": len(content),
            "uploaded_at": _utc_now(),
            "media_type": _guess_media_type(safe_name),
        }
    )
    _save_manifest(session_id, manifest)

    sess = _load_session(session_id)
    sess["upload_count"] = len(manifest["files"])
    _save_session(session_id, sess)

    _emit(
        "pre_contact_upload_completed",
        session_id=session_id,
        metadata={"filename": safe_name, "count": sess["upload_count"]},
    )
    return {"ok": True, "filename": safe_name, "upload_count": sess["upload_count"]}


def complete_session(
    session_id: str,
    session_token: str,
    name: str,
    email: str,
    note: str = "",
) -> Dict[str, Any]:
    validate_session_access(session_id, session_token)
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not name or not email or "@" not in email:
        raise HTTPException(status_code=400, detail="name and valid email required")

    _emit("min_info_requested", session_id=session_id)
    manifest = _load_manifest(session_id)
    files: List[Dict[str, Any]] = manifest.get("files") or []
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one file before continuing")

    from services.projects import new_project
    from services.process import init_workflow, set_phase

    order_id = f"SESSION-{session_id[3:]}"
    skus = ["UPLOAD-FIRST"]
    meta = new_project(order_id, email, name, skus)
    project_id = meta["project_id"]
    try:
        init_workflow(project_id, skus)
        set_phase(project_id, "INTAKE")
    except Exception as e:
        logger.warning("Workflow init for session %s: %s", session_id, e)

    evidence_dir = PROJECTS / project_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    session_uploads = _session_dir(session_id) / "uploads"
    linked: List[str] = []

    for entry in files:
        src = session_uploads / entry["stored_name"]
        if not src.is_file():
            continue
        safe_name = entry["safe_name"]
        dest = evidence_dir / safe_name
        if dest.exists():
            dest = evidence_dir / f"{entry['stored_name']}"
        shutil.copy2(src, dest)
        media_type = entry.get("media_type") or _guess_media_type(safe_name)
        register_artifact(project_id, dest, media_type, email)
        linked.append(safe_name)
        try:
            from services.acquisition.forensics import safe_record_evidence

            safe_record_evidence(project_id, safe_name, media_type)
        except Exception:
            pass
        try:
            from services.evidence_intelligence import process_evidence_upload

            process_evidence_upload(
                project_id,
                dest,
                artifact_id="",
                sha256="",
                owner=email,
            )
        except Exception:
            pass

    if note.strip():
        comm = PROJECTS / project_id / "communications"
        comm.mkdir(parents=True, exist_ok=True)
        (comm / "session_note.json").write_text(
            json.dumps(
                {
                    "note": note.strip(),
                    "session_id": session_id,
                    "received_utc": _utc_now(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    _emit("min_info_completed", session_id=session_id, project_id=project_id)

    try:
        from services.memory.central_memory import safe_link_after_customer_session

        safe_link_after_customer_session(
            project_id,
            session_id,
            email,
            name,
            skus,
            file_count=len(linked),
            note=note.strip(),
        )
    except Exception as e:
        logger.warning("Memory link after session: %s", e)

    base = get_public_base_url()
    continuation_token = ""
    continuation_url = ""
    upload_url = ""
    qr_url = ""
    try:
        from services.customer_friction import get_or_issue_continuation

        cont = get_or_issue_continuation(project_id, email)
        continuation_token = cont["continuation_token"]
        continuation_url = cont["continuation_url"]
        upload_url = f"{base}/upload?project_id={project_id}&token={continuation_token}"
        qr_url = f"{base}/api/customer/qr.svg?data={continuation_url}"
    except Exception:
        from services.security import make_continuation_token

        continuation_token = make_continuation_token(project_id, email)
        continuation_url = f"{base}/ui/continue.html?token={continuation_token}"
        upload_url = f"{base}/upload?project_id={project_id}&token={continuation_token}"
        qr_url = f"{base}/api/customer/qr.svg?data={continuation_url}"

    _emit("workspace_created", session_id=session_id, project_id=project_id)
    _emit("continuation_created", session_id=session_id, project_id=project_id)
    _emit("qr_shown", session_id=session_id, project_id=project_id)

    sess = _load_session(session_id)
    sess["status"] = "completed"
    sess["project_id"] = project_id
    sess["completed_at"] = _utc_now()
    sess["customer"] = {"name": name, "email": email}
    _save_session(session_id, sess)

    try:
        from services.emails import send_email

        html = f"""
        <h2>Your secure workspace is ready</h2>
        <p>We received your paperwork and created your workspace.</p>
        <p><strong><a href="{upload_url}">Upload more paperwork</a></strong></p>
        <p>Continue anytime on any device (no password):<br>
        <a href="{continuation_url}">{continuation_url}</a></p>
        """
        send_email(email, "Your secure workspace — KeepYourContracts", html)
    except Exception as e:
        logger.warning("Session complete email failed: %s", e)

    return {
        "ok": True,
        "project_id": project_id,
        "continuation_url": continuation_url,
        "continuation_token": continuation_token,
        "upload_url": upload_url,
        "qr_url": qr_url,
        "files_linked": len(linked),
    }

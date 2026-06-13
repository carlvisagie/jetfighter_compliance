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

from .defensive_wiring import safe_write_json
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
        ".json",
        ".xml",
        ".md",
        ".log",
        ".yaml",
        ".yml",
        ".html",
        ".eml",
        ".msg",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(event_type: str, *, session_id: str = "", project_id: str = "", metadata: Optional[Dict] = None) -> None:
    try:
        from services.organism_observability.emit import organism_emit

        meta = {"session_id": session_id, **(metadata or {})}
        link = bool(project_id)
        entity_id = ""
        if project_id:
            try:
                from services.memory.central_memory import find_entity_id

                entity_id = find_entity_id(project_id=project_id) or ""
            except Exception:
                pass
        organism_emit(
            "customer_session",
            event_type,
            project_id=project_id,
            entity_id=entity_id,
            message=session_id,
            metadata=meta,
            link_timeline=link and bool(entity_id),
        )
    except Exception as e:
        logger.debug("Session telemetry skipped: %s", e)


def _session_timing_meta(session_id: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
    """Attach seconds_to_upload and first-interaction timing when available."""
    meta = dict(extra or {})
    try:
        sess = _load_session(session_id)
    except HTTPException:
        return meta
    created = sess.get("created_at")
    first_ix = sess.get("first_interaction_at")
    if created and first_ix:
        try:
            t0 = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(str(first_ix).replace("Z", "+00:00"))
            meta.setdefault("seconds_to_first_interaction", max(0, int((t1 - t0).total_seconds())))
        except (TypeError, ValueError):
            pass
    if created and sess.get("first_upload_at"):
        try:
            t0 = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            tu = datetime.fromisoformat(str(sess["first_upload_at"]).replace("Z", "+00:00"))
            meta.setdefault("seconds_to_upload", max(0, int((tu - t0).total_seconds())))
        except (TypeError, ValueError):
            pass
    return meta


def _mark_first_interaction(session_id: str) -> None:
    sess = _load_session(session_id)
    if not sess.get("first_interaction_at"):
        sess["first_interaction_at"] = _utc_now()
        _save_session(session_id, sess)


def _mark_first_upload(session_id: str) -> None:
    sess = _load_session(session_id)
    if not sess.get("first_upload_at"):
        sess["first_upload_at"] = _utc_now()
        _save_session(session_id, sess)


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
    """Save session with defensive framework."""
    path = _session_dir(session_id) / "session.json"
    safe_write_json(path, data, component="customer_session", context=f"session {session_id}", severity="critical")


def _load_manifest(session_id: str) -> Dict[str, Any]:
    path = _session_dir(session_id) / "pending_manifest.json"
    if not path.is_file():
        return {"files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(session_id: str, manifest: Dict[str, Any]) -> None:
    """Save manifest with defensive error telemetry."""
    path = _session_dir(session_id) / "pending_manifest.json"
    try:
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except OSError as e:
        # CRITICAL: Manifest write failed
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "customer_session",
                "manifest_write_failed",
                severity="critical",
                metadata={
                    "session_id": session_id,
                    "path": str(path),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise


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
            detail=f"File type not allowed: {ext}. Allowed formats: PDF, Word, Excel, ZIP, images, CSV, TXT, JSON, XML, MD, YAML, LOG, HTML, EML, MSG.",
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
    _emit("upload_page_view", session_id=session_id, metadata={"source": "session_start"})
    return {
        "ok": True,
        "session_id": session_id,
        "session_token": token,
        "redirect_ui": "/ui/intake",
        "deprecated_route": "/api/customer/session/start",
        "canonical_intake": True,
    }


async def upload_to_session(session_id: str, session_token: str, file: UploadFile) -> Dict[str, Any]:
    """Deprecated shim — all customer paperwork writes canonical durable intake only."""
    from services.durable_storage import require_intake_upload_allowed
    from services.intake.intake import process_upload

    require_intake_upload_allowed()
    validate_session_access(session_id, session_token)
    _mark_first_interaction(session_id)
    sess = _load_session(session_id)
    iid = str(sess.get("canonical_intake_id") or "")
    token = str(sess.get("canonical_intake_token") or "")
    email = str(sess.get("email") or "").strip()
    if not email and not iid:
        email = f"pending.{session_id.lower()}@upload.local"

    result = await process_upload(
        [file],
        intake_id=iid,
        token=token,
        email=email,
        phone=str(sess.get("phone") or ""),
        company=str(sess.get("company") or ""),
        context=str(sess.get("context") or ""),
        expected_file_count=1,
        expected_file_names=[file.filename or "upload.bin"],
        upload_manifest={
            "client_selected_count": 1,
            "filenames": [file.filename or "upload.bin"],
            "upload_session_id": session_id,
            "submission_method": "resume",
            "resume_token_used": True,
            "route": "/api/customer/session/upload",
        },
        request_metadata={
            "upload_session_id": session_id,
            "route": "/api/customer/session/upload",
        },
    )
    if not iid:
        sess["canonical_intake_id"] = result.get("intake_id")
        sess["canonical_intake_token"] = result.get("token")
        sess["upload_count"] = int(result.get("file_count") or 0)
        _save_session(session_id, sess)

    _emit(
        "pre_contact_upload_completed",
        session_id=session_id,
        metadata={"canonical_intake_id": result.get("intake_id"), "deprecated_shim": True},
    )
    logger.info(
        "session_upload_shim session=%s intake=%s (canonical intakes/)",
        session_id,
        result.get("intake_id"),
    )
    return {
        **result,
        "ok": bool(result.get("ok")),
        "session_id": session_id,
        "deprecated_route": "/api/customer/session/upload",
        "canonical_intake": True,
        "redirect_ui": "/ui/intake",
        "upload_count": int(result.get("file_count") or 0),
        "filename": (result.get("files_saved") or [{}])[0].get("name") if result.get("files_saved") else "",
    }


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
    sess = _load_session(session_id)
    iid = str(sess.get("canonical_intake_id") or "")
    if not iid:
        raise HTTPException(
            status_code=400,
            detail="Upload paperwork first. Use /ui/intake if this page did not redirect.",
        )

    from services.intake.intake import _load_intake, _save_intake

    rec = _load_intake(iid)
    if not (rec.get("files") or rec.get("file_count")):
        raise HTTPException(status_code=400, detail="Upload at least one file before continuing")

    rec["email"] = email
    if name:
        rec["company"] = name
    if note.strip():
        rec["context"] = ((rec.get("context") or "") + "\n" + note.strip()).strip()[:2000]
    _save_intake(iid, rec)
    sess["email"] = email
    sess["company"] = name
    _save_session(session_id, sess)

    token = str(sess.get("canonical_intake_token") or "")
    base = get_public_base_url()
    magic = f"{base}/ui/intake?intake_id={iid}&token={token}" if token else f"{base}/ui/intake"

    logger.info("session_complete_shim session=%s intake=%s (no shadow project)", session_id, iid)
    return {
        "ok": True,
        "intake_id": iid,
        "token": token,
        "magic_link": magic,
        "redirect_ui": "/ui/intake",
        "deprecated_route": "/api/customer/session/complete",
        "project_created": False,
        "message": "Paperwork on durable intake — operator review before project kickoff.",
    }

"""Operator-only intake document listing and secure file delivery."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException
from fastapi.responses import FileResponse

from .integrity import lifecycle_to_custody_row
from .storage import intake_dir, load_intake_record

_INTAKE_ID_RE = re.compile(r"^FB-[a-f0-9]{12}$", re.I)


def _validate_intake_id(intake_id: str) -> str:
    iid = (intake_id or "").strip()
    if not _INTAKE_ID_RE.match(iid):
        raise HTTPException(status_code=400, detail=f"Invalid intake_id: {iid}")
    return iid


def _validate_filename(filename: str) -> str:
    name = (filename or "").strip().replace("\\", "/")
    if not name or "/" in name or ".." in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


def _uploads_dir(intake_id: str) -> Path:
    iid = _validate_intake_id(intake_id)
    return (intake_dir(iid) / "uploads").resolve()


def resolve_intake_upload_path(intake_id: str, filename: str) -> Path:
    """Resolve a stored filename under intakes/{id}/uploads — rejects traversal."""
    fname = _validate_filename(filename)
    uploads = _uploads_dir(intake_id)
    target = (uploads / fname).resolve()
    if uploads not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return target


def _file_urls(intake_id: str, stored_name: str) -> Dict[str, str]:
    from urllib.parse import quote

    enc = quote(stored_name, safe="")
    base = f"/api/operator/intake/{intake_id}/files/{enc}"
    return {"view_url": f"{base}/view", "download_url": f"{base}/download"}


def _format_size(size_bytes: Optional[int]) -> str:
    if size_bytes is None or size_bytes < 0:
        return "—"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{round(size_bytes / (1024 * 1024), 2)} MB"


def _document_row(
    intake_id: str,
    *,
    stored_name: str,
    original_name: Optional[str] = None,
    extension: Optional[str] = None,
    media_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    status: str = "unknown",
    sha256: Optional[str] = None,
    access_error: Optional[str] = None,
) -> Dict[str, Any]:
    urls = _file_urls(intake_id, stored_name)
    ext = extension or Path(stored_name).suffix.lower()
    mt = media_type or mimetypes.guess_type(stored_name)[0] or "application/octet-stream"
    accessible = access_error is None
    return {
        "original_filename": original_name or stored_name,
        "stored_filename": stored_name,
        "extension": ext,
        "media_type": mt,
        "size_bytes": size_bytes,
        "size_human": _format_size(size_bytes),
        "status": status,
        "sha256": sha256,
        "sha256_short": (sha256 or "")[:12] or "—",
        "view_url": urls["view_url"] if accessible else None,
        "download_url": urls["download_url"] if accessible else None,
        "accessible": accessible,
        "access_error": access_error,
    }


def list_intake_files_for_operator(intake_id: str) -> Dict[str, Any]:
    """List all documents for an intake with operator view/download URLs."""
    iid = _validate_intake_id(intake_id)
    try:
        rec = load_intake_record(iid, persist_recovery=True)
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=404, detail=f"Intake not found: {iid}") from exc

    uploads = _uploads_dir(iid)
    on_disk: Dict[str, Path] = {}
    if uploads.is_dir():
        for p in sorted(uploads.iterdir()):
            if p.is_file():
                on_disk[p.name] = p

    lifecycle_by_stored: Dict[str, Dict[str, Any]] = {}
    ui = rec.get("upload_integrity") or {}
    lifecycle_table = list(ui.get("file_lifecycle_table") or [])
    if not lifecycle_table and ui.get("file_lifecycle"):
        lifecycle_table = [lifecycle_to_custody_row(e) for e in ui.get("file_lifecycle") or []]

    for row in lifecycle_table:
        stored = str(row.get("sanitized_filename") or row.get("stored_name") or "").strip()
        if stored:
            lifecycle_by_stored[stored] = row

    for f in rec.get("files") or []:
        stored = str(f.get("name") or f.get("stored_name") or "").strip()
        if stored and stored not in lifecycle_by_stored:
            lifecycle_by_stored[stored] = {
                "original_filename": f.get("original_name") or stored,
                "sanitized_filename": stored,
                "size_bytes": f.get("size"),
                "extension": f.get("ext"),
                "media_type": f.get("media_type"),
                "sha256": f.get("sha256"),
                "lifecycle_state": "verified" if stored in on_disk else "missing",
            }

    documents: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for stored, row in sorted(lifecycle_by_stored.items()):
        seen.add(stored)
        path = on_disk.get(stored)
        access_error = None
        size_bytes = row.get("size_bytes")
        if path and path.is_file():
            size_bytes = path.stat().st_size
        elif stored not in on_disk:
            access_error = (
                f"File '{stored}' is recorded for this intake but not found on durable storage "
                f"at {uploads / stored}. Operator auth is required; the file may have been removed or never persisted."
            )
        status = str(row.get("lifecycle_state") or row.get("state") or "unknown")
        documents.append(
            _document_row(
                iid,
                stored_name=stored,
                original_name=str(row.get("original_filename") or stored),
                extension=str(row.get("extension") or Path(stored).suffix.lower()),
                media_type=row.get("media_type"),
                size_bytes=int(size_bytes) if size_bytes is not None else None,
                status=status,
                sha256=row.get("sha256"),
                access_error=access_error,
            )
        )

    for stored, path in sorted(on_disk.items()):
        if stored in seen:
            continue
        documents.append(
            _document_row(
                iid,
                stored_name=stored,
                original_name=stored,
                size_bytes=path.stat().st_size,
                status="on_disk_unindexed",
                sha256=None,
            )
        )

    return {
        "ok": True,
        "intake_id": iid,
        "file_count": len(documents),
        "documents": documents,
    }


def serve_intake_file(
    intake_id: str,
    filename: str,
    *,
    mode: Literal["view", "download"],
) -> FileResponse:
    iid = _validate_intake_id(intake_id)
    fname = _validate_filename(filename)
    path = resolve_intake_upload_path(iid, fname)
    uploads = _uploads_dir(iid)

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "error": "file_not_on_disk",
                "message": (
                    f"Cannot {mode} '{fname}': file not found on durable storage at {path}. "
                    "Verify retention-check and forensic reconcile for this intake."
                ),
                "intake_id": iid,
                "filename": fname,
                "expected_path": str(path),
                "uploads_dir": str(uploads),
                "reason": "Operator-authenticated access only — file missing from intakes/{id}/uploads/",
            },
        )

    media_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    if mode == "download":
        return FileResponse(path, media_type=media_type, filename=fname)
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


def documents_for_queue_row(intake_id: str) -> List[Dict[str, Any]]:
    """Lightweight document list embedded in operator queue cards."""
    try:
        payload = list_intake_files_for_operator(intake_id)
        return list(payload.get("documents") or [])
    except HTTPException:
        return []
    except Exception:
        return []

"""Operator kickoff — copy canonical intake paperwork into a project after review."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

from services.config import PROJECTS
from services.ledger import register_artifact
from services.process import init_workflow, set_phase
from services.projects import new_project

from .storage import ensure_canonical_intake_dir, intake_json_path, load_intake_record
from .telemetry import emit_beta_event

logger = logging.getLogger(__name__)


def kickoff_project_from_intake(
    intake_id: str,
    *,
    operator_note: str = "",
    order_id: str = "",
) -> Dict[str, Any]:
    rec = load_intake_record(intake_id, persist_recovery=True)
    uploads = ensure_canonical_intake_dir(intake_id) / "uploads"
    if not uploads.is_dir() or not any(uploads.iterdir()):
        raise HTTPException(status_code=400, detail="Intake has no files on durable disk")

    email = (rec.get("email") or "").strip().lower()
    name = (rec.get("company") or rec.get("contact") or email.split("@")[0] or "Client").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Intake missing valid email for kickoff")

    oid = (order_id or f"FB-{intake_id[3:12]}").strip()[:80]
    meta = new_project(oid, email, name, ["UPLOAD-FIRST"])
    project_id = meta["project_id"]
    try:
        init_workflow(project_id, ["UPLOAD-FIRST"])
        set_phase(project_id, "INTAKE")
    except Exception as exc:
        logger.warning("Workflow init for intake kickoff %s: %s", intake_id, exc)

    evidence_dir = PROJECTS / project_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    linked: List[str] = []

    for src in sorted(uploads.iterdir()):
        if not src.is_file():
            continue
        dest = evidence_dir / src.name
        if dest.exists():
            dest = evidence_dir / f"{src.stem}_from_intake{src.suffix}"
        shutil.copy2(src, dest)
        register_artifact(project_id, dest, _guess_media_type(src.name), email)
        linked.append(src.name)
        try:
            from services.acquisition.forensics import safe_record_evidence

            safe_record_evidence(project_id, src.name, _guess_media_type(src.name))
        except Exception:
            pass

    comm = PROJECTS / project_id / "communications"
    comm.mkdir(parents=True, exist_ok=True)
    intake_meta = {
        "company": rec.get("company") or "",
        "contact": name,
        "phone": rec.get("phone") or "",
        "notes": rec.get("context") or "",
        "canonical_intake_id": intake_id,
        "kickoff_from_intake": True,
    }
    if operator_note:
        intake_meta["operator_note"] = operator_note.strip()[:1000]
    (comm / "intake.json").write_text(json.dumps(intake_meta, indent=2), encoding="utf-8")

    meta_path = PROJECTS / project_id / "meta.json"
    if meta_path.is_file():
        try:
            pm = json.loads(meta_path.read_text(encoding="utf-8"))
            pm["canonical_intake_id"] = intake_id
            meta_path.write_text(json.dumps(pm, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    rec["review_status"] = "approved"
    rec["status"] = "approved"
    rec["project_id"] = project_id
    if operator_note:
        rec["operator_note"] = operator_note.strip()[:1000]
    from .intake import _save_intake

    _save_intake(intake_id, rec)

    emit_beta_event(
        "intake_kickoff_project",
        message=f"{intake_id} → {project_id}",
        metadata={
            "intake_id": intake_id,
            "project_id": project_id,
            "files_linked": len(linked),
        },
    )

    return {
        "ok": True,
        "intake_id": intake_id,
        "project_id": project_id,
        "files_linked": linked,
        "intake_json_path": str(intake_json_path(intake_id)),
    }


def _guess_media_type(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext in (".png", ".jpg", ".jpeg"):
        return f"image/{ext.lstrip('.')}"
    return "application/octet-stream"

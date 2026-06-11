"""Operator kickoff — copy canonical intake paperwork into a project after review."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

from services import config as _config
from services.ledger import register_artifact
from services.process import init_workflow, set_phase
from services.projects import new_project

from .storage import ensure_canonical_intake_dir, intake_json_path, load_intake_record
from .telemetry import emit_intake_event

logger = logging.getLogger(__name__)


def _run_post_kickoff_intelligence(project_id: str, intake_id: str) -> None:
    """
    Run Evidence Intelligence and Cognition after project kickoff.
    
    This ensures both systems operate on the correct projects/{project_id}/
    directory structure with properly linked evidence files.
    
    Runs non-blocking to avoid delaying kickoff response.
    """
    # Organism event: Intelligence processing started
    try:
        from services.memory.organism_integration import safe_write_after_workflow
        safe_write_after_workflow(
            project_id,
            step_id="post_kickoff_intelligence_started",
            phase="INTELLIGENCE",
            metadata={
                "intake_id": intake_id,
                "stage": "evidence_intelligence",
            }
        )
    except Exception:
        pass
    
    # Run Evidence Intelligence
    ei_success = False
    ei_files_processed = 0
    try:
        from services.evidence_intelligence import process_evidence_upload
        evidence_dir = _config.PROJECTS / project_id / "evidence"
        if evidence_dir.is_dir():
            evidence_files = [f for f in evidence_dir.iterdir() if f.is_file()]
            if evidence_files:
                logger.info(
                    f"Post-kickoff Evidence Intelligence for {project_id}: "
                    f"{len(evidence_files)} files"
                )
                for evidence_file in evidence_files:
                    try:
                        process_evidence_upload(project_id, evidence_file)
                        ei_files_processed += 1
                    except Exception as ei_exc:
                        logger.warning(
                            f"Evidence Intelligence failed for {project_id}/{evidence_file.name}: {ei_exc}"
                        )
                ei_success = True
    except Exception as ei_outer:
        logger.warning(
            f"Post-kickoff Evidence Intelligence dispatch failed for {project_id}: {ei_outer}"
        )
    
    # Organism event: Evidence Intelligence completed
    try:
        from services.memory.organism_integration import safe_write_after_workflow
        safe_write_after_workflow(
            project_id,
            step_id="evidence_intelligence_completed",
            phase="INTELLIGENCE",
            metadata={
                "intake_id": intake_id,
                "success": ei_success,
                "files_processed": ei_files_processed,
            }
        )
    except Exception:
        pass
    
    # Run Cognition
    cognition_success = False
    try:
        from services.cognition.storage import run_cognition_safely
        logger.info(f"Post-kickoff Cognition for {project_id}")
        result = run_cognition_safely(project_id)
        cognition_success = (result.get("status") == "success")
    except Exception as cog_exc:
        logger.warning(
            f"Post-kickoff Cognition failed for {project_id}: {cog_exc}"
        )
    
    # Organism event: Cognition completed
    try:
        from services.memory.organism_integration import safe_write_after_workflow
        safe_write_after_workflow(
            project_id,
            step_id="cognition_completed",
            phase="INTELLIGENCE",
            metadata={
                "intake_id": intake_id,
                "success": cognition_success,
            }
        )
    except Exception:
        pass
    
    # Organism event: Intelligence processing completed
    try:
        from services.memory.organism_integration import safe_write_after_workflow
        safe_write_after_workflow(
            project_id,
            step_id="post_kickoff_intelligence_completed",
            phase="INTELLIGENCE",
            metadata={
                "intake_id": intake_id,
                "evidence_intelligence_success": ei_success,
                "evidence_intelligence_files": ei_files_processed,
                "cognition_success": cognition_success,
            }
        )
    except Exception:
        pass
    
    emit_intake_event(
        "post_kickoff_intelligence_completed",
        message=f"Intelligence processing completed for {project_id}",
        metadata={
            "project_id": project_id,
            "intake_id": intake_id,
            "evidence_intelligence_success": ei_success,
            "cognition_success": cognition_success,
        },
    )


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

    # Revenue gate: require explicit payment confirmation before delivering service.
    # Operator must call confirm_payment_received first, or pass override_payment_check=True
    # with an explicit operator note explaining why (e.g. PO, wire, free trial).
    payment = rec.get("payment") or {}
    payment_confirmed = bool(payment.get("payment_received_at_utc"))
    if not payment_confirmed and not operator_note.startswith("PAYMENT_OVERRIDE:"):
        raise HTTPException(
            status_code=402,
            detail=(
                "Payment not yet confirmed for this intake. "
                "Call confirm_payment_received first, or prefix operator_note with "
                "'PAYMENT_OVERRIDE: <reason>' to acknowledge delivering without confirmed payment."
            ),
        )

    oid = (order_id or f"FB-{intake_id[3:12]}").strip()[:80]
    meta = new_project(oid, email, name, ["UPLOAD-FIRST"])
    project_id = meta["project_id"]
    try:
        init_workflow(project_id, ["UPLOAD-FIRST"])
        set_phase(project_id, "INTAKE")
    except Exception as exc:
        logger.warning("Workflow init for intake kickoff %s: %s", intake_id, exc)

    evidence_dir = _config.PROJECTS / project_id / "evidence"
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

    comm = _config.PROJECTS / project_id / "communications"
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

    meta_path = _config.PROJECTS / project_id / "meta.json"
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

    emit_intake_event(
        "intake_kickoff_project",
        message=f"{intake_id} → {project_id}",
        metadata={
            "intake_id": intake_id,
            "project_id": project_id,
            "files_linked": len(linked),
        },
    )
    
    # Post-kickoff intelligence trigger
    # Run Evidence Intelligence and Cognition on the newly created project
    _run_post_kickoff_intelligence(project_id, intake_id)

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

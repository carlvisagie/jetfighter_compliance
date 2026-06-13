"""PATCH 13A-5B: Project Deliverables Workbench.

Operator-controlled viewing, approval, and delivery of final customer products.
Builds on project_observability to provide deliverable-focused state.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .project_observability import (
from services.defensive_wiring import safe_write_text, safe_write_json
    get_project_observability,
    _read_json_safe,
    _read_jsonl_safe,
    _projects_root,
)

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _deliverables_state_path(project_id: str) -> Path:
    """Path to deliverables state JSON for a project."""
    return _projects_root() / project_id / "deliverables_state.json"


def _load_deliverables_state(project_id: str) -> Dict[str, Any]:
    """Load deliverables state from disk."""
    path = _deliverables_state_path(project_id)
    return _read_json_safe(path)


def _save_deliverables_state(project_id: str, state: Dict[str, Any]) -> None:
    """Save deliverables state to disk."""
    path = _deliverables_state_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write_json(

        path,

        state,

        component="deliverables",

        context="deliverable generation"

    )


def _get_generated_documents(project_id: str) -> List[Dict[str, Any]]:
    """Get list of generated documents for a project."""
    project_root = _projects_root() / project_id
    cognition_dir = project_root / "cognition"
    evidence_dir = project_root / "evidence"
    
    documents: List[Dict[str, Any]] = []
    
    # Check cognition summary for generated documents
    summary = _read_json_safe(cognition_dir / "cognition_summary.json")
    if summary.get("generated_documents"):
        for doc in summary["generated_documents"]:
            documents.append({
                "name": doc.get("name") or doc.get("filename") or "Unknown",
                "type": doc.get("type") or "document",
                "path": doc.get("path") or "",
                "generated_utc": doc.get("generated_utc") or summary.get("completed_utc") or "",
            })
    
    # Check for generated documents directory
    gen_dir = evidence_dir / "generated_documents"
    if gen_dir.is_dir():
        for f in gen_dir.iterdir():
            if f.is_file() and f.suffix in (".pdf", ".md", ".docx", ".json"):
                documents.append({
                    "name": f.name,
                    "type": "generated",
                    "path": str(f.relative_to(project_root)),
                    "generated_utc": "",
                })
    
    return documents


def _compute_missing_stages(obs: Dict[str, Any]) -> List[str]:
    """Determine which stages are incomplete."""
    missing = []
    
    ei = obs.get("evidence_intelligence", {})
    if ei.get("status") not in ("COMPLETED", "PARTIAL"):
        missing.append("Evidence Intelligence")
    
    cog = obs.get("cognition", {})
    if cog.get("status") != "COMPLETED":
        missing.append("Cognition")
    
    val = obs.get("validation", {})
    if val.get("status") != "COMPLETED":
        missing.append("Validation")
    
    ch = obs.get("compliance_health", {})
    if not ch.get("assessment_present"):
        missing.append("Compliance Health")
    
    return missing


def _compute_operator_status(
    ready: bool,
    state: Dict[str, Any],
) -> str:
    """Compute operator-facing status."""
    if not ready:
        return "not_ready"
    
    if state.get("sent_at_utc"):
        return "sent"
    
    if state.get("approved_at_utc"):
        return "approved"
    
    return "ready_for_review"


def get_project_deliverables(project_id: str) -> Dict[str, Any]:
    """
    Build complete deliverables payload for operator workbench.
    
    Returns everything needed to inspect, approve, and deliver.
    """
    if not project_id:
        return {
            "ok": False,
            "error": "project_id required",
            "queried_at_utc": _utc_now(),
        }
    
    # Get full observability first
    obs = get_project_observability(project_id)
    if not obs.get("ok"):
        return obs
    
    # Load deliverables state
    state = _load_deliverables_state(project_id)
    
    # Compute readiness
    missing_stages = _compute_missing_stages(obs)
    ready = len(missing_stages) == 0
    
    # Get generated documents
    generated_documents = _get_generated_documents(project_id)
    
    # Compute operator status
    operator_status = _compute_operator_status(ready, state)
    
    # Build download links (relative paths)
    project_root = _projects_root() / project_id
    download_links = []
    
    # Cognition summary
    cog_summary = project_root / "cognition" / "cognition_summary.json"
    if cog_summary.is_file():
        download_links.append({
            "name": "Cognition Summary",
            "filename": "cognition_summary.json",
            "path": f"/api/operator/project/{project_id}/download/cognition/cognition_summary.json",
        })
    
    # Validation report
    val_report = project_root / "cognition" / "validation_report.json"
    if val_report.is_file():
        download_links.append({
            "name": "Validation Report",
            "filename": "validation_report.json",
            "path": f"/api/operator/project/{project_id}/download/cognition/validation_report.json",
        })
    
    # Next actions
    next_actions = project_root / "cognition" / "next_actions.json"
    if next_actions.is_file():
        download_links.append({
            "name": "Next Actions",
            "filename": "next_actions.json",
            "path": f"/api/operator/project/{project_id}/download/cognition/next_actions.json",
        })
    
    return {
        "ok": True,
        "project_id": project_id,
        "queried_at_utc": _utc_now(),
        "ready": ready,
        "missing_stages": missing_stages,
        "operator_status": operator_status,
        "approved_at_utc": state.get("approved_at_utc") or "",
        "approved_by": state.get("approved_by") or "",
        "sent_at_utc": state.get("sent_at_utc") or "",
        "sent_to": state.get("sent_to") or "",
        "observability": obs,
        "compliance_health": obs.get("compliance_health", {}),
        "validation": obs.get("validation", {}),
        "cognition": obs.get("cognition", {}),
        "evidence_intelligence": obs.get("evidence_intelligence", {}),
        "generated_documents": generated_documents,
        "download_links": download_links,
    }


def approve_deliverables(project_id: str, *, operator_id: str = "operator") -> Dict[str, Any]:
    """
    Operator approves deliverables as ready to send.
    
    Idempotent — re-approving returns existing approval.
    """
    if not project_id:
        return {"ok": False, "error": "project_id required"}
    
    # Check readiness first
    deliverables = get_project_deliverables(project_id)
    if not deliverables.get("ok"):
        return deliverables
    
    if not deliverables.get("ready"):
        return {
            "ok": False,
            "error": "Cannot approve — deliverables not ready",
            "missing_stages": deliverables.get("missing_stages", []),
        }
    
    # Load existing state
    state = _load_deliverables_state(project_id)
    
    # Idempotent — return existing if already approved
    if state.get("approved_at_utc"):
        return {
            "ok": True,
            "project_id": project_id,
            "action": "approve",
            "idempotent_return": True,
            "approved_at_utc": state["approved_at_utc"],
            "approved_by": state.get("approved_by", ""),
            "operator_status": "approved" if not state.get("sent_at_utc") else "sent",
        }
    
    # Record approval
    now = _utc_now()
    state["approved_at_utc"] = now
    state["approved_by"] = operator_id
    _save_deliverables_state(project_id, state)
    
    # Emit timeline event
    try:
        from services.intake.telemetry import emit_lifecycle_event
        emit_lifecycle_event(
            "deliverables_approved",
            message=f"Deliverables approved for {project_id}",
            metadata={
                "project_id": project_id,
                "approved_by": operator_id,
                "approved_at_utc": now,
            },
        )
    except Exception:
        pass
    
    return {
        "ok": True,
        "project_id": project_id,
        "action": "approve",
        "approved_at_utc": now,
        "approved_by": operator_id,
        "operator_status": "approved",
    }


def send_deliverables(
    project_id: str,
    *,
    recipient_email: str = "",
    operator_id: str = "operator",
) -> Dict[str, Any]:
    """
    Mark deliverables as sent to customer.
    
    Does NOT actually send email — that's a separate communications action.
    This records the delivery state for tracking.
    
    Requires prior approval.
    """
    if not project_id:
        return {"ok": False, "error": "project_id required"}
    
    # Load existing state
    state = _load_deliverables_state(project_id)
    
    # Must be approved first
    if not state.get("approved_at_utc"):
        return {
            "ok": False,
            "error": "Cannot send — deliverables not yet approved",
            "operator_status": "not_ready" if not state else "ready_for_review",
        }
    
    # Idempotent — return existing if already sent
    if state.get("sent_at_utc"):
        return {
            "ok": True,
            "project_id": project_id,
            "action": "send",
            "idempotent_return": True,
            "sent_at_utc": state["sent_at_utc"],
            "sent_to": state.get("sent_to", ""),
            "operator_status": "sent",
        }
    
    # Resolve recipient email if not provided
    if not recipient_email:
        # Try to get from project/intake
        deliverables = get_project_deliverables(project_id)
        kickoff = deliverables.get("observability", {}).get("kickoff", {})
        # Try to load from intake
        intake_id = kickoff.get("canonical_intake_id", "")
        if intake_id:
            try:
                from services.intake.storage import load_intake_record
                intake = load_intake_record(intake_id, persist_recovery=False)
                recipient_email = intake.get("email", "")
            except Exception:
                pass
    
    # Record send
    now = _utc_now()
    state["sent_at_utc"] = now
    state["sent_to"] = recipient_email
    state["sent_by"] = operator_id
    _save_deliverables_state(project_id, state)
    
    # Emit timeline event
    try:
        from services.intake.telemetry import emit_lifecycle_event
        emit_lifecycle_event(
            "deliverables_sent",
            message=f"Deliverables sent for {project_id}",
            metadata={
                "project_id": project_id,
                "sent_to": recipient_email,
                "sent_by": operator_id,
                "sent_at_utc": now,
            },
        )
    except Exception:
        pass
    
    return {
        "ok": True,
        "project_id": project_id,
        "action": "send",
        "sent_at_utc": now,
        "sent_to": recipient_email,
        "operator_status": "sent",
    }

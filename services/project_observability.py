"""PATCH 13A-4D: Project Observability Foundation.

Single-endpoint visibility into all project state:
- Project metadata and kickoff state
- Evidence Intelligence processing state
- Cognition processing state
- Validation state
- Compliance Health assessment
- Timeline events

Enables operators to answer "What happened to this customer?" via API
without SSH, filesystem inspection, or log scraping.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json_safe(path: Path) -> Dict[str, Any]:
    """Read JSON file, return empty dict on any error."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_jsonl_safe(path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    """Read JSONL file, return empty list on any error."""
    if not path.is_file():
        return []
    try:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]
    except Exception:
        return []


def _projects_root() -> Path:
    from services.durable_storage import active_data_root
    return active_data_root() / "projects"


def _intakes_root() -> Path:
    from services.durable_storage import active_data_root
    return active_data_root() / "intakes"


def _get_kickoff_state(project_id: str) -> Dict[str, Any]:
    """Get project kickoff state from intake record if linked."""
    from services.intake.storage import load_intake_record
    
    project_root = _projects_root() / project_id
    meta = _read_json_safe(project_root / "meta.json")
    intake_meta = _read_json_safe(project_root / "communications" / "intake.json")
    
    # Get intake_id from project metadata
    intake_id = meta.get("canonical_intake_id") or intake_meta.get("canonical_intake_id") or ""
    
    # If no intake link, check if project_id is an intake ID (FB- prefix)
    if not intake_id and project_id.startswith("FB-"):
        intake_id = project_id
    
    kickoff_state = {
        "project_id": project_id,
        "project_exists": project_root.is_dir(),
        "project_created_utc": meta.get("created_utc") or meta.get("created") or "",
        "project_status": meta.get("status") or "unknown",
        "canonical_intake_id": intake_id,
        "project_kickoff_completed": False,
        "project_kickoff_at_utc": "",
        "auto_kickoff_reason": "",
    }
    
    # Load intake record to get kickoff metadata
    if intake_id:
        try:
            intake_record = load_intake_record(intake_id, persist_recovery=False)
            kickoff_state["project_kickoff_completed"] = bool(intake_record.get("project_kickoff_completed"))
            kickoff_state["project_kickoff_at_utc"] = intake_record.get("project_kickoff_at_utc") or ""
            kickoff_state["auto_kickoff_reason"] = intake_record.get("auto_kickoff_reason") or ""
            kickoff_state["custody_status"] = intake_record.get("custody_status") or ""
        except Exception as e:
            logger.debug(f"Could not load intake record for {intake_id}: {e}")
    
    return kickoff_state


def _get_evidence_intelligence_state(project_id: str) -> Dict[str, Any]:
    """Get Evidence Intelligence processing state."""
    project_root = _projects_root() / project_id
    ei_dir = project_root / "evidence_intelligence"
    
    state = {
        "status": "NOT_STARTED",
        "ei_started_utc": "",
        "ei_completed_utc": "",
        "ei_total": 0,
        "ei_success_count": 0,
        "ei_failed_count": 0,
        "profile_exists": False,
        "gaps_count": 0,
        "review_items_count": 0,
        "entities_count": 0,
    }
    
    if not ei_dir.is_dir():
        return state
    
    # Load profile directly from file
    profile_path = ei_dir / "profile.json"
    if profile_path.is_file():
        profile = _read_json_safe(profile_path)
        if profile.get("document_inventory"):
            state["profile_exists"] = True
            state["ei_total"] = len(profile.get("document_inventory") or [])
            state["ei_completed_utc"] = profile.get("updated_utc") or ""
    
    # Load gaps
    gaps_path = ei_dir / "gaps.json"
    if gaps_path.is_file():
        gaps_data = _read_json_safe(gaps_path)
        state["gaps_count"] = len(gaps_data.get("gaps") or [])
    
    # Load review queue
    review_path = ei_dir / "review_queue.jsonl"
    review_items = _read_jsonl_safe(review_path)
    state["review_items_count"] = len(review_items)
    
    # Load entities
    entities_path = ei_dir / "entities.jsonl"
    entities = _read_jsonl_safe(entities_path)
    state["entities_count"] = len(entities)
    
    # Load classifications for timing
    classifications_path = ei_dir / "classifications.jsonl"
    classifications = _read_jsonl_safe(classifications_path)
    if classifications:
        state["ei_started_utc"] = classifications[0].get("recorded_utc") or ""
        state["ei_completed_utc"] = classifications[-1].get("recorded_utc") or state["ei_completed_utc"]
        
        # Count successes and failures
        for cls in classifications:
            if cls.get("status") == "error" or cls.get("error"):
                state["ei_failed_count"] += 1
            else:
                state["ei_success_count"] += 1
    
    # Determine status
    if state["ei_started_utc"] or state["profile_exists"]:
        if state["ei_failed_count"] > 0 and state["ei_success_count"] > 0:
            state["status"] = "PARTIAL"
        elif state["ei_failed_count"] > 0 and state["ei_success_count"] == 0:
            state["status"] = "FAILED"
        elif state["ei_success_count"] > 0 or state["profile_exists"]:
            state["status"] = "COMPLETED"
        else:
            state["status"] = "RUNNING"
    
    return state


def _get_cognition_state(project_id: str) -> Dict[str, Any]:
    """Get Cognition processing state."""
    project_root = _projects_root() / project_id
    cognition_dir = project_root / "cognition"
    
    state = {
        "status": "NOT_STARTED",
        "cognition_started_utc": "",
        "cognition_completed_utc": "",
        "cognition_summary_present": False,
        "validation_report_present": False,
        "generated_documents_count": 0,
        "next_actions_count": 0,
    }
    
    if not cognition_dir.is_dir():
        return state
    
    # Check cognition_summary.json
    summary_path = cognition_dir / "cognition_summary.json"
    if summary_path.is_file():
        summary = _read_json_safe(summary_path)
        state["cognition_summary_present"] = True
        state["cognition_started_utc"] = summary.get("started_utc") or ""
        state["cognition_completed_utc"] = summary.get("completed_utc") or summary.get("generated_utc") or ""
        state["generated_documents_count"] = len(summary.get("generated_documents") or [])
        state["status"] = "COMPLETED"
    
    # Check validation_report.json
    validation_path = cognition_dir / "validation_report.json"
    if validation_path.is_file():
        state["validation_report_present"] = True
    
    # Check next_actions.json
    next_actions_path = cognition_dir / "next_actions.json"
    if next_actions_path.is_file():
        next_actions = _read_json_safe(next_actions_path)
        if isinstance(next_actions, list):
            state["next_actions_count"] = len(next_actions)
        elif isinstance(next_actions, dict):
            state["next_actions_count"] = len(next_actions.get("actions") or next_actions.get("items") or [])
    
    # Check for events to determine start time if not in summary
    events_path = cognition_dir / "cognition_events.jsonl"
    if events_path.is_file() and not state["cognition_started_utc"]:
        events = _read_jsonl_safe(events_path)
        if events:
            state["cognition_started_utc"] = events[0].get("recorded_utc") or events[0].get("timestamp") or ""
            state["status"] = "RUNNING" if not state["cognition_summary_present"] else "COMPLETED"
    
    # Check for errors
    if state["status"] == "RUNNING":
        error_path = cognition_dir / "error.json"
        if error_path.is_file():
            state["status"] = "FAILED"
    
    return state


def _get_validation_state(project_id: str) -> Dict[str, Any]:
    """Get Validation processing state."""
    project_root = _projects_root() / project_id
    cognition_dir = project_root / "cognition"
    
    state = {
        "status": "NOT_STARTED",
        "validation_started_utc": "",
        "validation_completed_utc": "",
        "validation_report_present": False,
        "human_review_items_count": 0,
        "safety_warnings_count": 0,
        "confidence_score": None,
    }
    
    validation_path = cognition_dir / "validation_report.json"
    if not validation_path.is_file():
        return state
    
    validation = _read_json_safe(validation_path)
    if validation:
        state["validation_report_present"] = True
        state["validation_completed_utc"] = validation.get("generated_utc") or validation.get("completed_utc") or ""
        state["status"] = "COMPLETED"
        
        # Extract review items and warnings
        state["human_review_items_count"] = len(validation.get("human_review_items") or validation.get("review_items") or [])
        state["safety_warnings_count"] = len(validation.get("safety_warnings") or validation.get("warnings") or [])
        state["confidence_score"] = validation.get("confidence_score") or validation.get("overall_confidence")
    
    return state


def _get_compliance_health_state(project_id: str) -> Dict[str, Any]:
    """Get Compliance Health assessment state."""
    from services.compliance_health.assessment import get_assessment
    
    state = {
        "assessment_present": False,
        "assessment_id": "",
        "coverage_percent": 0.0,
        "overall_status": "UNKNOWN",
        "missing_verifications_count": 0,
        "blocking_failures_count": 0,
        "generated_utc": "",
    }
    
    assessment = get_assessment(project_id)
    if assessment:
        state["assessment_present"] = True
        state["assessment_id"] = assessment.assessment_id
        state["coverage_percent"] = assessment.verification_coverage_percent
        state["overall_status"] = assessment.overall_status.upper() if assessment.overall_status else "UNKNOWN"
        state["missing_verifications_count"] = len(assessment.missing_verifications or [])
        state["blocking_failures_count"] = len(assessment.blocking_failures or [])
        state["generated_utc"] = assessment.generated_utc
    
    return state


def _get_payment_state(project_id: str) -> Dict[str, Any]:
    """
    PATCH 13A-4G: Get payment state from intake record.
    
    Returns payment workflow visibility:
    - payment_link_sent: bool
    - payment_confirmed: bool
    - payment timestamps
    - product details
    - kickoff_blocked_by_payment: bool
    """
    from services.intake.storage import load_intake_record
    
    state = {
        "payment_link_sent": False,
        "payment_link_sent_at_utc": "",
        "payment_confirmed": False,
        "payment_received_at_utc": "",
        "payment_confirmed_via": "",
        "product_id": "",
        "product_title": "",
        "price_display": "",
        "kickoff_blocked_by_payment": False,
    }
    
    # Try to find linked intake
    project_root = _projects_root() / project_id
    meta = _read_json_safe(project_root / "meta.json")
    intake_meta = _read_json_safe(project_root / "communications" / "intake.json")
    
    intake_id = meta.get("canonical_intake_id") or intake_meta.get("canonical_intake_id") or ""
    
    # If no intake link, check if project_id is an intake ID
    if not intake_id and project_id.startswith("FB-"):
        intake_id = project_id
    
    if not intake_id:
        return state
    
    try:
        intake_record = load_intake_record(intake_id, persist_recovery=False)
        payment = intake_record.get("payment") or {}
        
        state["payment_link_sent"] = bool(payment.get("payment_link_generated_at_utc"))
        state["payment_link_sent_at_utc"] = payment.get("payment_link_sent_at_utc") or ""
        state["payment_confirmed"] = bool(payment.get("payment_received_at_utc"))
        state["payment_received_at_utc"] = payment.get("payment_received_at_utc") or ""
        state["payment_confirmed_via"] = payment.get("payment_confirmed_via") or ""
        state["product_id"] = payment.get("product_id") or ""
        state["product_title"] = payment.get("product_title") or ""
        state["price_display"] = payment.get("price_display") or ""
        
        # Check if kickoff would be blocked by payment
        # Kickoff is blocked if: payment link sent but not confirmed, and not validation mode
        is_validation_mode = bool(intake_record.get("validation_project") or intake_record.get("founding_pilot"))
        state["kickoff_blocked_by_payment"] = (
            state["payment_link_sent"] 
            and not state["payment_confirmed"] 
            and not is_validation_mode
        )
        
    except Exception as e:
        logger.debug(f"Could not load intake record for payment state {intake_id}: {e}")
    
    return state


def _get_timeline_events(project_id: str) -> List[Dict[str, Any]]:
    """Get relevant timeline events from telemetry."""
    from services.durable_storage import active_data_root
    
    events: List[Dict[str, Any]] = []
    
    # Load from telemetry.jsonl
    telemetry_path = active_data_root() / "memory" / "telemetry.jsonl"
    if telemetry_path.is_file():
        all_events = _read_jsonl_safe(telemetry_path, limit=1000)
        
        # PATCH 13A-4F: Canonical lifecycle events + backward-compatible aliases
        # PATCH 13A-4G: Added payment_confirmed
        relevant_types = {
            # Canonical lifecycle events
            "upload_started",
            "upload_completed",
            "verified_complete",
            "external_verification_started",
            "external_verification_completed",
            "payment_confirmed",  # PATCH 13A-4G
            "project_kickoff_started",
            "project_kickoff_completed",
            "evidence_intelligence_started",
            "evidence_intelligence_completed",
            "cognition_started",
            "cognition_completed",
            "validation_started",
            "validation_completed",
            "compliance_health_completed",
            # Legacy aliases for backward compatibility
            "pilot_upload_started",
            "pilot_upload_completed",
            "post_kickoff_intelligence_started",
            "post_kickoff_intelligence_completed",
            "intake_kickoff_project",
            "intake_verified_complete",
            "operator_payment_received",  # PATCH 13A-4G: Legacy alias
        }
        
        for evt in all_events:
            # Check if event is about this project
            meta = evt.get("metadata") or {}
            evt_project = meta.get("project_id") or meta.get("intake_id") or ""
            
            if project_id in str(evt) or evt_project == project_id:
                event_type = evt.get("event_type") or evt.get("event") or ""
                if event_type in relevant_types or project_id in str(evt):
                    events.append({
                        "event_type": event_type,
                        "timestamp": evt.get("timestamp") or evt.get("recorded_utc") or "",
                        "message": evt.get("message") or "",
                        "metadata": meta,
                    })
    
    # Sort by timestamp
    events.sort(key=lambda e: e.get("timestamp") or "")
    
    return events[-50:]  # Last 50 events


def get_project_observability(project_id: str) -> Dict[str, Any]:
    """
    Build complete observability payload for a project.
    
    Returns all state an operator needs to answer:
    "What happened to this customer?"
    
    No SSH, no filesystem inspection, no log scraping required.
    """
    if not project_id:
        return {
            "ok": False,
            "error": "project_id required",
            "queried_at_utc": _utc_now(),
        }
    
    # Validate project_id format
    if "/" in project_id or ".." in project_id or "\\" in project_id:
        return {
            "ok": False,
            "error": "invalid project_id format",
            "queried_at_utc": _utc_now(),
        }
    
    project_root = _projects_root() / project_id
    project_exists = project_root.is_dir()
    
    # Also check if it's an intake that hasn't been kicked off yet
    intake_exists = False
    if not project_exists and project_id.startswith("FB-"):
        intake_root = _intakes_root() / project_id
        intake_exists = intake_root.is_dir()
    
    if not project_exists and not intake_exists:
        return {
            "ok": False,
            "error": f"Project not found: {project_id}",
            "project_id": project_id,
            "project_exists": False,
            "intake_exists": False,
            "queried_at_utc": _utc_now(),
        }
    
    # Build observability payload
    kickoff = _get_kickoff_state(project_id)
    payment = _get_payment_state(project_id)  # PATCH 13A-4G
    evidence_intelligence = _get_evidence_intelligence_state(project_id)
    cognition = _get_cognition_state(project_id)
    validation = _get_validation_state(project_id)
    compliance_health = _get_compliance_health_state(project_id)
    timeline = _get_timeline_events(project_id)
    
    return {
        "ok": True,
        "project_id": project_id,
        "queried_at_utc": _utc_now(),
        "kickoff": kickoff,
        "payment": payment,  # PATCH 13A-4G
        "evidence_intelligence": evidence_intelligence,
        "cognition": cognition,
        "validation": validation,
        "compliance_health": compliance_health,
        "timeline": timeline,
        "summary": {
            "project_exists": project_exists,
            "intake_exists": intake_exists,
            "kickoff_completed": kickoff.get("project_kickoff_completed", False),
            "ei_status": evidence_intelligence.get("status", "NOT_STARTED"),
            "cognition_status": cognition.get("status", "NOT_STARTED"),
            "validation_status": validation.get("status", "NOT_STARTED"),
            "compliance_status": compliance_health.get("overall_status", "UNKNOWN"),
            "timeline_events_count": len(timeline),
        },
    }

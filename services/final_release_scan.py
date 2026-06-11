"""PATCH 13A-5C: Final Release Inspection Cockpit.

Gated final-product inspection and approval system.
The operator is not the quality system — the organism is.
Operator can only approve release after all required gates pass.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .project_observability import (
    get_project_observability,
    _read_json_safe,
    _read_jsonl_safe,
    _projects_root,
)

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _release_state_path(project_id: str) -> Path:
    """Path to release state JSON for a project."""
    return _projects_root() / project_id / "release_state.json"


def _load_release_state(project_id: str) -> Dict[str, Any]:
    """Load release state from disk."""
    path = _release_state_path(project_id)
    return _read_json_safe(path)


def _save_release_state(project_id: str, state: Dict[str, Any]) -> None:
    """Save release state to disk."""
    path = _release_state_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _compute_deliverables_hash(project_id: str) -> str:
    """Compute hash of deliverables for audit trail."""
    project_root = _projects_root() / project_id
    cognition_dir = project_root / "cognition"
    
    hash_content = []
    
    for filename in ["cognition_summary.json", "validation_report.json", "next_actions.json"]:
        path = cognition_dir / filename
        if path.is_file():
            hash_content.append(f"{filename}:{path.stat().st_mtime}")
    
    if not hash_content:
        return "no_deliverables"
    
    return hashlib.sha256("|".join(hash_content).encode()).hexdigest()[:16]


def _check_custody_complete(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check custody chain is complete."""
    kickoff = obs.get("kickoff", {})
    custody = kickoff.get("custody_status", "")
    
    if custody == "verified_complete":
        return {
            "gate": "custody_complete",
            "status": "PASS",
            "blocking": True,
            "reason": "Custody chain verified complete",
            "evidence_ref": f"custody_status={custody}",
            "inspect_url": "",
        }
    elif custody:
        return {
            "gate": "custody_complete",
            "status": "WARNING",
            "blocking": False,
            "reason": f"Custody status is {custody}, not verified_complete",
            "evidence_ref": f"custody_status={custody}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "custody_complete",
            "status": "FAIL",
            "blocking": True,
            "reason": "No custody status recorded",
            "evidence_ref": "custody_status=missing",
            "inspect_url": "",
        }


def _check_external_verification(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check external verification completed."""
    timeline = obs.get("timeline", [])
    event_types = [e.get("event_type") for e in timeline]
    
    if "external_verification_completed" in event_types:
        return {
            "gate": "external_verification_complete",
            "status": "PASS",
            "blocking": False,
            "reason": "External verification completed",
            "evidence_ref": "timeline:external_verification_completed",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "external_verification_complete",
            "status": "WARNING",
            "blocking": False,
            "reason": "External verification not found in timeline",
            "evidence_ref": "timeline:missing",
            "inspect_url": "",
        }


def _check_evidence_intelligence(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check Evidence Intelligence completed."""
    ei = obs.get("evidence_intelligence", {})
    status = ei.get("status", "NOT_STARTED")
    
    if status == "COMPLETED":
        return {
            "gate": "evidence_intelligence_complete",
            "status": "PASS",
            "blocking": True,
            "reason": "Evidence Intelligence completed successfully",
            "evidence_ref": f"ei.status={status}",
            "inspect_url": "",
        }
    elif status == "PARTIAL":
        return {
            "gate": "evidence_intelligence_complete",
            "status": "WARNING",
            "blocking": False,
            "reason": f"Evidence Intelligence partially completed ({ei.get('ei_failed_count', 0)} failures)",
            "evidence_ref": f"ei.status={status}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "evidence_intelligence_complete",
            "status": "FAIL",
            "blocking": True,
            "reason": f"Evidence Intelligence status: {status}",
            "evidence_ref": f"ei.status={status}",
            "inspect_url": "",
        }


def _check_cognition(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check Cognition completed."""
    cog = obs.get("cognition", {})
    status = cog.get("status", "NOT_STARTED")
    
    if status == "COMPLETED":
        return {
            "gate": "cognition_complete",
            "status": "PASS",
            "blocking": True,
            "reason": "Cognition completed successfully",
            "evidence_ref": f"cognition.status={status}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "cognition_complete",
            "status": "FAIL",
            "blocking": True,
            "reason": f"Cognition status: {status}",
            "evidence_ref": f"cognition.status={status}",
            "inspect_url": "",
        }


def _check_validation(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check Validation completed."""
    val = obs.get("validation", {})
    status = val.get("status", "NOT_STARTED")
    
    if status == "COMPLETED":
        return {
            "gate": "validation_complete",
            "status": "PASS",
            "blocking": True,
            "reason": "Validation completed successfully",
            "evidence_ref": f"validation.status={status}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "validation_complete",
            "status": "FAIL",
            "blocking": True,
            "reason": f"Validation status: {status}",
            "evidence_ref": f"validation.status={status}",
            "inspect_url": "",
        }


def _check_compliance_health(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check Compliance Health assessment exists."""
    ch = obs.get("compliance_health", {})
    present = ch.get("assessment_present", False)
    
    if present:
        overall = ch.get("overall_status", "UNKNOWN")
        if overall == "RED":
            return {
                "gate": "compliance_health_complete",
                "status": "WARNING",
                "blocking": False,
                "reason": f"Compliance Health assessment present but status is RED",
                "evidence_ref": f"compliance_health.overall_status={overall}",
                "inspect_url": "",
            }
        return {
            "gate": "compliance_health_complete",
            "status": "PASS",
            "blocking": True,
            "reason": f"Compliance Health assessment present (status: {overall})",
            "evidence_ref": f"compliance_health.overall_status={overall}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "compliance_health_complete",
            "status": "FAIL",
            "blocking": True,
            "reason": "Compliance Health assessment not found",
            "evidence_ref": "compliance_health.assessment_present=false",
            "inspect_url": "",
        }


def _check_blocking_failures(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check for blocking compliance failures."""
    ch = obs.get("compliance_health", {})
    blocking_count = ch.get("blocking_failures_count", 0)
    
    if blocking_count == 0:
        return {
            "gate": "no_blocking_failures",
            "status": "PASS",
            "blocking": True,
            "reason": "No blocking compliance failures",
            "evidence_ref": f"blocking_failures_count={blocking_count}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_blocking_failures",
            "status": "FAIL",
            "blocking": True,
            "reason": f"{blocking_count} blocking compliance failure(s) found",
            "evidence_ref": f"blocking_failures_count={blocking_count}",
            "inspect_url": "",
        }


def _check_critical_findings(project_id: str, obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check for unresolved critical findings."""
    val = obs.get("validation", {})
    safety_count = val.get("safety_warnings_count", 0)
    
    if safety_count == 0:
        return {
            "gate": "no_unresolved_critical_findings",
            "status": "PASS",
            "blocking": True,
            "reason": "No unresolved critical findings",
            "evidence_ref": f"safety_warnings_count={safety_count}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_unresolved_critical_findings",
            "status": "WARNING",
            "blocking": False,
            "reason": f"{safety_count} safety warning(s) require review",
            "evidence_ref": f"safety_warnings_count={safety_count}",
            "inspect_url": "",
        }


def _check_placeholder_outputs(project_id: str) -> Dict[str, Any]:
    """Check for placeholder content in deliverables."""
    project_root = _projects_root() / project_id
    cognition_dir = project_root / "cognition"
    
    placeholders_found = []
    placeholder_patterns = ["TODO", "PLACEHOLDER", "TBD", "FIXME", "[INSERT"]
    
    for filename in ["cognition_summary.json", "validation_report.json"]:
        path = cognition_dir / filename
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8").upper()
                for pattern in placeholder_patterns:
                    if pattern in content:
                        placeholders_found.append(f"{filename}:{pattern}")
            except Exception:
                pass
    
    if not placeholders_found:
        return {
            "gate": "no_placeholder_outputs",
            "status": "PASS",
            "blocking": True,
            "reason": "No placeholder content detected",
            "evidence_ref": "scan:clean",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_placeholder_outputs",
            "status": "FAIL",
            "blocking": True,
            "reason": f"Placeholder content found: {', '.join(placeholders_found[:3])}",
            "evidence_ref": f"scan:found:{len(placeholders_found)}",
            "inspect_url": "",
        }


def _check_missing_deliverables(project_id: str) -> Dict[str, Any]:
    """Check for required deliverables presence."""
    project_root = _projects_root() / project_id
    cognition_dir = project_root / "cognition"
    
    required = ["cognition_summary.json", "validation_report.json"]
    missing = [f for f in required if not (cognition_dir / f).is_file()]
    
    if not missing:
        return {
            "gate": "no_missing_final_deliverables",
            "status": "PASS",
            "blocking": True,
            "reason": "All required deliverables present",
            "evidence_ref": f"files:{','.join(required)}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_missing_final_deliverables",
            "status": "FAIL",
            "blocking": True,
            "reason": f"Missing deliverables: {', '.join(missing)}",
            "evidence_ref": f"missing:{','.join(missing)}",
            "inspect_url": "",
        }


def _check_timeline_gaps(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check for gaps in timeline (missing expected events)."""
    timeline = obs.get("timeline", [])
    event_types = set(e.get("event_type") for e in timeline)
    
    required_events = {
        "upload_started", "upload_completed", "project_kickoff_completed",
        "cognition_completed", "validation_completed",
    }
    
    missing = required_events - event_types
    
    if not missing:
        return {
            "gate": "no_timeline_gaps",
            "status": "PASS",
            "blocking": False,
            "reason": "All required timeline events present",
            "evidence_ref": f"events:{len(timeline)}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_timeline_gaps",
            "status": "WARNING",
            "blocking": False,
            "reason": f"Missing timeline events: {', '.join(list(missing)[:3])}",
            "evidence_ref": f"missing:{','.join(list(missing)[:3])}",
            "inspect_url": "",
        }


def _check_human_review_items(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check for unreviewed human review items."""
    val = obs.get("validation", {})
    review_count = val.get("human_review_items_count", 0)
    
    if review_count == 0:
        return {
            "gate": "no_unreviewed_human_review_items",
            "status": "PASS",
            "blocking": False,
            "reason": "No human review items pending",
            "evidence_ref": f"human_review_items_count={review_count}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_unreviewed_human_review_items",
            "status": "WARNING",
            "blocking": False,
            "reason": f"{review_count} human review item(s) pending",
            "evidence_ref": f"human_review_items_count={review_count}",
            "inspect_url": "",
        }


def _check_required_unknowns(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Check for UNKNOWN status on required verifications."""
    ch = obs.get("compliance_health", {})
    missing_count = ch.get("missing_verifications_count", 0)
    
    if missing_count == 0:
        return {
            "gate": "no_required_unknowns",
            "status": "PASS",
            "blocking": False,
            "reason": "All required verifications complete",
            "evidence_ref": f"missing_verifications_count={missing_count}",
            "inspect_url": "",
        }
    else:
        return {
            "gate": "no_required_unknowns",
            "status": "WARNING",
            "blocking": False,
            "reason": f"{missing_count} required verification(s) still UNKNOWN",
            "evidence_ref": f"missing_verifications_count={missing_count}",
            "inspect_url": "",
        }


def scan_release_gates(project_id: str) -> Dict[str, Any]:
    """
    Perform complete release gate scan.
    
    Returns all gates with their status, along with overall release status.
    """
    if not project_id:
        return {
            "ok": False,
            "error": "project_id required",
            "scanned_at_utc": _utc_now(),
        }
    
    # Get observability data
    obs = get_project_observability(project_id)
    if not obs.get("ok"):
        return {
            "ok": False,
            "error": obs.get("error", "Failed to get project observability"),
            "scanned_at_utc": _utc_now(),
        }
    
    # Run all gate checks
    gates: List[Dict[str, Any]] = [
        _check_custody_complete(obs),
        _check_external_verification(obs),
        _check_evidence_intelligence(obs),
        _check_cognition(obs),
        _check_validation(obs),
        _check_compliance_health(obs),
        _check_blocking_failures(obs),
        _check_critical_findings(project_id, obs),
        _check_placeholder_outputs(project_id),
        _check_missing_deliverables(project_id),
        _check_timeline_gaps(obs),
        _check_human_review_items(obs),
        _check_required_unknowns(obs),
    ]
    
    # Compute overall status
    blocking_failures = [g for g in gates if g["status"] == "FAIL" and g["blocking"]]
    warnings = [g for g in gates if g["status"] == "WARNING"]
    
    if blocking_failures:
        release_status = "RED"
        ready_to_release = False
    elif warnings:
        release_status = "AMBER"
        ready_to_release = False  # Requires override
    else:
        release_status = "GREEN"
        ready_to_release = True
    
    # Check for existing approval
    state = _load_release_state(project_id)
    if state.get("approved_at_utc"):
        ready_to_release = True
    
    # Required operator actions
    required_actions = []
    for g in blocking_failures:
        required_actions.append(f"Resolve: {g['gate']} - {g['reason']}")
    if release_status == "AMBER" and not state.get("amber_override_at_utc"):
        required_actions.append("AMBER override required with justification")
    
    return {
        "ok": True,
        "project_id": project_id,
        "scanned_at_utc": _utc_now(),
        "release_status": release_status,
        "ready_to_release": ready_to_release,
        "gates": gates,
        "blocking_failures": [g["gate"] for g in blocking_failures],
        "warnings": [g["gate"] for g in warnings],
        "required_operator_actions": required_actions,
        "approval_state": {
            "approved": bool(state.get("approved_at_utc")),
            "approved_at_utc": state.get("approved_at_utc", ""),
            "approved_by": state.get("approved_by", ""),
            "amber_override": bool(state.get("amber_override_at_utc")),
            "amber_override_reason": state.get("amber_override_reason", ""),
            "sent": bool(state.get("sent_at_utc")),
            "sent_at_utc": state.get("sent_at_utc", ""),
        },
        "deliverables_hash": _compute_deliverables_hash(project_id),
    }


def approve_release(project_id: str, *, operator_id: str = "operator") -> Dict[str, Any]:
    """
    Approve release after all gates pass.
    
    Blocked if release_status is RED.
    """
    if not project_id:
        return {"ok": False, "error": "project_id required"}
    
    # Run scan first
    scan = scan_release_gates(project_id)
    if not scan.get("ok"):
        return scan
    
    # Check if RED
    if scan["release_status"] == "RED":
        return {
            "ok": False,
            "error": "Cannot approve — release status is RED",
            "blocking_failures": scan["blocking_failures"],
            "required_operator_actions": scan["required_operator_actions"],
        }
    
    # Check if AMBER without override
    state = _load_release_state(project_id)
    if scan["release_status"] == "AMBER" and not state.get("amber_override_at_utc"):
        return {
            "ok": False,
            "error": "Cannot approve — AMBER status requires override first",
            "warnings": scan["warnings"],
            "required_operator_actions": ["Call override-amber endpoint with justification"],
        }
    
    # Idempotent check
    if state.get("approved_at_utc"):
        return {
            "ok": True,
            "project_id": project_id,
            "action": "approve",
            "idempotent_return": True,
            "approved_at_utc": state["approved_at_utc"],
            "approved_by": state.get("approved_by", ""),
            "deliverables_hash": scan["deliverables_hash"],
        }
    
    # Record approval
    now = _utc_now()
    state["approved_at_utc"] = now
    state["approved_by"] = operator_id
    state["release_status_at_approval"] = scan["release_status"]
    state["deliverables_hash"] = scan["deliverables_hash"]
    _save_release_state(project_id, state)
    
    # Emit timeline event
    try:
        from services.intake.telemetry import emit_lifecycle_event
        emit_lifecycle_event(
            "release_approved",
            message=f"Release approved for {project_id}",
            metadata={
                "project_id": project_id,
                "approved_by": operator_id,
                "approved_at_utc": now,
                "release_status": scan["release_status"],
                "deliverables_hash": scan["deliverables_hash"],
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
        "release_status": scan["release_status"],
        "deliverables_hash": scan["deliverables_hash"],
    }


def override_amber(
    project_id: str,
    *,
    reason: str,
    operator_id: str = "operator",
) -> Dict[str, Any]:
    """
    Override AMBER status with explicit justification.
    
    Required before approval when warnings exist.
    """
    if not project_id:
        return {"ok": False, "error": "project_id required"}
    
    if not reason or len(reason.strip()) < 10:
        return {
            "ok": False,
            "error": "Override reason required (minimum 10 characters)",
        }
    
    # Run scan first
    scan = scan_release_gates(project_id)
    if not scan.get("ok"):
        return scan
    
    # Cannot override RED
    if scan["release_status"] == "RED":
        return {
            "ok": False,
            "error": "Cannot override RED status — resolve blocking failures first",
            "blocking_failures": scan["blocking_failures"],
        }
    
    # Load state
    state = _load_release_state(project_id)
    
    # Idempotent check
    if state.get("amber_override_at_utc"):
        return {
            "ok": True,
            "project_id": project_id,
            "action": "override_amber",
            "idempotent_return": True,
            "amber_override_at_utc": state["amber_override_at_utc"],
            "amber_override_reason": state.get("amber_override_reason", ""),
        }
    
    # Record override
    now = _utc_now()
    state["amber_override_at_utc"] = now
    state["amber_override_by"] = operator_id
    state["amber_override_reason"] = reason.strip()[:500]
    state["warnings_at_override"] = scan["warnings"]
    _save_release_state(project_id, state)
    
    # Emit timeline event
    try:
        from services.intake.telemetry import emit_lifecycle_event
        emit_lifecycle_event(
            "release_amber_override",
            message=f"AMBER override for {project_id}: {reason[:100]}",
            metadata={
                "project_id": project_id,
                "operator_id": operator_id,
                "override_at_utc": now,
                "reason": reason.strip()[:200],
                "warnings": scan["warnings"],
            },
        )
    except Exception:
        pass
    
    return {
        "ok": True,
        "project_id": project_id,
        "action": "override_amber",
        "amber_override_at_utc": now,
        "amber_override_by": operator_id,
        "amber_override_reason": reason.strip()[:200],
        "warnings_overridden": scan["warnings"],
    }


def send_release(
    project_id: str,
    *,
    recipient_email: str = "",
    operator_id: str = "operator",
) -> Dict[str, Any]:
    """
    Mark release as sent to customer.
    
    Blocked until release is approved.
    """
    if not project_id:
        return {"ok": False, "error": "project_id required"}
    
    # Load state
    state = _load_release_state(project_id)
    
    # Must be approved first
    if not state.get("approved_at_utc"):
        return {
            "ok": False,
            "error": "Cannot send — release not yet approved",
        }
    
    # Idempotent check
    if state.get("sent_at_utc"):
        return {
            "ok": True,
            "project_id": project_id,
            "action": "send",
            "idempotent_return": True,
            "sent_at_utc": state["sent_at_utc"],
            "sent_to": state.get("sent_to", ""),
        }
    
    # Resolve recipient if not provided
    if not recipient_email:
        obs = get_project_observability(project_id)
        kickoff = obs.get("kickoff", {})
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
    _save_release_state(project_id, state)
    
    # Emit timeline event
    try:
        from services.intake.telemetry import emit_lifecycle_event
        emit_lifecycle_event(
            "release_sent",
            message=f"Release sent for {project_id}",
            metadata={
                "project_id": project_id,
                "sent_to": recipient_email,
                "sent_by": operator_id,
                "sent_at_utc": now,
                "deliverables_hash": state.get("deliverables_hash", ""),
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
        "deliverables_hash": state.get("deliverables_hash", ""),
    }

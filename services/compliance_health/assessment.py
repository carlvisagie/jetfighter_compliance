"""Compliance Health assessment builder."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .registry import load_requirements
from .schemas import ComplianceHealthAssessment, RequirementStatus


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _root() -> Path:
    from ..config import DATA
    d = DATA / "compliance_health"
    d.mkdir(parents=True, exist_ok=True)
    return d


def assessment_path(project_id: str) -> Path:
    return _root() / f"assessment_{project_id}.json"


def build_assessment(project_id: str) -> ComplianceHealthAssessment:
    """
    Build compliance health assessment for a project.
    
    Uses current requirement registry state.
    All requirements start UNKNOWN until verified.
    No fake passes. No assumptions.
    """
    requirements = load_requirements()
    
    # Compute missing verifications
    missing = [
        r.requirement_id for r in requirements
        if r.required and r.status == RequirementStatus.UNKNOWN
    ]
    
    # Compute blocking failures
    blocking_failed = [
        r.requirement_id for r in requirements
        if r.blocking and r.status == RequirementStatus.FAIL
    ]
    
    # Create assessment
    assessment = ComplianceHealthAssessment(
        assessment_id=f"ASSESS-{uuid.uuid4().hex[:10]}",
        project_id=project_id,
        overall_status="GREEN",  # Will be computed
        verification_coverage_percent=0.0,  # Will be computed
        requirements=requirements,
        missing_verifications=missing,
        blocking_failures=blocking_failed,
        generated_utc=_utc(),
    )
    
    # Compute derived fields
    assessment.verification_coverage_percent = assessment.compute_coverage()
    assessment.overall_status = assessment.compute_status()
    
    # Save assessment
    path = assessment_path(project_id)
    path.write_text(json.dumps(assessment.model_dump(), indent=2), encoding="utf-8")
    
    # PATCH 13A-4F: Emit compliance_health_completed lifecycle event
    try:
        from services.intake.telemetry import emit_lifecycle_event
        emit_lifecycle_event(
            "compliance_health_completed",
            message=f"Compliance health assessment completed for {project_id}",
            metadata={
                "project_id": project_id,
                "assessment_id": assessment.assessment_id,
                "overall_status": assessment.overall_status,
                "coverage_percent": assessment.verification_coverage_percent,
                "missing_count": len(missing),
                "blocking_failures": len(blocking_failed),
            },
        )
    except Exception:
        pass
    
    return assessment


def get_assessment(project_id: str) -> Optional[ComplianceHealthAssessment]:
    """Load existing assessment for a project."""
    path = assessment_path(project_id)
    if not path.is_file():
        return None
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ComplianceHealthAssessment.model_validate(data)
    except Exception:
        return None


def get_or_build_assessment(project_id: str) -> ComplianceHealthAssessment:
    """Get existing assessment or build new one."""
    assessment = get_assessment(project_id)
    if assessment:
        return assessment
    return build_assessment(project_id)

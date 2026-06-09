"""Compliance Health schemas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RequirementStatus(str, Enum):
    """Verification status for a single requirement."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AssessmentStatus(str, Enum):
    """Overall compliance health status."""
    GREEN = "GREEN"    # All required verifications passed
    AMBER = "AMBER"    # Missing required verifications or low confidence
    RED = "RED"        # Blocking verification failed


class ComplianceHealthRequirement(BaseModel):
    """A single compliance verification requirement."""
    requirement_id: str = Field(..., description="Unique identifier (e.g., 'sam_registration')")
    name: str = Field(..., description="Human-readable name")
    category: str = Field(..., description="Category (e.g., 'external_verification', 'document_quality')")
    required: bool = Field(..., description="Must be satisfied for compliance")
    blocking: bool = Field(..., description="Failure triggers RED status")
    verification_source: str = Field(..., description="Where this is verified (e.g., 'sam_gov_api', 'document_quality_gate')")
    status: RequirementStatus = Field(default=RequirementStatus.UNKNOWN)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in verification (0.0-1.0)")
    last_verified_utc: Optional[str] = Field(default=None, description="ISO timestamp of last verification")
    evidence_refs: List[str] = Field(default_factory=list, description="Document IDs or evidence identifiers")


class ComplianceHealthAssessment(BaseModel):
    """Overall compliance health assessment for a project."""
    assessment_id: str = Field(..., description="Unique assessment ID")
    project_id: str = Field(..., description="Project/intake ID being assessed")
    overall_status: AssessmentStatus
    verification_coverage_percent: float = Field(..., ge=0.0, le=100.0, description="Percentage of required verifications completed")
    requirements: List[ComplianceHealthRequirement] = Field(default_factory=list)
    missing_verifications: List[str] = Field(default_factory=list, description="Requirement IDs with status=UNKNOWN")
    blocking_failures: List[str] = Field(default_factory=list, description="Requirement IDs with blocking=True and status=FAIL")
    generated_utc: str = Field(..., description="ISO timestamp of assessment generation")

    def compute_coverage(self) -> float:
        """Calculate verification coverage percentage."""
        required = [r for r in self.requirements if r.required]
        if not required:
            return 100.0
        verified = [r for r in required if r.status in (RequirementStatus.PASS, RequirementStatus.NOT_APPLICABLE)]
        return (len(verified) / len(required)) * 100.0

    def compute_status(self) -> AssessmentStatus:
        """Compute overall status from requirements."""
        # RED: Any blocking verification failed
        blocking_failed = [r for r in self.requirements if r.blocking and r.status == RequirementStatus.FAIL]
        if blocking_failed:
            return AssessmentStatus.RED
        
        # AMBER: Missing required verifications
        required_missing = [
            r for r in self.requirements 
            if r.required and r.status == RequirementStatus.UNKNOWN
        ]
        if required_missing:
            return AssessmentStatus.AMBER
        
        # GREEN: All required verifications passed (or not applicable)
        return AssessmentStatus.GREEN

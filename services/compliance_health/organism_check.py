"""Compliance Health organism check."""
from __future__ import annotations

from organism_core.health import Check, CheckResult, Severity

from .assessment import get_or_build_assessment
from .registry import load_requirements
from .schemas import AssessmentStatus, RequirementStatus


class ComplianceHealthCoverageCheck(Check):
    """
    Check compliance health verification coverage.
    
    Rules:
    - GREEN: 100% required verification coverage (all PASS or NOT_APPLICABLE)
    - AMBER: Missing required verifications (status=UNKNOWN)
    - RED: Blocking verification failed (blocking=True and status=FAIL)
    """
    
    name = "compliance_health_coverage"
    
    def evaluate(self, bundle: dict) -> CheckResult:
        """Evaluate compliance health coverage."""
        # Check if we have any projects with assessments
        requirements = load_requirements()
        
        # Count requirement statuses
        total_required = sum(1 for r in requirements if r.required)
        verified = sum(
            1 for r in requirements 
            if r.required and r.status in (RequirementStatus.PASS, RequirementStatus.NOT_APPLICABLE)
        )
        unknown = sum(1 for r in requirements if r.required and r.status == RequirementStatus.UNKNOWN)
        blocking_failed = sum(1 for r in requirements if r.blocking and r.status == RequirementStatus.FAIL)
        
        coverage = (verified / total_required * 100.0) if total_required > 0 else 0.0
        
        # RED: Blocking verification failed
        if blocking_failed > 0:
            blocking_names = [
                r.name for r in requirements 
                if r.blocking and r.status == RequirementStatus.FAIL
            ]
            return CheckResult(
                name=self.name,
                ok=False,
                severity=Severity.RED,
                detail=f"Blocking verification failed: {', '.join(blocking_names)}",
                evidence={
                    "coverage_percent": coverage,
                    "blocking_failures": blocking_failed,
                    "blocking_failed_names": blocking_names,
                },
            )
        
        # AMBER: Missing required verifications
        if unknown > 0:
            return CheckResult(
                name=self.name,
                ok=False,
                severity=Severity.AMBER,
                detail=f"{unknown} required verifications pending (coverage: {coverage:.1f}%)",
                evidence={
                    "coverage_percent": coverage,
                    "required_total": total_required,
                    "verified": verified,
                    "unknown": unknown,
                },
            )
        
        # GREEN: All required verifications complete
        return CheckResult(
            name=self.name,
            ok=True,
            severity=Severity.INFO,
            detail=f"All required verifications complete (coverage: {coverage:.1f}%)",
            evidence={
                "coverage_percent": coverage,
                "required_total": total_required,
                "verified": verified,
            },
        )

"""Tests for Compliance Health Foundation (PATCH 13A-0)."""
import json
from pathlib import Path

import pytest

from services.compliance_health import (
    AssessmentStatus,
    ComplianceHealthAssessment,
    ComplianceHealthRequirement,
    RequirementStatus,
    build_assessment,
    get_assessment,
    get_requirement,
    load_requirements,
    update_requirement,
)
from services.compliance_health.organism_check import ComplianceHealthCoverageCheck


@pytest.fixture
def clean_compliance_health(tmp_path, monkeypatch):
    """Clean compliance health state for testing."""
    import services.config
    monkeypatch.setattr(services.config, "DATA", tmp_path / "data")
    yield tmp_path


def test_requirement_schema_validation():
    """Test ComplianceHealthRequirement schema."""
    req = ComplianceHealthRequirement(
        requirement_id="sam_registration",
        name="SAM.gov Registration",
        category="external_verification",
        required=True,
        blocking=True,
        verification_source="sam_gov_api",
        status=RequirementStatus.UNKNOWN,
        confidence=0.0,
    )
    
    assert req.requirement_id == "sam_registration"
    assert req.status == RequirementStatus.UNKNOWN
    assert req.confidence == 0.0
    assert req.required is True
    assert req.blocking is True
    assert req.evidence_refs == []


def test_requirement_status_enum():
    """Test RequirementStatus enum values."""
    assert RequirementStatus.PASS == "PASS"
    assert RequirementStatus.FAIL == "FAIL"
    assert RequirementStatus.UNKNOWN == "UNKNOWN"
    assert RequirementStatus.NOT_APPLICABLE == "NOT_APPLICABLE"


def test_assessment_status_enum():
    """Test AssessmentStatus enum values."""
    assert AssessmentStatus.GREEN == "GREEN"
    assert AssessmentStatus.AMBER == "AMBER"
    assert AssessmentStatus.RED == "RED"


def test_registry_seeding(clean_compliance_health):
    """Test requirement registry seeds with all UNKNOWN."""
    requirements = load_requirements()
    
    assert len(requirements) == 10
    assert all(r.status == RequirementStatus.UNKNOWN for r in requirements)
    assert all(r.confidence == 0.0 for r in requirements)
    
    # Check canonical requirements exist
    req_ids = {r.requirement_id for r in requirements}
    assert "sam_registration" in req_ids
    assert "uei_verification" in req_ids
    assert "cage_verification" in req_ids
    assert "certification_verification" in req_ids
    assert "representation_verification" in req_ids
    assert "document_quality" in req_ids
    assert "evidence_quality" in req_ids
    assert "clause_verification" in req_ids
    assert "flowdown_verification" in req_ids
    assert "temporal_verification" in req_ids


def test_get_requirement(clean_compliance_health):
    """Test fetching single requirement."""
    req = get_requirement("sam_registration")
    
    assert req is not None
    assert req.requirement_id == "sam_registration"
    assert req.name == "SAM.gov Registration"
    assert req.category == "external_verification"
    assert req.required is True
    assert req.blocking is True
    assert req.status == RequirementStatus.UNKNOWN


def test_update_requirement(clean_compliance_health):
    """Test updating requirement status."""
    success = update_requirement(
        requirement_id="sam_registration",
        status=RequirementStatus.PASS,
        confidence=0.95,
        last_verified_utc="2026-06-09T20:00:00Z",
        evidence_refs=["doc-123"],
    )
    
    assert success is True
    
    req = get_requirement("sam_registration")
    assert req.status == RequirementStatus.PASS
    assert req.confidence == 0.95
    assert req.last_verified_utc == "2026-06-09T20:00:00Z"
    assert req.evidence_refs == ["doc-123"]


def test_assessment_coverage_calculation():
    """Test verification coverage calculation."""
    requirements = [
        ComplianceHealthRequirement(
            requirement_id="req1",
            name="Req 1",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.PASS,
        ),
        ComplianceHealthRequirement(
            requirement_id="req2",
            name="Req 2",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.PASS,
        ),
        ComplianceHealthRequirement(
            requirement_id="req3",
            name="Req 3",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.UNKNOWN,
        ),
        ComplianceHealthRequirement(
            requirement_id="req4",
            name="Req 4",
            category="test",
            required=False,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.UNKNOWN,
        ),
    ]
    
    assessment = ComplianceHealthAssessment(
        assessment_id="TEST-001",
        project_id="FB-test",
        overall_status=AssessmentStatus.AMBER,
        verification_coverage_percent=0.0,
        requirements=requirements,
        missing_verifications=[],
        blocking_failures=[],
        generated_utc="2026-06-09T20:00:00Z",
    )
    
    coverage = assessment.compute_coverage()
    # 2 passed out of 3 required = 66.67%
    assert coverage == pytest.approx(66.67, abs=0.1)


def test_assessment_status_green():
    """Test GREEN status (all required verifications complete)."""
    requirements = [
        ComplianceHealthRequirement(
            requirement_id="req1",
            name="Req 1",
            category="test",
            required=True,
            blocking=True,
            verification_source="test",
            status=RequirementStatus.PASS,
        ),
        ComplianceHealthRequirement(
            requirement_id="req2",
            name="Req 2",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.NOT_APPLICABLE,
        ),
    ]
    
    assessment = ComplianceHealthAssessment(
        assessment_id="TEST-001",
        project_id="FB-test",
        overall_status=AssessmentStatus.AMBER,  # Will be recomputed
        verification_coverage_percent=0.0,
        requirements=requirements,
        missing_verifications=[],
        blocking_failures=[],
        generated_utc="2026-06-09T20:00:00Z",
    )
    
    status = assessment.compute_status()
    assert status == AssessmentStatus.GREEN


def test_assessment_status_amber():
    """Test AMBER status (missing required verifications)."""
    requirements = [
        ComplianceHealthRequirement(
            requirement_id="req1",
            name="Req 1",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.PASS,
        ),
        ComplianceHealthRequirement(
            requirement_id="req2",
            name="Req 2",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.UNKNOWN,
        ),
    ]
    
    assessment = ComplianceHealthAssessment(
        assessment_id="TEST-001",
        project_id="FB-test",
        overall_status=AssessmentStatus.GREEN,  # Will be recomputed
        verification_coverage_percent=0.0,
        requirements=requirements,
        missing_verifications=[],
        blocking_failures=[],
        generated_utc="2026-06-09T20:00:00Z",
    )
    
    status = assessment.compute_status()
    assert status == AssessmentStatus.AMBER


def test_assessment_status_red():
    """Test RED status (blocking verification failed)."""
    requirements = [
        ComplianceHealthRequirement(
            requirement_id="req1",
            name="Req 1",
            category="test",
            required=True,
            blocking=True,
            verification_source="test",
            status=RequirementStatus.FAIL,
        ),
        ComplianceHealthRequirement(
            requirement_id="req2",
            name="Req 2",
            category="test",
            required=True,
            blocking=False,
            verification_source="test",
            status=RequirementStatus.PASS,
        ),
    ]
    
    assessment = ComplianceHealthAssessment(
        assessment_id="TEST-001",
        project_id="FB-test",
        overall_status=AssessmentStatus.GREEN,  # Will be recomputed
        verification_coverage_percent=0.0,
        requirements=requirements,
        missing_verifications=[],
        blocking_failures=[],
        generated_utc="2026-06-09T20:00:00Z",
    )
    
    status = assessment.compute_status()
    assert status == AssessmentStatus.RED


def test_build_assessment_all_unknown(clean_compliance_health):
    """Test building assessment with all requirements UNKNOWN (default state)."""
    assessment = build_assessment("FB-test")
    
    assert assessment.project_id == "FB-test"
    assert len(assessment.requirements) == 10
    assert all(r.status == RequirementStatus.UNKNOWN for r in assessment.requirements)
    
    # All required are UNKNOWN → AMBER
    assert assessment.overall_status == AssessmentStatus.AMBER
    
    # 0 verified out of required
    assert assessment.verification_coverage_percent == 0.0
    
    # All required should be in missing_verifications
    assert len(assessment.missing_verifications) > 0
    
    # No blocking failures yet (all UNKNOWN)
    assert len(assessment.blocking_failures) == 0


def test_build_assessment_green_path(clean_compliance_health):
    """Test building assessment with all required verifications passed (GREEN)."""
    # Update all required requirements to PASS
    for req in load_requirements():
        if req.required:
            update_requirement(
                requirement_id=req.requirement_id,
                status=RequirementStatus.PASS,
                confidence=0.9,
                last_verified_utc="2026-06-09T20:00:00Z",
            )
    
    assessment = build_assessment("FB-test")
    
    assert assessment.overall_status == AssessmentStatus.GREEN
    assert assessment.verification_coverage_percent == 100.0
    assert len(assessment.missing_verifications) == 0
    assert len(assessment.blocking_failures) == 0


def test_build_assessment_red_path(clean_compliance_health):
    """Test building assessment with blocking verification failure (RED)."""
    # Fail a blocking requirement
    update_requirement(
        requirement_id="sam_registration",
        status=RequirementStatus.FAIL,
        confidence=0.9,
        last_verified_utc="2026-06-09T20:00:00Z",
    )
    
    assessment = build_assessment("FB-test")
    
    assert assessment.overall_status == AssessmentStatus.RED
    assert "sam_registration" in assessment.blocking_failures


def test_get_assessment_persistence(clean_compliance_health):
    """Test assessment persistence and retrieval."""
    # Build and save
    assessment1 = build_assessment("FB-test")
    
    # Retrieve
    assessment2 = get_assessment("FB-test")
    
    assert assessment2 is not None
    assert assessment2.project_id == "FB-test"
    assert assessment2.assessment_id == assessment1.assessment_id


def test_organism_check_green(clean_compliance_health):
    """Test organism check returns GREEN when all required verifications complete."""
    # Pass all required requirements
    for req in load_requirements():
        if req.required:
            update_requirement(
                requirement_id=req.requirement_id,
                status=RequirementStatus.PASS,
                confidence=0.9,
            )
    
    check = ComplianceHealthCoverageCheck()
    result = check.evaluate({})
    
    assert result.ok is True
    assert result.severity.value == "info"
    assert "complete" in result.detail.lower()
    assert result.evidence["coverage_percent"] == 100.0


def test_organism_check_amber(clean_compliance_health):
    """Test organism check returns AMBER when required verifications missing."""
    # Leave all as UNKNOWN (default state)
    check = ComplianceHealthCoverageCheck()
    result = check.evaluate({})
    
    assert result.ok is False
    assert result.severity.value == "amber"
    assert "pending" in result.detail.lower()
    assert result.evidence["coverage_percent"] == 0.0
    assert result.evidence["unknown"] > 0


def test_organism_check_red(clean_compliance_health):
    """Test organism check returns RED when blocking verification fails."""
    # Fail a blocking requirement
    update_requirement(
        requirement_id="sam_registration",
        status=RequirementStatus.FAIL,
        confidence=0.9,
    )
    
    check = ComplianceHealthCoverageCheck()
    result = check.evaluate({})
    
    assert result.ok is False
    assert result.severity.value == "red"
    assert "blocking" in result.detail.lower()
    assert result.evidence["blocking_failures"] == 1
    assert "SAM.gov Registration" in result.evidence["blocking_failed_names"]


def test_no_fake_passes(clean_compliance_health):
    """Test that system never fakes passes - UNKNOWN means UNKNOWN."""
    requirements = load_requirements()
    
    # All should start UNKNOWN
    assert all(r.status == RequirementStatus.UNKNOWN for r in requirements)
    assert all(r.confidence == 0.0 for r in requirements)
    
    # Assessment should be AMBER (missing required verifications)
    assessment = build_assessment("FB-test")
    assert assessment.overall_status == AssessmentStatus.AMBER
    assert assessment.verification_coverage_percent == 0.0


def test_blocking_vs_required_distinction():
    """Test distinction between blocking and required."""
    req_blocking = ComplianceHealthRequirement(
        requirement_id="blocking_req",
        name="Blocking Requirement",
        category="test",
        required=True,
        blocking=True,
        verification_source="test",
        status=RequirementStatus.FAIL,
    )
    
    req_required_not_blocking = ComplianceHealthRequirement(
        requirement_id="required_req",
        name="Required but Not Blocking",
        category="test",
        required=True,
        blocking=False,
        verification_source="test",
        status=RequirementStatus.FAIL,
    )
    
    assessment = ComplianceHealthAssessment(
        assessment_id="TEST-001",
        project_id="FB-test",
        overall_status=AssessmentStatus.GREEN,
        verification_coverage_percent=0.0,
        requirements=[req_blocking, req_required_not_blocking],
        missing_verifications=[],
        blocking_failures=[],
        generated_utc="2026-06-09T20:00:00Z",
    )
    
    status = assessment.compute_status()
    # Blocking failure → RED
    assert status == AssessmentStatus.RED
    
    # Only blocking req should be in blocking_failures
    assessment.blocking_failures = [r.requirement_id for r in assessment.requirements if r.blocking and r.status == RequirementStatus.FAIL]
    assert "blocking_req" in assessment.blocking_failures
    assert "required_req" not in assessment.blocking_failures

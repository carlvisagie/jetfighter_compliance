"""Tests for Remediation Memory Foundation — PATCH 13A-4A."""
import pytest
from pathlib import Path
from unittest.mock import patch

from services.remediation_memory import (
    record_outcome,
    record_lesson,
    record_implementation_method,
    load_outcomes,
    load_lessons,
    load_methods,
    get_outcome,
    get_project_outcomes,
    get_requirement_outcomes,
    ResolutionStatus,
    ComplexityLevel,
)
from services.remediation_memory.storage import get_outcome_summary


@pytest.fixture
def tmp_remediation_memory(tmp_path, monkeypatch):
    """Temporary remediation memory storage for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("services.remediation_memory.storage.DATA", data_dir)
    monkeypatch.setattr("services.config.DATA", data_dir)
    yield data_dir


def test_record_outcome_creates_file(tmp_remediation_memory):
    """Recording an outcome creates the outcomes.jsonl file."""
    outcome = record_outcome(
        project_id="FB-test-123",
        action_taken="Implemented MFA using Azure AD",
        implementation_method="azure_ad_mfa",
        resolution_status=ResolutionStatus.RESOLVED,
        category="access_control",
    )

    assert outcome.outcome_id.startswith("REM-")
    assert outcome.project_id == "FB-test-123"
    assert outcome.action_taken == "Implemented MFA using Azure AD"
    assert outcome.resolution_status == ResolutionStatus.RESOLVED
    assert outcome.category == "access_control"

    # Check file was created
    outcomes_file = tmp_remediation_memory / "remediation_memory" / "outcomes.jsonl"
    assert outcomes_file.exists()


def test_record_outcome_with_full_data(tmp_remediation_memory):
    """Recording outcome with all fields works correctly."""
    outcome = record_outcome(
        project_id="FB-test-456",
        requirement_id="cmmc.ac.1.001",
        gap_id="GAP-abc123",
        action_taken="Deployed password policy GPO",
        implementation_method="windows_gpo_password_policy",
        category="access_control",
        resolution_status=ResolutionStatus.RESOLVED,
        success_evidence="Policy verified via AD audit",
        blocking_factors=["vendor_delay", "policy_approval"],
        duration_days=7,
        cost_usd=1200.50,
        estimated_duration_days=5,
        estimated_cost_usd=1000.00,
        complexity=ComplexityLevel.MEDIUM,
        lessons_learned=["GPO takes 24h to replicate", "Test in staging first"],
        would_recommend=True,
        alternative_approaches=["Okta", "JumpCloud"],
        operator_email="operator@test.com",
        metadata={"vendor": "Microsoft"},
    )

    assert outcome.requirement_id == "cmmc.ac.1.001"
    assert outcome.gap_id == "GAP-abc123"
    assert outcome.duration_days == 7
    assert outcome.cost_usd == 1200.50
    assert outcome.complexity == ComplexityLevel.MEDIUM
    assert len(outcome.lessons_learned) == 2
    assert outcome.would_recommend is True
    assert len(outcome.blocking_factors) == 2


def test_load_outcomes_returns_recent_first(tmp_remediation_memory):
    """Loading outcomes returns most recent first."""
    record_outcome(
        project_id="FB-test-1",
        action_taken="First action",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
    )
    record_outcome(
        project_id="FB-test-2",
        action_taken="Second action",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
    )
    record_outcome(
        project_id="FB-test-3",
        action_taken="Third action",
        implementation_method="method3",
        resolution_status=ResolutionStatus.FAILED,
    )

    outcomes = load_outcomes()

    assert len(outcomes) == 3
    # Most recent first
    assert outcomes[0].action_taken == "Third action"
    assert outcomes[1].action_taken == "Second action"
    assert outcomes[2].action_taken == "First action"


def test_load_outcomes_with_filters(tmp_remediation_memory):
    """Loading outcomes with filters works correctly."""
    record_outcome(
        project_id="FB-test-1",
        action_taken="Access control fix",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
        category="access_control",
    )
    record_outcome(
        project_id="FB-test-2",
        action_taken="Documentation fix",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
        category="documentation",
    )
    record_outcome(
        project_id="FB-test-1",
        action_taken="Another access control fix",
        implementation_method="method3",
        resolution_status=ResolutionStatus.RESOLVED,
        category="access_control",
    )

    # Filter by project
    project_outcomes = load_outcomes(project_id="FB-test-1")
    assert len(project_outcomes) == 2

    # Filter by category
    access_outcomes = load_outcomes(category="access_control")
    assert len(access_outcomes) == 2

    # Filter by resolution status
    resolved_outcomes = load_outcomes(resolution_status=ResolutionStatus.RESOLVED)
    assert len(resolved_outcomes) == 2

    # Combine filters
    project_resolved = load_outcomes(
        project_id="FB-test-1", resolution_status=ResolutionStatus.RESOLVED
    )
    assert len(project_resolved) == 2


def test_get_outcome_by_id(tmp_remediation_memory):
    """Getting a specific outcome by ID works."""
    outcome1 = record_outcome(
        project_id="FB-test-1",
        action_taken="First action",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
    )

    outcome2 = record_outcome(
        project_id="FB-test-2",
        action_taken="Second action",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
    )

    # Get first outcome
    retrieved = get_outcome(outcome1.outcome_id)
    assert retrieved is not None
    assert retrieved.outcome_id == outcome1.outcome_id
    assert retrieved.action_taken == "First action"

    # Get second outcome
    retrieved2 = get_outcome(outcome2.outcome_id)
    assert retrieved2 is not None
    assert retrieved2.outcome_id == outcome2.outcome_id

    # Try non-existent
    missing = get_outcome("REM-nonexistent")
    assert missing is None


def test_get_project_outcomes(tmp_remediation_memory):
    """Getting outcomes for a specific project works."""
    record_outcome(
        project_id="FB-test-1",
        action_taken="Action 1",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
    )
    record_outcome(
        project_id="FB-test-2",
        action_taken="Action 2",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
    )
    record_outcome(
        project_id="FB-test-1",
        action_taken="Action 3",
        implementation_method="method3",
        resolution_status=ResolutionStatus.RESOLVED,
    )

    project1_outcomes = get_project_outcomes("FB-test-1")
    assert len(project1_outcomes) == 2
    assert all(o.project_id == "FB-test-1" for o in project1_outcomes)


def test_get_requirement_outcomes(tmp_remediation_memory):
    """Getting outcomes for a specific requirement works."""
    record_outcome(
        project_id="FB-test-1",
        requirement_id="cmmc.ac.1.001",
        action_taken="Action 1",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
    )
    record_outcome(
        project_id="FB-test-2",
        requirement_id="cmmc.ac.1.002",
        action_taken="Action 2",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
    )
    record_outcome(
        project_id="FB-test-3",
        requirement_id="cmmc.ac.1.001",
        action_taken="Action 3",
        implementation_method="method3",
        resolution_status=ResolutionStatus.FAILED,
    )

    req_outcomes = get_requirement_outcomes("cmmc.ac.1.001")
    assert len(req_outcomes) == 2
    assert all(o.requirement_id == "cmmc.ac.1.001" for o in req_outcomes)


def test_outcome_summary_statistics(tmp_remediation_memory):
    """Getting outcome summary computes correct statistics."""
    record_outcome(
        project_id="FB-test-1",
        action_taken="Action 1",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
        category="access_control",
        duration_days=5,
        cost_usd=1000.00,
    )
    record_outcome(
        project_id="FB-test-1",
        action_taken="Action 2",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
        category="access_control",
        duration_days=3,
        cost_usd=500.00,
    )
    record_outcome(
        project_id="FB-test-1",
        action_taken="Action 3",
        implementation_method="method3",
        resolution_status=ResolutionStatus.FAILED,
        category="documentation",
        blocking_factors=["budget", "vendor_delay"],
    )

    summary = get_outcome_summary(project_id="FB-test-1")

    assert summary.total_outcomes == 3
    assert summary.resolved_count == 1
    assert summary.partial_count == 1
    assert summary.failed_count == 1
    assert summary.total_cost_usd == 1500.00
    assert summary.total_duration_days == 8
    assert summary.avg_cost_usd == 750.00
    assert summary.avg_duration_days == 4.0
    assert summary.success_rate == pytest.approx(0.666, rel=0.01)
    assert summary.by_category["access_control"] == 2
    assert summary.by_category["documentation"] == 1
    assert len(summary.top_blocking_factors) == 2


def test_record_lesson_creates_file(tmp_remediation_memory):
    """Recording a lesson creates the lessons.jsonl file."""
    lesson = record_lesson(
        title="GPO replication takes time",
        description="Group Policy Objects take 24 hours to fully replicate across domain",
        category="access_control",
        what_worked="Testing in staging first",
        what_failed="Deploying to production immediately",
    )

    assert lesson.lesson_id.startswith("LESSON-")
    assert lesson.title == "GPO replication takes time"
    assert lesson.category == "access_control"

    # Check file was created
    lessons_file = tmp_remediation_memory / "remediation_memory" / "lessons.jsonl"
    assert lessons_file.exists()


def test_record_lesson_with_full_data(tmp_remediation_memory):
    """Recording lesson with all fields works correctly."""
    lesson = record_lesson(
        title="MFA deployment lessons",
        description="Learned from deploying MFA across multiple projects",
        category="access_control",
        requirement_ids=["cmmc.ac.1.001", "cmmc.ac.1.002"],
        outcome_ids=["REM-abc123", "REM-def456"],
        project_ids=["FB-test-1", "FB-test-2"],
        what_worked="Phased rollout with pilot group",
        what_failed="Deploying to everyone at once",
        recommended_approach="Start with IT team, then executives, then all users",
        avoid_approach="Big bang deployment without training",
        severity="high",
        operator_email="operator@test.com",
        metadata={"vendor": "Microsoft"},
    )

    assert len(lesson.requirement_ids) == 2
    assert len(lesson.outcome_ids) == 2
    assert len(lesson.project_ids) == 2
    assert lesson.severity == "high"
    assert lesson.recommended_approach is not None


def test_load_lessons_with_filters(tmp_remediation_memory):
    """Loading lessons with filters works correctly."""
    record_lesson(
        title="Lesson 1",
        description="Access control lesson",
        category="access_control",
        requirement_ids=["cmmc.ac.1.001"],
    )
    record_lesson(
        title="Lesson 2",
        description="Documentation lesson",
        category="documentation",
        requirement_ids=["cmmc.mp.2.001"],
    )
    record_lesson(
        title="Lesson 3",
        description="Another access control lesson",
        category="access_control",
        requirement_ids=["cmmc.ac.1.002"],
    )

    # Filter by category
    access_lessons = load_lessons(category="access_control")
    assert len(access_lessons) == 2

    # Filter by requirement
    req_lessons = load_lessons(requirement_id="cmmc.ac.1.001")
    assert len(req_lessons) == 1


def test_record_implementation_method_creates_file(tmp_remediation_memory):
    """Recording a method creates the methods.jsonl file."""
    method = record_implementation_method(
        name="azure_ad_mfa",
        description="Deploy MFA using Azure Active Directory",
        category="access_control",
        steps=["Enable Azure AD Premium", "Configure MFA settings", "Test with pilot group"],
        tools_required=["Azure AD Premium P1"],
        typical_duration_days=7,
        typical_cost_usd=2000.00,
        complexity=ComplexityLevel.MEDIUM,
    )

    assert method.method_id.startswith("METHOD-")
    assert method.name == "azure_ad_mfa"
    assert method.complexity == ComplexityLevel.MEDIUM
    assert len(method.steps) == 3

    # Check file was created
    methods_file = tmp_remediation_memory / "remediation_memory" / "methods.jsonl"
    assert methods_file.exists()


def test_load_methods_with_filters(tmp_remediation_memory):
    """Loading methods with filters works correctly."""
    record_implementation_method(
        name="method1",
        description="Access control method",
        category="access_control",
        requirement_ids=["cmmc.ac.1.001"],
    )
    record_implementation_method(
        name="method2",
        description="Documentation method",
        category="documentation",
        requirement_ids=["cmmc.mp.2.001"],
    )
    record_implementation_method(
        name="method3",
        description="Another access control method",
        category="access_control",
        requirement_ids=["cmmc.ac.1.002"],
    )

    # Filter by category
    access_methods = load_methods(category="access_control")
    assert len(access_methods) == 2

    # Filter by requirement
    req_methods = load_methods(requirement_id="cmmc.ac.1.001")
    assert len(req_methods) == 1


def test_outcome_links_to_central_memory(tmp_remediation_memory):
    """Recording an outcome attempts to link to central memory."""
    with patch("services.remediation_memory.bridge.link_outcome_to_memory") as mock_link:
        outcome = record_outcome(
            project_id="FB-test-123",
            action_taken="Test action",
            implementation_method="test_method",
            resolution_status=ResolutionStatus.RESOLVED,
        )

        # Should attempt to link (even if it fails due to missing entity)
        mock_link.assert_called_once()


def test_lesson_links_to_central_memory(tmp_remediation_memory):
    """Recording a lesson attempts to link to central memory."""
    with patch("services.remediation_memory.bridge.link_lesson_to_memory") as mock_link:
        lesson = record_lesson(
            title="Test lesson",
            description="Test lesson description",
            project_ids=["FB-test-123"],
        )

        mock_link.assert_called_once()


def test_outcome_append_only_never_deletes(tmp_remediation_memory):
    """Outcomes are append-only and never deleted."""
    # Record 3 outcomes
    o1 = record_outcome(
        project_id="FB-test-1",
        action_taken="Action 1",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
    )
    o2 = record_outcome(
        project_id="FB-test-2",
        action_taken="Action 2",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
    )
    o3 = record_outcome(
        project_id="FB-test-3",
        action_taken="Action 3",
        implementation_method="method3",
        resolution_status=ResolutionStatus.FAILED,
    )

    # Load all
    outcomes = load_outcomes()
    assert len(outcomes) == 3

    # Try to "delete" by filtering (outcomes remain in file)
    filtered = load_outcomes(project_id="FB-test-1")
    assert len(filtered) == 1

    # Original file still has all 3
    all_outcomes = load_outcomes()
    assert len(all_outcomes) == 3


def test_malformed_outcome_skipped_gracefully(tmp_remediation_memory):
    """Malformed outcome records are skipped without breaking load."""
    # Write a valid outcome
    record_outcome(
        project_id="FB-test-1",
        action_taken="Valid action",
        implementation_method="method1",
        resolution_status=ResolutionStatus.RESOLVED,
    )

    # Manually inject a malformed record
    outcomes_file = tmp_remediation_memory / "remediation_memory" / "outcomes.jsonl"
    with outcomes_file.open("a") as f:
        f.write('{"invalid": "json", "missing_required_fields": true}\n')

    # Write another valid outcome
    record_outcome(
        project_id="FB-test-2",
        action_taken="Another valid action",
        implementation_method="method2",
        resolution_status=ResolutionStatus.PARTIAL,
    )

    # Should still load the valid outcomes
    outcomes = load_outcomes()
    assert len(outcomes) == 2
    assert all(o.project_id in ["FB-test-1", "FB-test-2"] for o in outcomes)


def test_empty_outcomes_returns_empty_list(tmp_remediation_memory):
    """Loading outcomes when file doesn't exist returns empty list."""
    outcomes = load_outcomes()
    assert outcomes == []


def test_empty_lessons_returns_empty_list(tmp_remediation_memory):
    """Loading lessons when file doesn't exist returns empty list."""
    lessons = load_lessons()
    assert lessons == []


def test_empty_methods_returns_empty_list(tmp_remediation_memory):
    """Loading methods when file doesn't exist returns empty list."""
    methods = load_methods()
    assert methods == []

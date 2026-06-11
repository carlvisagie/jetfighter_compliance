"""PATCH 13A-4D: Project Observability Foundation tests.

Tests for the project observability endpoint that enables operators to
answer "What happened to this customer?" via API without SSH, filesystem
inspection, or log scraping.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_project_dir(tmp_path):
    """Create a mock project directory structure."""
    project_id = "P-test-observability"
    project_root = tmp_path / "projects" / project_id
    project_root.mkdir(parents=True)
    
    # Create meta.json
    meta = {
        "project_id": project_id,
        "created_utc": "2026-06-11T10:00:00Z",
        "status": "active",
        "canonical_intake_id": "FB-test-intake",
        "customer": {"email": "test@example.com", "name": "Test Corp"},
    }
    (project_root / "meta.json").write_text(json.dumps(meta))
    
    # Create communications/intake.json
    comm_dir = project_root / "communications"
    comm_dir.mkdir()
    intake_meta = {
        "canonical_intake_id": "FB-test-intake",
        "company": "Test Corp",
    }
    (comm_dir / "intake.json").write_text(json.dumps(intake_meta))
    
    return project_root, project_id


@pytest.fixture
def mock_ei_dir(mock_project_dir):
    """Add Evidence Intelligence artifacts."""
    project_root, project_id = mock_project_dir
    ei_dir = project_root / "evidence_intelligence"
    ei_dir.mkdir()
    
    # Create profile.json
    profile = {
        "project_id": project_id,
        "document_inventory": [
            {"filename": "contract.pdf", "document_type": "contract"},
            {"filename": "certificate.pdf", "document_type": "certificate"},
        ],
        "evidence_coverage": {"contracts": True, "certificates": True},
        "updated_utc": "2026-06-11T10:05:00Z",
    }
    (ei_dir / "profile.json").write_text(json.dumps(profile))
    
    # Create classifications.jsonl
    classifications = [
        {"filename": "contract.pdf", "classification": "contract", "recorded_utc": "2026-06-11T10:02:00Z"},
        {"filename": "certificate.pdf", "classification": "certificate", "recorded_utc": "2026-06-11T10:03:00Z"},
    ]
    with (ei_dir / "classifications.jsonl").open("w") as f:
        for c in classifications:
            f.write(json.dumps(c) + "\n")
    
    # Create entities.jsonl
    entities = [
        {"entity_type": "company", "value": "Test Corp", "recorded_utc": "2026-06-11T10:03:00Z"},
    ]
    with (ei_dir / "entities.jsonl").open("w") as f:
        for e in entities:
            f.write(json.dumps(e) + "\n")
    
    return ei_dir


@pytest.fixture
def mock_cognition_dir(mock_project_dir):
    """Add Cognition artifacts."""
    project_root, project_id = mock_project_dir
    cognition_dir = project_root / "cognition"
    cognition_dir.mkdir()
    
    # Create cognition_summary.json
    summary = {
        "project_id": project_id,
        "started_utc": "2026-06-11T10:10:00Z",
        "completed_utc": "2026-06-11T10:15:00Z",
        "generated_documents": [
            {"name": "compliance_report.pdf", "type": "report"},
        ],
    }
    (cognition_dir / "cognition_summary.json").write_text(json.dumps(summary))
    
    # Create validation_report.json
    validation = {
        "generated_utc": "2026-06-11T10:14:00Z",
        "human_review_items": [
            {"item": "review_clause_52", "severity": "medium"},
        ],
        "safety_warnings": [],
        "confidence_score": 0.85,
    }
    (cognition_dir / "validation_report.json").write_text(json.dumps(validation))
    
    # Create next_actions.json
    next_actions = [
        {"action": "review_clause", "priority": "high"},
    ]
    (cognition_dir / "next_actions.json").write_text(json.dumps(next_actions))
    
    return cognition_dir


# --- Test: Basic observability retrieval ---

def test_get_project_observability_returns_all_sections(tmp_path, mock_project_dir):
    """Observability returns all required sections."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    assert result["ok"] is True
    assert result["project_id"] == project_id
    assert "kickoff" in result
    assert "evidence_intelligence" in result
    assert "cognition" in result
    assert "validation" in result
    assert "compliance_health" in result
    assert "timeline" in result
    assert "summary" in result


def test_get_project_observability_missing_project():
    """Returns error for non-existent project."""
    from services.project_observability import get_project_observability
    
    with patch("services.project_observability._projects_root") as mock_root:
        mock_root.return_value = Path("/nonexistent")
        with patch("services.project_observability._intakes_root") as mock_intakes:
            mock_intakes.return_value = Path("/nonexistent/intakes")
            result = get_project_observability("P-does-not-exist")
    
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


def test_get_project_observability_invalid_project_id():
    """Rejects malformed project_id."""
    from services.project_observability import get_project_observability
    
    result = get_project_observability("../etc/passwd")
    assert result["ok"] is False
    assert "invalid" in result["error"].lower()
    
    result = get_project_observability("project/with/slashes")
    assert result["ok"] is False


def test_get_project_observability_empty_project_id():
    """Rejects empty project_id."""
    from services.project_observability import get_project_observability
    
    result = get_project_observability("")
    assert result["ok"] is False
    assert "required" in result["error"].lower()


# --- Test: Kickoff state ---

def test_kickoff_state_from_intake_record(tmp_path, mock_project_dir):
    """Kickoff state populated from intake record."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    intake_record = {
        "project_kickoff_completed": True,
        "project_kickoff_at_utc": "2026-06-11T10:00:00Z",
        "auto_kickoff_reason": "validation_mode",
        "custody_status": "verified_complete",
    }
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value=intake_record):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    kickoff = result["kickoff"]
    assert kickoff["project_kickoff_completed"] is True
    assert kickoff["project_kickoff_at_utc"] == "2026-06-11T10:00:00Z"
    assert kickoff["auto_kickoff_reason"] == "validation_mode"


# --- Test: Evidence Intelligence state ---

def test_ei_state_completed(tmp_path, mock_project_dir, mock_ei_dir):
    """Evidence Intelligence state shows completed."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    ei = result["evidence_intelligence"]
    assert ei["status"] == "COMPLETED"
    assert ei["profile_exists"] is True
    assert ei["ei_total"] == 2
    assert ei["ei_success_count"] == 2
    assert ei["entities_count"] == 1


def test_ei_state_not_started(tmp_path, mock_project_dir):
    """Evidence Intelligence shows NOT_STARTED when no EI directory."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    ei = result["evidence_intelligence"]
    assert ei["status"] == "NOT_STARTED"


def test_ei_state_partial_with_failures(tmp_path, mock_project_dir):
    """Evidence Intelligence shows PARTIAL when some files fail."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    ei_dir = project_root / "evidence_intelligence"
    ei_dir.mkdir()
    
    # Create classifications with one failure
    classifications = [
        {"filename": "good.pdf", "classification": "contract", "recorded_utc": "2026-06-11T10:02:00Z"},
        {"filename": "bad.pdf", "status": "error", "error": "parse failed", "recorded_utc": "2026-06-11T10:03:00Z"},
    ]
    with (ei_dir / "classifications.jsonl").open("w") as f:
        for c in classifications:
            f.write(json.dumps(c) + "\n")
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    ei = result["evidence_intelligence"]
    assert ei["status"] == "PARTIAL"
    assert ei["ei_success_count"] == 1
    assert ei["ei_failed_count"] == 1


# --- Test: Cognition state ---

def test_cognition_state_completed(tmp_path, mock_project_dir, mock_cognition_dir):
    """Cognition state shows completed with summary."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    cog = result["cognition"]
    assert cog["status"] == "COMPLETED"
    assert cog["cognition_summary_present"] is True
    assert cog["validation_report_present"] is True
    assert cog["generated_documents_count"] == 1
    assert cog["next_actions_count"] == 1


def test_cognition_state_not_started(tmp_path, mock_project_dir):
    """Cognition shows NOT_STARTED when no cognition directory."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    cog = result["cognition"]
    assert cog["status"] == "NOT_STARTED"


# --- Test: Validation state ---

def test_validation_state_completed(tmp_path, mock_project_dir, mock_cognition_dir):
    """Validation state shows completed with report."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    val = result["validation"]
    assert val["status"] == "COMPLETED"
    assert val["validation_report_present"] is True
    assert val["human_review_items_count"] == 1
    assert val["confidence_score"] == 0.85


# --- Test: Compliance Health state ---

def test_compliance_health_state_present(tmp_path, mock_project_dir):
    """Compliance Health shows assessment when present."""
    from services.project_observability import get_project_observability
    from services.compliance_health.schemas import ComplianceHealthAssessment
    
    project_root, project_id = mock_project_dir
    
    mock_assessment = MagicMock(spec=ComplianceHealthAssessment)
    mock_assessment.assessment_id = "ASSESS-test123"
    mock_assessment.verification_coverage_percent = 75.0
    mock_assessment.overall_status = "GREEN"
    mock_assessment.missing_verifications = ["req1"]
    mock_assessment.blocking_failures = []
    mock_assessment.generated_utc = "2026-06-11T10:20:00Z"
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=mock_assessment):
                    result = get_project_observability(project_id)
    
    ch = result["compliance_health"]
    assert ch["assessment_present"] is True
    assert ch["assessment_id"] == "ASSESS-test123"
    assert ch["coverage_percent"] == 75.0
    assert ch["overall_status"] == "GREEN"


def test_compliance_health_state_missing(tmp_path, mock_project_dir):
    """Compliance Health shows not present when no assessment."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    ch = result["compliance_health"]
    assert ch["assessment_present"] is False


# --- Test: Timeline events ---

def test_timeline_events_populated(tmp_path, mock_project_dir):
    """Timeline events populated from telemetry."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    # Create telemetry file
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    telemetry = [
        {"event_type": "post_kickoff_intelligence_started", "timestamp": "2026-06-11T10:01:00Z", "metadata": {"project_id": project_id}},
        {"event_type": "evidence_intelligence_completed", "timestamp": "2026-06-11T10:05:00Z", "metadata": {"project_id": project_id}},
        {"event_type": "cognition_completed", "timestamp": "2026-06-11T10:15:00Z", "metadata": {"project_id": project_id}},
    ]
    with (memory_dir / "telemetry.jsonl").open("w") as f:
        for t in telemetry:
            f.write(json.dumps(t) + "\n")
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.durable_storage.active_data_root", return_value=tmp_path):
                with patch("services.intake.storage.load_intake_record", return_value={}):
                    with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                        result = get_project_observability(project_id)
    
    timeline = result["timeline"]
    assert len(timeline) == 3
    assert timeline[0]["event_type"] == "post_kickoff_intelligence_started"
    assert timeline[2]["event_type"] == "cognition_completed"


# --- Test: Summary field ---

def test_summary_aggregates_status(tmp_path, mock_project_dir, mock_ei_dir, mock_cognition_dir):
    """Summary field aggregates all status values."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    intake_record = {
        "project_kickoff_completed": True,
    }
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value=intake_record):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    summary = result["summary"]
    assert summary["project_exists"] is True
    assert summary["kickoff_completed"] is True
    assert summary["ei_status"] == "COMPLETED"
    assert summary["cognition_status"] == "COMPLETED"
    assert summary["validation_status"] == "COMPLETED"


# --- Test: Missing artifacts handled gracefully ---

def test_missing_artifacts_handled_gracefully(tmp_path):
    """Missing artifacts don't cause crashes."""
    from services.project_observability import get_project_observability
    
    project_id = "P-minimal"
    project_root = tmp_path / "projects" / project_id
    project_root.mkdir(parents=True)
    
    # Only create meta.json, nothing else
    (project_root / "meta.json").write_text(json.dumps({"project_id": project_id}))
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    result = get_project_observability(project_id)
    
    assert result["ok"] is True
    assert result["evidence_intelligence"]["status"] == "NOT_STARTED"
    assert result["cognition"]["status"] == "NOT_STARTED"
    assert result["validation"]["status"] == "NOT_STARTED"


# --- Test: No customer-facing behavior changes ---

def test_observability_does_not_modify_state(tmp_path, mock_project_dir, mock_ei_dir, mock_cognition_dir):
    """Observability is read-only and doesn't modify project state."""
    from services.project_observability import get_project_observability
    
    project_root, project_id = mock_project_dir
    
    # Record file modification times before
    meta_mtime_before = (project_root / "meta.json").stat().st_mtime
    
    with patch("services.project_observability._projects_root", return_value=tmp_path / "projects"):
        with patch("services.project_observability._intakes_root", return_value=tmp_path / "intakes"):
            with patch("services.intake.storage.load_intake_record", return_value={}):
                with patch("services.compliance_health.assessment.get_assessment", return_value=None):
                    # Call multiple times
                    get_project_observability(project_id)
                    get_project_observability(project_id)
                    get_project_observability(project_id)
    
    # Verify no files modified
    meta_mtime_after = (project_root / "meta.json").stat().st_mtime
    assert meta_mtime_before == meta_mtime_after

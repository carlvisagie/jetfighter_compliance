"""Tests for validation mode and auto-kickoff."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_intake_record() -> Dict[str, Any]:
    """Base intake record for testing."""
    return {
        "intake_id": "FB-test-12345",
        "email": "test@example.com",
        "company": "Test Corp",
        "custody_status": "verified_complete",
        "files": [{"name": "test.pdf"}],
        "file_count": 1,
    }


def test_is_validation_project_with_validation_flag(sample_intake_record):
    """Validation project flag enables validation mode."""
    from services.intake.validation_mode import is_validation_project
    
    sample_intake_record["validation_project"] = True
    assert is_validation_project(sample_intake_record) is True


def test_is_validation_project_with_founding_pilot_flag(sample_intake_record):
    """Founding pilot flag enables validation mode."""
    from services.intake.validation_mode import is_validation_project
    
    sample_intake_record["founding_pilot"] = True
    assert is_validation_project(sample_intake_record) is True


def test_is_validation_project_with_test_intake_id(sample_intake_record):
    """Test intake ID pattern enables validation mode."""
    from services.intake.validation_mode import is_validation_project
    
    sample_intake_record["intake_id"] = "FB-test-abcd1234"
    assert is_validation_project(sample_intake_record) is True


def test_is_validation_project_commercial_intake(sample_intake_record):
    """Commercial intake without flags requires payment."""
    from services.intake.validation_mode import is_validation_project
    
    sample_intake_record["intake_id"] = "FB-comm-12345"
    assert is_validation_project(sample_intake_record) is False


def test_is_auto_kickoff_eligible_payment_confirmed(sample_intake_record):
    """Payment confirmation enables auto-kickoff."""
    from services.intake.validation_mode import is_auto_kickoff_eligible
    
    sample_intake_record["payment"] = {"payment_received_at_utc": "2026-06-10T12:00:00Z"}
    eligible, reason = is_auto_kickoff_eligible(sample_intake_record)
    
    assert eligible is True
    assert reason == "payment_confirmed"


def test_is_auto_kickoff_eligible_validation_mode(sample_intake_record):
    """Validation mode enables auto-kickoff without payment."""
    from services.intake.validation_mode import is_auto_kickoff_eligible
    
    sample_intake_record["validation_project"] = True
    eligible, reason = is_auto_kickoff_eligible(sample_intake_record)
    
    assert eligible is True
    assert reason == "validation_mode"


def test_is_auto_kickoff_eligible_no_payment_no_validation(sample_intake_record):
    """Commercial intake without payment blocks auto-kickoff."""
    from services.intake.validation_mode import is_auto_kickoff_eligible
    
    sample_intake_record["intake_id"] = "FB-comm-12345"
    eligible, reason = is_auto_kickoff_eligible(sample_intake_record)
    
    assert eligible is False
    assert reason == "payment_required"


def test_should_bypass_payment_gate_validation_project(sample_intake_record):
    """Validation project bypasses payment gate."""
    from services.intake.validation_mode import should_bypass_payment_gate
    
    sample_intake_record["validation_project"] = True
    assert should_bypass_payment_gate(sample_intake_record) is True


def test_should_bypass_payment_gate_commercial_project(sample_intake_record):
    """Commercial project requires payment gate."""
    from services.intake.validation_mode import should_bypass_payment_gate
    
    sample_intake_record["intake_id"] = "FB-comm-12345"
    assert should_bypass_payment_gate(sample_intake_record) is False


def test_auto_kickoff_skips_non_verified_complete(tmp_path, sample_intake_record):
    """Auto-kickoff only triggers on verified_complete."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "partial_upload"
    sample_intake_record["validation_project"] = True
    
    with patch("services.intake.intake.logger") as mock_logger:
        _trigger_auto_kickoff_if_eligible("FB-test-12345", sample_intake_record)
        
        # Should return early, no kickoff attempt
        assert not sample_intake_record.get("project_kickoff_completed")


def test_auto_kickoff_prevents_duplicates(tmp_path, sample_intake_record):
    """Auto-kickoff prevents duplicate project creation."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["validation_project"] = True
    sample_intake_record["project_kickoff_completed"] = True
    
    with patch("services.intake.intake.logger") as mock_logger:
        _trigger_auto_kickoff_if_eligible("FB-test-12345", sample_intake_record)
        
        # Should return early without calling kickoff
        mock_logger.info.assert_not_called()


def test_auto_kickoff_validation_mode_audit_trail(tmp_path, sample_intake_record):
    """Auto-kickoff logs payment bypass for validation projects."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["validation_project"] = True
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        with patch("services.intake.intake.logger") as mock_logger:
            mock_kickoff.return_value = {"project_id": "test-project-123"}
            
            _trigger_auto_kickoff_if_eligible("FB-test-12345", sample_intake_record)
            
            # Check audit trail logging
            mock_logger.warning.assert_called()
            warning_call = str(mock_logger.warning.call_args)
            assert "bypassing payment gate" in warning_call.lower()
            assert "validation_project=true" in warning_call.lower()
            
            # Check operator note contains PAYMENT_OVERRIDE
            mock_kickoff.assert_called_once()
            call_kwargs = mock_kickoff.call_args.kwargs
            assert "PAYMENT_OVERRIDE" in call_kwargs["operator_note"]
            assert "validation mode" in call_kwargs["operator_note"].lower()


def test_auto_kickoff_payment_confirmed_no_bypass(tmp_path, sample_intake_record):
    """Auto-kickoff with payment does not log as bypass."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["intake_id"] = "FB-comm-12345"  # Commercial intake, not test
    sample_intake_record["payment"] = {"payment_received_at_utc": "2026-06-10T12:00:00Z"}
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        with patch("services.intake.intake.logger") as mock_logger:
            mock_kickoff.return_value = {"project_id": "test-project-123"}
            
            _trigger_auto_kickoff_if_eligible("FB-comm-12345", sample_intake_record)
            
            # Should use info logging, not warning
            mock_logger.info.assert_called()
            info_call = str(mock_logger.info.call_args_list)
            assert "completed" in info_call.lower()
            assert "payment_confirmed" in info_call.lower()
            
            # Operator note should NOT contain PAYMENT_OVERRIDE
            mock_kickoff.assert_called_once()
            call_kwargs = mock_kickoff.call_args.kwargs
            assert "PAYMENT_OVERRIDE" not in call_kwargs["operator_note"]


def test_auto_kickoff_founding_pilot_bypass(tmp_path, sample_intake_record):
    """Founding pilot flag enables auto-kickoff bypass."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["founding_pilot"] = True
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        with patch("services.intake.intake.logger"):
            mock_kickoff.return_value = {"project_id": "test-project-123"}
            
            _trigger_auto_kickoff_if_eligible("FB-test-12345", sample_intake_record)
            
            # Check operator note mentions founding_pilot
            mock_kickoff.assert_called_once()
            call_kwargs = mock_kickoff.call_args.kwargs
            assert "founding_pilot=true" in call_kwargs["operator_note"]


def test_auto_kickoff_marks_completion(tmp_path, sample_intake_record):
    """Auto-kickoff updates record with completion status."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["validation_project"] = True
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        with patch("services.intake.intake.logger"):
            mock_kickoff.return_value = {"project_id": "test-project-123"}
            
            _trigger_auto_kickoff_if_eligible("FB-test-12345", sample_intake_record)
            
            # Check record updated
            assert sample_intake_record["project_kickoff_completed"] is True
            assert "project_kickoff_at_utc" in sample_intake_record
            assert sample_intake_record["auto_kickoff_reason"] == "validation_mode"


def test_auto_kickoff_failure_handling(tmp_path, sample_intake_record):
    """Auto-kickoff logs errors without breaking intake pipeline."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["validation_project"] = True
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        with patch("services.intake.intake.logger") as mock_logger:
            mock_kickoff.side_effect = Exception("Kickoff failed")
            
            # Should not raise exception
            _trigger_auto_kickoff_if_eligible("FB-test-12345", sample_intake_record)
            
            # Should log error
            mock_logger.error.assert_called()
            error_call = str(mock_logger.error.call_args)
            assert "auto-kickoff failed" in error_call.lower()


def test_post_kickoff_intelligence_runs_evidence_intelligence(tmp_path):
    """Post-kickoff intelligence processes evidence files."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "test-project-123"
    intake_id = "FB-test-12345"
    
    # Create fake evidence directory
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "test.pdf").write_text("fake pdf content")
    
    with patch("services.intake.kickoff.PROJECTS", tmp_path / "projects"):
        with patch("services.evidence_intelligence.process_evidence_upload") as mock_ei:
            with patch("services.cognition.storage.run_cognition_safely") as mock_cog:
                with patch("services.intake.kickoff.logger"):
                    _run_post_kickoff_intelligence(project_id, intake_id)
                    
                    # Evidence Intelligence should run
                    mock_ei.assert_called()
                    
                    # Cognition should run
                    mock_cog.assert_called_once_with(project_id)


def test_post_kickoff_intelligence_handles_ei_errors(tmp_path):
    """Post-kickoff intelligence continues after Evidence Intelligence errors."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "test-project-123"
    intake_id = "FB-test-12345"
    
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "test.pdf").write_text("fake pdf content")
    
    with patch("services.intake.kickoff.PROJECTS", tmp_path / "projects"):
        with patch("services.evidence_intelligence.process_evidence_upload") as mock_ei:
            with patch("services.cognition.storage.run_cognition_safely") as mock_cog:
                with patch("services.intake.kickoff.logger") as mock_logger:
                    mock_ei.side_effect = Exception("EI failed")
                    
                    _run_post_kickoff_intelligence(project_id, intake_id)
                    
                    # Should log warning but continue
                    mock_logger.warning.assert_called()
                    
                    # Cognition should still run
                    mock_cog.assert_called_once()


def test_post_kickoff_intelligence_handles_cognition_errors(tmp_path):
    """Post-kickoff intelligence logs cognition errors gracefully."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "test-project-123"
    intake_id = "FB-test-12345"
    
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    
    with patch("services.intake.kickoff.PROJECTS", tmp_path / "projects"):
        with patch("services.cognition.storage.run_cognition_safely") as mock_cog:
            with patch("services.intake.kickoff.logger") as mock_logger:
                mock_cog.side_effect = Exception("Cognition failed")
                
                # Should not raise exception
                _run_post_kickoff_intelligence(project_id, intake_id)
                
                # Should log warning
                mock_logger.warning.assert_called()
                warning_call = str(mock_logger.warning.call_args)
                assert "cognition failed" in warning_call.lower()


def test_commercial_flow_unchanged(tmp_path, sample_intake_record):
    """Commercial projects still require payment confirmation."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["intake_id"] = "FB-comm-12345"  # Commercial intake
    # No payment, no validation flags
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        with patch("services.intake.intake.logger") as mock_logger:
            _trigger_auto_kickoff_if_eligible("FB-comm-12345", sample_intake_record)
            
            # Should not call kickoff
            mock_kickoff.assert_not_called()
            
            # Should log skipped
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("payment_required" in call.lower() for call in info_calls)

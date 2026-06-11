"""PATCH 13A-4F: Timeline Normalization Tests.

Tests that all 14 canonical lifecycle events are:
1. Emitted with correct names
2. Visible in timeline
3. Visible in observability
4. Not duplicated
5. Backward compatible with aliases
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from services.intake.telemetry import (
    emit_lifecycle_event,
    LIFECYCLE_EVENTS,
)


class TestLifecycleEventsRegistry:
    """Test that all 14 canonical events are registered."""
    
    def test_all_14_events_registered(self):
        """Verify all required lifecycle events are in LIFECYCLE_EVENTS."""
        required = {
            "upload_started",
            "upload_completed",
            "verified_complete",
            "external_verification_started",
            "external_verification_completed",
            "project_kickoff_started",
            "project_kickoff_completed",
            "evidence_intelligence_started",
            "evidence_intelligence_completed",
            "cognition_started",
            "cognition_completed",
            "validation_started",
            "validation_completed",
            "compliance_health_completed",
        }
        assert required == LIFECYCLE_EVENTS
        assert len(LIFECYCLE_EVENTS) == 14


class TestEmitLifecycleEvent:
    """Test emit_lifecycle_event function."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_emits_canonical_event(self, mock_emit, mock_mode):
        """emit_lifecycle_event emits the canonical event name."""
        emit_lifecycle_event(
            "upload_started",
            message="Test upload",
            metadata={"intake_id": "FB-test"},
        )
        
        # Should emit at least the canonical event
        calls = [c for c in mock_emit.call_args_list if c[0][1] == "upload_started"]
        assert len(calls) == 1
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_emits_alias_for_backward_compatibility(self, mock_emit, mock_mode):
        """emit_lifecycle_event emits alias alongside canonical name."""
        emit_lifecycle_event(
            "upload_started",
            message="Test upload",
            metadata={"intake_id": "FB-test"},
            alias="pilot_upload_started",
        )
        
        # Should emit both canonical and alias
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        assert "upload_started" in event_types
        assert "pilot_upload_started" in event_types
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_no_duplicate_when_alias_same_as_canonical(self, mock_emit, mock_mode):
        """When alias equals canonical, only emit once."""
        emit_lifecycle_event(
            "upload_started",
            message="Test upload",
            metadata={"intake_id": "FB-test"},
            alias="upload_started",  # Same as canonical
        )
        
        # Should only emit once
        upload_calls = [c for c in mock_emit.call_args_list if c[0][1] == "upload_started"]
        assert len(upload_calls) == 1
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_lifecycle_event_metadata_includes_marker(self, mock_emit, mock_mode):
        """lifecycle_event metadata includes lifecycle_event=True marker."""
        emit_lifecycle_event(
            "verified_complete",
            message="Test verified",
            metadata={"intake_id": "FB-test"},
        )
        
        call = mock_emit.call_args_list[0]
        assert call[1]["metadata"]["lifecycle_event"] is True
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=False)
    @patch("services.organism_observability.emit.organism_emit")
    def test_skips_when_not_intake_mode(self, mock_emit, mock_mode):
        """emit_lifecycle_event returns True but doesn't emit when not in intake mode."""
        result = emit_lifecycle_event(
            "upload_started",
            message="Test upload",
            metadata={"intake_id": "FB-test"},
        )
        
        assert result is True
        mock_emit.assert_not_called()


class TestUploadEvents:
    """Test upload_started and upload_completed events."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_upload_completed_triggers_acquisition_event(self, mock_emit, mock_mode):
        """upload_completed also triggers acquisition organism event."""
        emit_lifecycle_event(
            "upload_completed",
            message="Test upload complete",
            metadata={"intake_id": "FB-test"},
        )
        
        # Should also emit acquisition conversion event
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        assert "upload_completed" in event_types
        assert "upload_conversion_completed" in event_types


class TestIntakeIntegration:
    """Test lifecycle events emitted by intake pipeline."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_apply_custody_status_emits_verified_complete(self, mock_emit, mock_mode, tmp_path):
        """_apply_custody_status emits verified_complete when status is verified_complete."""
        from services.intake.intake import _apply_custody_status
        
        record = {"intake_id": "FB-test"}
        integrity = {
            "expected_file_count": 1,
            "received_file_count": 1,
            "persisted_file_count": 1,
            "verified_file_count": 1,
            "rejected_file_count": 0,
        }
        
        _apply_custody_status(record, integrity, durability_ok=True)
        
        # Should emit verified_complete
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        assert "verified_complete" in event_types


class TestKickoffEvents:
    """Test kickoff lifecycle events."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_emit_lifecycle_event_for_kickoff_started(self, mock_emit, mock_mode):
        """emit_lifecycle_event correctly emits project_kickoff_started."""
        from services.intake.telemetry import emit_lifecycle_event
        
        emit_lifecycle_event(
            "project_kickoff_started",
            message="Starting project kickoff for FB-test123",
            metadata={"intake_id": "FB-test123"},
        )
        
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        assert "project_kickoff_started" in event_types
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_emit_lifecycle_event_for_kickoff_completed(self, mock_emit, mock_mode):
        """emit_lifecycle_event correctly emits project_kickoff_completed with alias."""
        from services.intake.telemetry import emit_lifecycle_event
        
        emit_lifecycle_event(
            "project_kickoff_completed",
            message="FB-test123 → P-test123",
            metadata={"intake_id": "FB-test123", "project_id": "P-test123"},
            alias="intake_kickoff_project",
        )
        
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        assert "project_kickoff_completed" in event_types
        assert "intake_kickoff_project" in event_types


class TestExternalVerificationEvents:
    """Test external verification lifecycle events."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_verify_emits_started_and_completed(self, mock_emit, mock_mode, tmp_path):
        """verify_contractor_identity emits started and completed events."""
        from services.external_verification.schemas import VerificationStatus
        
        data_dir = tmp_path / "data"
        intakes_dir = data_dir / "intakes"
        ext_ver_dir = data_dir / "external_verification"
        
        project_id = "FB-test123"
        intake_dir = intakes_dir / project_id
        intake_dir.mkdir(parents=True, exist_ok=True)
        ext_ver_dir.mkdir(parents=True, exist_ok=True)
        
        with patch("services.external_verification.identity._extract_claimed_identity") as mock_extract, \
             patch("services.external_verification.identity.verify_sam_registration") as mock_sam, \
             patch("services.external_verification.identity.save_verification"), \
             patch("services.external_verification.identity._feed_compliance_health"):
            
            mock_extract.return_value = {"legal_name": None, "uei": None, "cage": None}
            mock_sam.return_value = {
                "registration_status": VerificationStatus.UNKNOWN,
                "uei_status": VerificationStatus.UNKNOWN,
                "cage_status": VerificationStatus.UNKNOWN,
                "source_checked_utc": "2026-01-01T00:00:00Z",
                "sam_record": None,
            }
            
            from services.external_verification.identity import verify_contractor_identity
            verify_contractor_identity(project_id, force_refresh=True)
            
            event_types = [c[0][1] for c in mock_emit.call_args_list]
            assert "external_verification_started" in event_types
            assert "external_verification_completed" in event_types


class TestCognitionValidationEvents:
    """Test cognition and validation lifecycle events."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_cognition_emits_validation_events(self, mock_emit, mock_mode, tmp_path):
        """run_cognition_safely emits validation_started and validation_completed."""
        data_dir = tmp_path / "data"
        projects_dir = data_dir / "projects"
        
        project_id = "P-test123"
        project_dir = projects_dir / project_id
        cognition_dir = project_dir / "cognition"
        evidence_dir = project_dir / "evidence"
        intel_dir = project_dir / "evidence_intelligence"
        
        cognition_dir.mkdir(parents=True, exist_ok=True)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        intel_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal profile
        (intel_dir / "profile.json").write_text("{}", encoding="utf-8")
        (intel_dir / "gaps.json").write_text('{"gaps": []}', encoding="utf-8")
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir):
            from services.cognition.storage import run_cognition_safely
            run_cognition_safely(project_id)
            
            event_types = [c[0][1] for c in mock_emit.call_args_list]
            assert "validation_started" in event_types
            assert "validation_completed" in event_types


class TestComplianceHealthEvents:
    """Test compliance health lifecycle events."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_build_assessment_emits_completed(self, mock_emit, mock_mode, tmp_path):
        """build_assessment emits compliance_health_completed."""
        data_dir = tmp_path / "data"
        compliance_dir = data_dir / "compliance_health"
        compliance_dir.mkdir(parents=True, exist_ok=True)
        
        with patch("services.compliance_health.assessment._root", return_value=compliance_dir), \
             patch("services.compliance_health.registry.load_requirements") as mock_load:
            
            mock_load.return_value = []
            
            from services.compliance_health.assessment import build_assessment
            build_assessment("P-test123")
            
            event_types = [c[0][1] for c in mock_emit.call_args_list]
            assert "compliance_health_completed" in event_types


class TestObservabilityReadsEvents:
    """Test that observability correctly reads lifecycle events."""
    
    def test_observability_includes_canonical_events(self, tmp_path):
        """project_observability reads canonical lifecycle events."""
        data_dir = tmp_path / "data"
        memory_dir = data_dir / "memory"
        projects_dir = data_dir / "projects"
        
        memory_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / "P-test123").mkdir(parents=True, exist_ok=True)
        
        # Write test telemetry with canonical events
        telemetry = [
            {"event_type": "upload_started", "timestamp": "2026-01-01T00:01:00Z", "metadata": {"intake_id": "P-test123"}},
            {"event_type": "upload_completed", "timestamp": "2026-01-01T00:02:00Z", "metadata": {"intake_id": "P-test123"}},
            {"event_type": "verified_complete", "timestamp": "2026-01-01T00:03:00Z", "metadata": {"intake_id": "P-test123"}},
            {"event_type": "project_kickoff_completed", "timestamp": "2026-01-01T00:04:00Z", "metadata": {"project_id": "P-test123"}},
        ]
        
        telemetry_path = memory_dir / "telemetry.jsonl"
        with telemetry_path.open("w", encoding="utf-8") as f:
            for evt in telemetry:
                f.write(json.dumps(evt) + "\n")
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir), \
             patch("services.project_observability._intakes_root", return_value=data_dir / "intakes"):
            
            from services.project_observability import get_project_observability
            
            result = get_project_observability("P-test123")
            
            timeline = result.get("timeline", [])
            event_types = [e["event_type"] for e in timeline]
            
            assert "upload_started" in event_types
            assert "upload_completed" in event_types
            assert "verified_complete" in event_types
            assert "project_kickoff_completed" in event_types


class TestBackwardCompatibility:
    """Test backward compatibility with legacy event names."""
    
    def test_observability_includes_legacy_aliases(self, tmp_path):
        """project_observability also reads legacy alias events."""
        data_dir = tmp_path / "data"
        memory_dir = data_dir / "memory"
        projects_dir = data_dir / "projects"
        
        memory_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / "P-test123").mkdir(parents=True, exist_ok=True)
        
        # Write test telemetry with legacy aliases
        telemetry = [
            {"event_type": "pilot_upload_started", "timestamp": "2026-01-01T00:01:00Z", "metadata": {"intake_id": "P-test123"}},
            {"event_type": "pilot_upload_completed", "timestamp": "2026-01-01T00:02:00Z", "metadata": {"intake_id": "P-test123"}},
            {"event_type": "intake_kickoff_project", "timestamp": "2026-01-01T00:03:00Z", "metadata": {"project_id": "P-test123"}},
        ]
        
        telemetry_path = memory_dir / "telemetry.jsonl"
        with telemetry_path.open("w", encoding="utf-8") as f:
            for evt in telemetry:
                f.write(json.dumps(evt) + "\n")
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir), \
             patch("services.project_observability._intakes_root", return_value=data_dir / "intakes"):
            
            from services.project_observability import get_project_observability
            
            result = get_project_observability("P-test123")
            
            timeline = result.get("timeline", [])
            event_types = [e["event_type"] for e in timeline]
            
            # Legacy aliases should still be visible
            assert "pilot_upload_started" in event_types
            assert "pilot_upload_completed" in event_types
            assert "intake_kickoff_project" in event_types


class TestNoDuplicateEmissions:
    """Test that events are not emitted twice."""
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    def test_canonical_and_alias_are_distinct(self, mock_emit, mock_mode):
        """Canonical and alias are emitted as separate events, not duplicated."""
        emit_lifecycle_event(
            "upload_started",
            message="Test",
            metadata={"intake_id": "FB-test"},
            alias="pilot_upload_started",
        )
        
        # Count unique event type emissions
        canonical_count = sum(1 for c in mock_emit.call_args_list if c[0][1] == "upload_started")
        alias_count = sum(1 for c in mock_emit.call_args_list if c[0][1] == "pilot_upload_started")
        
        # Each should be emitted exactly once
        assert canonical_count == 1
        assert alias_count == 1

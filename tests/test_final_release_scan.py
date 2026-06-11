"""Tests for PATCH 13A-5C: Final Release Inspection Cockpit."""
import pytest
from unittest.mock import patch, MagicMock


class TestGateChecks:
    """Test individual gate check functions."""
    
    def test_custody_complete_pass(self):
        from services.final_release_scan import _check_custody_complete
        obs = {"kickoff": {"custody_status": "verified_complete"}}
        result = _check_custody_complete(obs)
        assert result["status"] == "PASS"
        assert result["blocking"] is True
    
    def test_custody_complete_warning(self):
        from services.final_release_scan import _check_custody_complete
        obs = {"kickoff": {"custody_status": "partial"}}
        result = _check_custody_complete(obs)
        assert result["status"] == "WARNING"
    
    def test_custody_complete_fail(self):
        from services.final_release_scan import _check_custody_complete
        obs = {"kickoff": {}}
        result = _check_custody_complete(obs)
        assert result["status"] == "FAIL"
        assert result["blocking"] is True
    
    def test_cognition_complete_pass(self):
        from services.final_release_scan import _check_cognition
        obs = {"cognition": {"status": "COMPLETED"}}
        result = _check_cognition(obs)
        assert result["status"] == "PASS"
    
    def test_cognition_complete_fail(self):
        from services.final_release_scan import _check_cognition
        obs = {"cognition": {"status": "NOT_STARTED"}}
        result = _check_cognition(obs)
        assert result["status"] == "FAIL"
        assert result["blocking"] is True
    
    def test_validation_complete_pass(self):
        from services.final_release_scan import _check_validation
        obs = {"validation": {"status": "COMPLETED"}}
        result = _check_validation(obs)
        assert result["status"] == "PASS"
    
    def test_validation_complete_fail(self):
        from services.final_release_scan import _check_validation
        obs = {"validation": {"status": "NOT_STARTED"}}
        result = _check_validation(obs)
        assert result["status"] == "FAIL"
        assert result["blocking"] is True
    
    def test_compliance_health_pass(self):
        from services.final_release_scan import _check_compliance_health
        obs = {"compliance_health": {"assessment_present": True, "overall_status": "AMBER"}}
        result = _check_compliance_health(obs)
        assert result["status"] == "PASS"
    
    def test_compliance_health_fail(self):
        from services.final_release_scan import _check_compliance_health
        obs = {"compliance_health": {"assessment_present": False}}
        result = _check_compliance_health(obs)
        assert result["status"] == "FAIL"
        assert result["blocking"] is True
    
    def test_blocking_failures_pass(self):
        from services.final_release_scan import _check_blocking_failures
        obs = {"compliance_health": {"blocking_failures_count": 0}}
        result = _check_blocking_failures(obs)
        assert result["status"] == "PASS"
    
    def test_blocking_failures_fail(self):
        from services.final_release_scan import _check_blocking_failures
        obs = {"compliance_health": {"blocking_failures_count": 2}}
        result = _check_blocking_failures(obs)
        assert result["status"] == "FAIL"
        assert result["blocking"] is True
    
    def test_critical_findings_pass(self):
        from services.final_release_scan import _check_critical_findings
        obs = {"validation": {"safety_warnings_count": 0}}
        result = _check_critical_findings("test-proj", obs)
        assert result["status"] == "PASS"
    
    def test_critical_findings_warning(self):
        from services.final_release_scan import _check_critical_findings
        obs = {"validation": {"safety_warnings_count": 3}}
        result = _check_critical_findings("test-proj", obs)
        assert result["status"] == "WARNING"
    
    def test_timeline_gaps_pass(self):
        from services.final_release_scan import _check_timeline_gaps
        obs = {"timeline": [
            {"event_type": "upload_started"},
            {"event_type": "upload_completed"},
            {"event_type": "project_kickoff_completed"},
            {"event_type": "cognition_completed"},
            {"event_type": "validation_completed"},
        ]}
        result = _check_timeline_gaps(obs)
        assert result["status"] == "PASS"
    
    def test_timeline_gaps_warning(self):
        from services.final_release_scan import _check_timeline_gaps
        obs = {"timeline": [{"event_type": "upload_started"}]}
        result = _check_timeline_gaps(obs)
        assert result["status"] == "WARNING"
    
    def test_human_review_pass(self):
        from services.final_release_scan import _check_human_review_items
        obs = {"validation": {"human_review_items_count": 0}}
        result = _check_human_review_items(obs)
        assert result["status"] == "PASS"
    
    def test_human_review_warning(self):
        from services.final_release_scan import _check_human_review_items
        obs = {"validation": {"human_review_items_count": 5}}
        result = _check_human_review_items(obs)
        assert result["status"] == "WARNING"


class TestReleaseStatus:
    """Test overall release status computation."""
    
    @patch("services.final_release_scan.get_project_observability")
    @patch("services.final_release_scan._load_release_state")
    @patch("services.final_release_scan._projects_root")
    def test_red_status_with_blocking_failures(self, mock_root, mock_state, mock_obs, tmp_path):
        from services.final_release_scan import scan_release_gates
        
        mock_root.return_value = tmp_path
        (tmp_path / "test-proj").mkdir()
        mock_state.return_value = {}
        mock_obs.return_value = {
            "ok": True,
            "kickoff": {"custody_status": "verified_complete"},
            "evidence_intelligence": {"status": "COMPLETED"},
            "cognition": {"status": "NOT_STARTED"},  # FAIL - blocking
            "validation": {"status": "NOT_STARTED"},  # FAIL - blocking
            "compliance_health": {"assessment_present": False, "blocking_failures_count": 0},
            "timeline": [],
        }
        
        result = scan_release_gates("test-proj")
        assert result["ok"]
        assert result["release_status"] == "RED"
        assert result["ready_to_release"] is False
        assert len(result["blocking_failures"]) > 0
    
    @patch("services.final_release_scan.get_project_observability")
    @patch("services.final_release_scan._load_release_state")
    @patch("services.final_release_scan._projects_root")
    def test_green_status_all_pass(self, mock_root, mock_state, mock_obs, tmp_path):
        from services.final_release_scan import scan_release_gates
        
        mock_root.return_value = tmp_path
        proj_dir = tmp_path / "test-proj" / "cognition"
        proj_dir.mkdir(parents=True)
        (proj_dir / "cognition_summary.json").write_text("{}")
        (proj_dir / "validation_report.json").write_text("{}")
        
        mock_state.return_value = {}
        mock_obs.return_value = {
            "ok": True,
            "kickoff": {"custody_status": "verified_complete"},
            "evidence_intelligence": {"status": "COMPLETED"},
            "cognition": {"status": "COMPLETED"},
            "validation": {"status": "COMPLETED", "safety_warnings_count": 0, "human_review_items_count": 0},
            "compliance_health": {"assessment_present": True, "overall_status": "GREEN", "blocking_failures_count": 0, "missing_verifications_count": 0},
            "timeline": [
                {"event_type": "upload_started"},
                {"event_type": "upload_completed"},
                {"event_type": "project_kickoff_completed"},
                {"event_type": "cognition_completed"},
                {"event_type": "validation_completed"},
                {"event_type": "external_verification_completed"},
            ],
        }
        
        result = scan_release_gates("test-proj")
        assert result["ok"]
        assert result["release_status"] == "GREEN"
        assert result["ready_to_release"] is True


class TestApproveRelease:
    """Test release approval logic."""
    
    def test_approve_requires_project_id(self):
        from services.final_release_scan import approve_release
        result = approve_release("")
        assert not result["ok"]
        assert "project_id required" in result["error"]
    
    @patch("services.final_release_scan.scan_release_gates")
    def test_red_blocks_approval(self, mock_scan):
        from services.final_release_scan import approve_release
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "RED",
            "blocking_failures": ["cognition_complete"],
            "required_operator_actions": ["Resolve: cognition_complete"],
        }
        
        result = approve_release("test-proj")
        assert not result["ok"]
        assert "RED" in result["error"]
    
    @patch("services.final_release_scan.scan_release_gates")
    @patch("services.final_release_scan._load_release_state")
    def test_amber_requires_override(self, mock_state, mock_scan):
        from services.final_release_scan import approve_release
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "AMBER",
            "warnings": ["timeline_gaps"],
        }
        mock_state.return_value = {}  # No override
        
        result = approve_release("test-proj")
        assert not result["ok"]
        assert "AMBER" in result["error"]
    
    @patch("services.final_release_scan.scan_release_gates")
    @patch("services.final_release_scan._load_release_state")
    @patch("services.final_release_scan._save_release_state")
    @patch("services.intake.telemetry.emit_lifecycle_event", MagicMock())
    def test_green_enables_approval(self, mock_save, mock_state, mock_scan):
        from services.final_release_scan import approve_release
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "GREEN",
            "blocking_failures": [],
            "deliverables_hash": "abc123",
        }
        mock_state.return_value = {}
        
        result = approve_release("test-proj")
        assert result["ok"]
        assert result["action"] == "approve"
        mock_save.assert_called_once()
    
    @patch("services.final_release_scan.scan_release_gates")
    @patch("services.final_release_scan._load_release_state")
    @patch("services.final_release_scan._save_release_state")
    def test_approval_is_idempotent(self, mock_save, mock_state, mock_scan):
        from services.final_release_scan import approve_release
        
        mock_scan.return_value = {"ok": True, "release_status": "GREEN", "deliverables_hash": "abc"}
        mock_state.return_value = {"approved_at_utc": "2026-06-11T00:00:00Z"}
        
        result = approve_release("test-proj")
        assert result["ok"]
        assert result.get("idempotent_return") is True
        mock_save.assert_not_called()


class TestOverrideAmber:
    """Test AMBER override logic."""
    
    def test_override_requires_project_id(self):
        from services.final_release_scan import override_amber
        result = override_amber("", reason="test")
        assert not result["ok"]
    
    def test_override_requires_reason(self):
        from services.final_release_scan import override_amber
        result = override_amber("test-proj", reason="short")
        assert not result["ok"]
        assert "minimum 10" in result["error"]
    
    @patch("services.final_release_scan.scan_release_gates")
    def test_cannot_override_red(self, mock_scan):
        from services.final_release_scan import override_amber
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "RED",
            "blocking_failures": ["cognition_complete"],
        }
        
        result = override_amber("test-proj", reason="This is my justification for override")
        assert not result["ok"]
        assert "RED" in result["error"]
    
    @patch("services.final_release_scan.scan_release_gates")
    @patch("services.final_release_scan._load_release_state")
    @patch("services.final_release_scan._save_release_state")
    @patch("services.intake.telemetry.emit_lifecycle_event", MagicMock())
    def test_amber_override_success(self, mock_save, mock_state, mock_scan):
        from services.final_release_scan import override_amber
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "AMBER",
            "warnings": ["timeline_gaps"],
        }
        mock_state.return_value = {}
        
        result = override_amber("test-proj", reason="Customer urgently needs delivery, timeline gaps are acceptable")
        assert result["ok"]
        assert result["action"] == "override_amber"
        mock_save.assert_called_once()
    
    @patch("services.final_release_scan.scan_release_gates")
    @patch("services.final_release_scan._load_release_state")
    def test_override_is_idempotent(self, mock_state, mock_scan):
        from services.final_release_scan import override_amber
        
        mock_scan.return_value = {"ok": True, "release_status": "AMBER", "warnings": []}
        mock_state.return_value = {"amber_override_at_utc": "2026-06-11T00:00:00Z"}
        
        result = override_amber("test-proj", reason="This is my justification")
        assert result["ok"]
        assert result.get("idempotent_return") is True


class TestSendRelease:
    """Test send release logic."""
    
    def test_send_requires_project_id(self):
        from services.final_release_scan import send_release
        result = send_release("")
        assert not result["ok"]
    
    @patch("services.final_release_scan._load_release_state")
    def test_send_disabled_before_approval(self, mock_state):
        from services.final_release_scan import send_release
        
        mock_state.return_value = {}  # Not approved
        
        result = send_release("test-proj")
        assert not result["ok"]
        assert "not yet approved" in result["error"]
    
    @patch("services.final_release_scan._load_release_state")
    @patch("services.final_release_scan._save_release_state")
    @patch("services.intake.telemetry.emit_lifecycle_event", MagicMock())
    def test_send_enabled_after_approval(self, mock_save, mock_state):
        from services.final_release_scan import send_release
        
        mock_state.return_value = {"approved_at_utc": "2026-06-11T00:00:00Z"}
        
        result = send_release("test-proj", recipient_email="customer@example.com")
        assert result["ok"]
        assert result["action"] == "send"
        assert result["sent_to"] == "customer@example.com"
        mock_save.assert_called_once()
    
    @patch("services.final_release_scan._load_release_state")
    def test_send_is_idempotent(self, mock_state):
        from services.final_release_scan import send_release
        
        mock_state.return_value = {
            "approved_at_utc": "2026-06-11T00:00:00Z",
            "sent_at_utc": "2026-06-11T01:00:00Z",
            "sent_to": "customer@example.com",
        }
        
        result = send_release("test-proj")
        assert result["ok"]
        assert result.get("idempotent_return") is True


class TestAPIEndpoints:
    """Test API endpoint registration."""
    
    def test_scan_endpoint_exists(self):
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/final-release-scan/{project_id}" in routes
    
    def test_approve_endpoint_exists(self):
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/final-release-scan/{project_id}/approve" in routes
    
    def test_override_endpoint_exists(self):
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/final-release-scan/{project_id}/override-amber" in routes
    
    def test_send_endpoint_exists(self):
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/final-release-scan/{project_id}/send" in routes


class TestOperatorCannotBypassGates:
    """Test that operator cannot bypass gating logic."""
    
    @patch("services.final_release_scan.scan_release_gates")
    def test_cannot_approve_with_missing_validation(self, mock_scan):
        from services.final_release_scan import approve_release
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "RED",
            "blocking_failures": ["validation_complete"],
            "required_operator_actions": ["Resolve validation"],
        }
        
        result = approve_release("test-proj")
        assert not result["ok"]
        assert "validation_complete" in str(result.get("blocking_failures", []))
    
    @patch("services.final_release_scan.scan_release_gates")
    def test_cannot_approve_with_missing_compliance_health(self, mock_scan):
        from services.final_release_scan import approve_release
        
        mock_scan.return_value = {
            "ok": True,
            "release_status": "RED",
            "blocking_failures": ["compliance_health_complete"],
            "required_operator_actions": ["Resolve compliance health"],
        }
        
        result = approve_release("test-proj")
        assert not result["ok"]
        assert "compliance_health_complete" in str(result.get("blocking_failures", []))

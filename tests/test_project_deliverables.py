"""Tests for PATCH 13A-5B: Project Deliverables Workbench."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestGetProjectDeliverables:
    """Test get_project_deliverables function."""
    
    def test_requires_project_id(self):
        from services.project_deliverables import get_project_deliverables
        result = get_project_deliverables("")
        assert not result["ok"]
        assert "project_id required" in result["error"]
    
    def test_reports_missing_stages(self, tmp_path):
        """Test that missing stages are correctly identified."""
        from services.project_deliverables import _compute_missing_stages
        
        # Empty observability = all missing
        obs = {
            "evidence_intelligence": {"status": "NOT_STARTED"},
            "cognition": {"status": "NOT_STARTED"},
            "validation": {"status": "NOT_STARTED"},
            "compliance_health": {"assessment_present": False},
        }
        missing = _compute_missing_stages(obs)
        assert "Evidence Intelligence" in missing
        assert "Cognition" in missing
        assert "Validation" in missing
        assert "Compliance Health" in missing
    
    def test_no_missing_when_complete(self):
        """Test that completed project has no missing stages."""
        from services.project_deliverables import _compute_missing_stages
        
        obs = {
            "evidence_intelligence": {"status": "COMPLETED"},
            "cognition": {"status": "COMPLETED"},
            "validation": {"status": "COMPLETED"},
            "compliance_health": {"assessment_present": True},
        }
        missing = _compute_missing_stages(obs)
        assert len(missing) == 0
    
    def test_partial_ei_counts_as_ready(self):
        """Test that PARTIAL EI status counts as complete."""
        from services.project_deliverables import _compute_missing_stages
        
        obs = {
            "evidence_intelligence": {"status": "PARTIAL"},
            "cognition": {"status": "COMPLETED"},
            "validation": {"status": "COMPLETED"},
            "compliance_health": {"assessment_present": True},
        }
        missing = _compute_missing_stages(obs)
        assert "Evidence Intelligence" not in missing


class TestOperatorStatus:
    """Test operator status computation."""
    
    def test_not_ready_status(self):
        from services.project_deliverables import _compute_operator_status
        status = _compute_operator_status(ready=False, state={})
        assert status == "not_ready"
    
    def test_ready_for_review_status(self):
        from services.project_deliverables import _compute_operator_status
        status = _compute_operator_status(ready=True, state={})
        assert status == "ready_for_review"
    
    def test_approved_status(self):
        from services.project_deliverables import _compute_operator_status
        status = _compute_operator_status(
            ready=True,
            state={"approved_at_utc": "2026-06-11T00:00:00Z"}
        )
        assert status == "approved"
    
    def test_sent_status(self):
        from services.project_deliverables import _compute_operator_status
        status = _compute_operator_status(
            ready=True,
            state={
                "approved_at_utc": "2026-06-11T00:00:00Z",
                "sent_at_utc": "2026-06-11T01:00:00Z",
            }
        )
        assert status == "sent"


class TestApproveDeliverables:
    """Test approve_deliverables function."""
    
    def test_approve_requires_project_id(self):
        from services.project_deliverables import approve_deliverables
        result = approve_deliverables("")
        assert not result["ok"]
        assert "project_id required" in result["error"]
    
    @patch("services.project_deliverables.get_project_deliverables")
    @patch("services.project_deliverables._load_deliverables_state")
    @patch("services.project_deliverables._save_deliverables_state")
    def test_cannot_approve_not_ready(self, mock_save, mock_load, mock_get):
        from services.project_deliverables import approve_deliverables
        
        mock_get.return_value = {
            "ok": True,
            "ready": False,
            "missing_stages": ["Cognition"],
        }
        mock_load.return_value = {}
        
        result = approve_deliverables("test-project")
        assert not result["ok"]
        assert "not ready" in result["error"]
        mock_save.assert_not_called()
    
    @patch("services.project_deliverables.get_project_deliverables")
    @patch("services.project_deliverables._load_deliverables_state")
    @patch("services.project_deliverables._save_deliverables_state")
    @patch("services.intake.telemetry.emit_lifecycle_event", MagicMock())
    def test_approve_success(self, mock_save, mock_load, mock_get):
        from services.project_deliverables import approve_deliverables
        
        mock_get.return_value = {"ok": True, "ready": True, "missing_stages": []}
        mock_load.return_value = {}
        
        result = approve_deliverables("test-project", operator_id="test-op")
        assert result["ok"]
        assert result["operator_status"] == "approved"
        assert result["approved_by"] == "test-op"
        mock_save.assert_called_once()
    
    @patch("services.project_deliverables.get_project_deliverables")
    @patch("services.project_deliverables._load_deliverables_state")
    @patch("services.project_deliverables._save_deliverables_state")
    def test_approve_idempotent(self, mock_save, mock_load, mock_get):
        from services.project_deliverables import approve_deliverables
        
        mock_get.return_value = {"ok": True, "ready": True, "missing_stages": []}
        mock_load.return_value = {"approved_at_utc": "2026-06-11T00:00:00Z"}
        
        result = approve_deliverables("test-project")
        assert result["ok"]
        assert result.get("idempotent_return") is True
        mock_save.assert_not_called()


class TestSendDeliverables:
    """Test send_deliverables function."""
    
    def test_send_requires_project_id(self):
        from services.project_deliverables import send_deliverables
        result = send_deliverables("")
        assert not result["ok"]
        assert "project_id required" in result["error"]
    
    @patch("services.project_deliverables._load_deliverables_state")
    def test_cannot_send_without_approval(self, mock_load):
        from services.project_deliverables import send_deliverables
        
        mock_load.return_value = {}
        
        result = send_deliverables("test-project")
        assert not result["ok"]
        assert "not yet approved" in result["error"]
    
    @patch("services.project_deliverables._load_deliverables_state")
    @patch("services.project_deliverables._save_deliverables_state")
    @patch("services.intake.telemetry.emit_lifecycle_event", MagicMock())
    def test_send_success(self, mock_save, mock_load):
        from services.project_deliverables import send_deliverables
        
        mock_load.return_value = {"approved_at_utc": "2026-06-11T00:00:00Z"}
        
        result = send_deliverables("test-project", recipient_email="test@example.com")
        assert result["ok"]
        assert result["operator_status"] == "sent"
        assert result["sent_to"] == "test@example.com"
        mock_save.assert_called_once()
    
    @patch("services.project_deliverables._load_deliverables_state")
    @patch("services.project_deliverables._save_deliverables_state")
    def test_send_idempotent(self, mock_save, mock_load):
        from services.project_deliverables import send_deliverables
        
        mock_load.return_value = {
            "approved_at_utc": "2026-06-11T00:00:00Z",
            "sent_at_utc": "2026-06-11T01:00:00Z",
            "sent_to": "customer@example.com",
        }
        
        result = send_deliverables("test-project")
        assert result["ok"]
        assert result.get("idempotent_return") is True
        mock_save.assert_not_called()


class TestDeliverableStates:
    """Test deliverable state transitions."""
    
    def test_state_file_path(self):
        from services.project_deliverables import _deliverables_state_path
        path = _deliverables_state_path("test-proj")
        assert "test-proj" in str(path)
        assert path.name == "deliverables_state.json"


class TestGeneratedDocuments:
    """Test generated documents detection."""
    
    def test_no_documents_when_empty(self, tmp_path):
        """Test empty project returns no documents."""
        from services.project_deliverables import _get_generated_documents
        
        with patch("services.project_deliverables._projects_root", return_value=tmp_path):
            (tmp_path / "test-proj").mkdir()
            docs = _get_generated_documents("test-proj")
            assert docs == []


class TestAPIEndpoints:
    """Test API endpoint availability (route existence)."""
    
    def test_deliverables_endpoint_exists(self):
        """Verify deliverables endpoint is registered."""
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/project-deliverables/{project_id}" in routes
    
    def test_approve_endpoint_exists(self):
        """Verify approve endpoint is registered."""
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/project-deliverables/{project_id}/approve" in routes
    
    def test_send_endpoint_exists(self):
        """Verify send endpoint is registered."""
        from server import app
        routes = [r.path for r in app.routes]
        assert "/api/operator/project-deliverables/{project_id}/send" in routes


class TestUIRoute:
    """Test UI route availability."""
    
    def test_deliverables_ui_route_exists(self):
        """Verify deliverables UI route is registered."""
        from server import app
        routes = [r.path for r in app.routes]
        assert "/ui/deliverables" in routes or "/ui/deliverables.html" in routes

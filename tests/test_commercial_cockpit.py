"""PATCH 13A-4G: Commercial Cockpit Completion Tests.

Tests the complete commercial payment workflow:
1. Confirm payment received
2. Timeline event emission
3. Observability payment state
4. Kickoff unlocked after payment
5. Duplicate confirmation idempotency
"""
import io
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


class TestPaymentConfirmedLifecycleEvent:
    """Test that payment_confirmed lifecycle event is emitted correctly."""
    
    def test_payment_confirmed_in_lifecycle_events(self):
        """payment_confirmed is registered in LIFECYCLE_EVENTS."""
        from services.intake.telemetry import LIFECYCLE_EVENTS
        assert "payment_confirmed" in LIFECYCLE_EVENTS
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    @patch("services.intake.storage.assert_canonical_write_path", return_value=None)
    def test_confirm_payment_emits_lifecycle_event(self, mock_assert, mock_emit, mock_mode, tmp_path):
        """confirm_payment_received emits payment_confirmed lifecycle event."""
        # Setup intake directory
        intakes_dir = tmp_path / "intakes"
        intake_id = "FB-payment-test"
        intake_dir = intakes_dir / intake_id
        intake_dir.mkdir(parents=True)
        
        # Create intake with payment link generated
        record = {
            "intake_id": intake_id,
            "email": "pay@test.com",
            "company": "PayCo",
            "payment": {
                "product_id": "cmmc_l1",
                "product_title": "CMMC Level 1",
                "price_display": "$997",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
            },
        }
        (intake_dir / "intake.json").write_text(json.dumps(record), encoding="utf-8")
        
        with patch("services.intake.storage.intakes_root", return_value=intakes_dir):
            from services.intake.operator_actions import _confirm_payment_received
            result = _confirm_payment_received(intake_id)
        
        assert result["ok"] is True
        assert result["payment"]["payment_received_at_utc"]
        
        # Check lifecycle event was emitted
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        assert "payment_confirmed" in event_types or "operator_payment_received" in event_types
    
    @patch("services.intake.telemetry.is_intake_mode", return_value=True)
    @patch("services.organism_observability.emit.organism_emit")
    @patch("services.intake.storage.assert_canonical_write_path", return_value=None)
    def test_confirm_payment_emits_with_alias(self, mock_assert, mock_emit, mock_mode, tmp_path):
        """payment_confirmed also emits backward-compatible alias."""
        intakes_dir = tmp_path / "intakes"
        intake_id = "FB-alias-test"
        intake_dir = intakes_dir / intake_id
        intake_dir.mkdir(parents=True)
        
        record = {
            "intake_id": intake_id,
            "email": "alias@test.com",
            "payment": {
                "product_id": "cmmc_l2",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
            },
        }
        (intake_dir / "intake.json").write_text(json.dumps(record), encoding="utf-8")
        
        with patch("services.intake.storage.intakes_root", return_value=intakes_dir):
            from services.intake.operator_actions import _confirm_payment_received
            _confirm_payment_received(intake_id)
        
        event_types = [c[0][1] for c in mock_emit.call_args_list]
        # Both canonical and alias should be emitted
        assert "payment_confirmed" in event_types
        assert "operator_payment_received" in event_types


class TestObservabilityPaymentState:
    """Test observability includes payment state."""
    
    @patch("services.intake.storage.assert_canonical_write_path", return_value=None)
    def test_observability_includes_payment_section(self, mock_assert, tmp_path):
        """get_project_observability returns payment section."""
        data_dir = tmp_path / "data"
        intakes_dir = data_dir / "intakes"
        projects_dir = data_dir / "projects"
        memory_dir = data_dir / "memory"
        
        intake_id = "FB-obs-pay-test"
        intakes_dir.mkdir(parents=True)
        (intakes_dir / intake_id).mkdir()
        memory_dir.mkdir(parents=True)
        
        # Create intake with payment
        record = {
            "intake_id": intake_id,
            "email": "obs@test.com",
            "payment": {
                "product_id": "cmmc_l1",
                "product_title": "CMMC Level 1",
                "price_display": "$997",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
                "payment_link_sent_at_utc": "2026-01-01T00:01:00Z",
            },
        }
        (intakes_dir / intake_id / "intake.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir):
            from services.project_observability import get_project_observability
            result = get_project_observability(intake_id)
        
        assert result["ok"] is True
        assert "payment" in result
        payment = result["payment"]
        assert payment["payment_link_sent"] is True
        assert payment["payment_confirmed"] is False
        assert payment["product_id"] == "cmmc_l1"
        assert payment["kickoff_blocked_by_payment"] is True
    
    @patch("services.intake.storage.assert_canonical_write_path", return_value=None)
    def test_observability_payment_confirmed_state(self, mock_assert, tmp_path):
        """Observability shows payment confirmed state correctly."""
        data_dir = tmp_path / "data"
        intakes_dir = data_dir / "intakes"
        memory_dir = data_dir / "memory"
        
        intake_id = "FB-confirmed-test"
        (intakes_dir / intake_id).mkdir(parents=True)
        memory_dir.mkdir(parents=True)
        
        record = {
            "intake_id": intake_id,
            "email": "confirmed@test.com",
            "payment": {
                "product_id": "cmmc_l2",
                "product_title": "CMMC Level 2",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
                "payment_received_at_utc": "2026-01-02T10:00:00Z",
                "payment_confirmed_via": "operator",
            },
        }
        (intakes_dir / intake_id / "intake.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir):
            from services.project_observability import get_project_observability
            result = get_project_observability(intake_id)
        
        payment = result["payment"]
        assert payment["payment_confirmed"] is True
        assert payment["payment_received_at_utc"] == "2026-01-02T10:00:00Z"
        assert payment["payment_confirmed_via"] == "operator"
        assert payment["kickoff_blocked_by_payment"] is False
    
    @patch("services.intake.storage.assert_canonical_write_path", return_value=None)
    def test_observability_validation_mode_not_blocked(self, mock_assert, tmp_path):
        """Validation mode projects are not blocked by payment."""
        data_dir = tmp_path / "data"
        intakes_dir = data_dir / "intakes"
        memory_dir = data_dir / "memory"
        
        intake_id = "FB-validation-test"
        (intakes_dir / intake_id).mkdir(parents=True)
        memory_dir.mkdir(parents=True)
        
        record = {
            "intake_id": intake_id,
            "email": "val@test.com",
            "validation_project": True,
            "payment": {
                "product_id": "cmmc_l1",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
            },
        }
        (intakes_dir / intake_id / "intake.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir):
            from services.project_observability import get_project_observability
            result = get_project_observability(intake_id)
        
        payment = result["payment"]
        assert payment["payment_link_sent"] is True
        assert payment["payment_confirmed"] is False
        # Validation mode bypasses payment requirement
        assert payment["kickoff_blocked_by_payment"] is False


class TestKickoffUnlockedAfterPayment:
    """Test kickoff is blocked until payment confirmed."""
    
    def test_kickoff_blocked_without_payment(self, tmp_path):
        """Kickoff raises 402 when payment not confirmed."""
        intakes_dir = tmp_path / "intakes"
        projects_dir = tmp_path / "projects"
        
        intake_id = "FB-blocked-test"
        intake_dir = intakes_dir / intake_id
        uploads_dir = intake_dir / "uploads"
        uploads_dir.mkdir(parents=True)
        
        # Create test file
        (uploads_dir / "test.pdf").write_bytes(b"%PDF-1.4 test")
        
        # Create intake with payment link but not confirmed
        record = {
            "intake_id": intake_id,
            "email": "block@test.com",
            "company": "BlockCo",
            "payment": {
                "product_id": "cmmc_l1",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
                # No payment_received_at_utc
            },
        }
        (intake_dir / "intake.json").write_text(json.dumps(record), encoding="utf-8")
        
        with patch("services.intake.storage.intakes_root", return_value=intakes_dir), \
             patch("services.intake.durable_root.durable_data_root", return_value=tmp_path):
            from services.intake.kickoff import kickoff_project_from_intake
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as exc_info:
                kickoff_project_from_intake(intake_id)
            
            assert exc_info.value.status_code == 402
            assert "Payment not yet confirmed" in str(exc_info.value.detail)
    
    def test_kickoff_allowed_after_payment(self, tmp_path):
        """Kickoff succeeds when payment confirmed."""
        intakes_dir = tmp_path / "intakes"
        projects_dir = tmp_path / "projects"
        
        intake_id = "FB-allowed-test"
        intake_dir = intakes_dir / intake_id
        uploads_dir = intake_dir / "uploads"
        uploads_dir.mkdir(parents=True)
        projects_dir.mkdir(parents=True)
        
        (uploads_dir / "test.pdf").write_bytes(b"%PDF-1.4 test")
        
        record = {
            "intake_id": intake_id,
            "email": "allow@test.com",
            "company": "AllowCo",
            "payment": {
                "product_id": "cmmc_l1",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
                "payment_received_at_utc": "2026-01-02T00:00:00Z",
            },
        }
        (intake_dir / "intake.json").write_text(json.dumps(record), encoding="utf-8")
        
        with patch("services.intake.storage.intakes_root", return_value=intakes_dir), \
             patch("services.intake.durable_root.durable_data_root", return_value=tmp_path), \
             patch("services.config.PROJECTS", projects_dir), \
             patch("services.intake.kickoff._config.PROJECTS", projects_dir), \
             patch("services.intake.kickoff._config.DATA", tmp_path), \
             patch("services.intake.kickoff.new_project") as mock_new_project, \
             patch("services.intake.kickoff.init_workflow"), \
             patch("services.intake.kickoff.set_phase"), \
             patch("services.intake.kickoff.register_artifact"), \
             patch("services.intake.kickoff._run_post_kickoff_intelligence"):
            
            mock_new_project.return_value = {"project_id": "P-allowed-test"}
            (projects_dir / "P-allowed-test" / "evidence").mkdir(parents=True)
            (projects_dir / "P-allowed-test" / "communications").mkdir(parents=True)
            
            from services.intake.kickoff import kickoff_project_from_intake
            result = kickoff_project_from_intake(intake_id)
            
            assert result["ok"] is True
            assert result["project_id"] == "P-allowed-test"


class TestDuplicateConfirmationIdempotent:
    """Test duplicate payment confirmation is safe."""
    
    def test_duplicate_confirmation_idempotent(self, tmp_path):
        """Re-confirming payment is harmless and returns duplicate_skipped."""
        intakes_dir = tmp_path / "intakes"
        intake_id = "FB-idempotent-test"
        intake_dir = intakes_dir / intake_id
        intake_dir.mkdir(parents=True)
        
        record = {
            "intake_id": intake_id,
            "email": "idem@test.com",
            "payment": {
                "product_id": "cmmc_l1",
                "payment_link_generated_at_utc": "2026-01-01T00:00:00Z",
                "payment_received_at_utc": "2026-01-02T00:00:00Z",  # Already confirmed
            },
        }
        (intake_dir / "intake.json").write_text(json.dumps(record), encoding="utf-8")
        
        with patch("services.intake.storage.intakes_root", return_value=intakes_dir), \
             patch("services.intake.durable_root.durable_data_root", return_value=tmp_path):
            from services.intake.operator_actions import _confirm_payment_received
            result = _confirm_payment_received(intake_id)
        
        assert result["ok"] is True
        assert result["duplicate_skipped"] is True


class TestTimelineIncludesPaymentConfirmed:
    """Test timeline events include payment_confirmed."""
    
    def test_timeline_relevant_types_includes_payment(self):
        """Timeline event filter includes payment_confirmed."""
        # This test verifies the code structure includes payment_confirmed
        from services.project_observability import _get_timeline_events
        import inspect
        source = inspect.getsource(_get_timeline_events)
        assert "payment_confirmed" in source
        assert "operator_payment_received" in source
    
    def test_timeline_captures_payment_event(self, tmp_path):
        """Timeline events list includes payment_confirmed when present."""
        data_dir = tmp_path / "data"
        intakes_dir = data_dir / "intakes"
        memory_dir = data_dir / "memory"
        
        intake_id = "FB-timeline-pay"
        (intakes_dir / intake_id).mkdir(parents=True)
        memory_dir.mkdir(parents=True)
        
        # Create intake
        record = {"intake_id": intake_id, "email": "tl@test.com"}
        (intakes_dir / intake_id / "intake.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        
        # Create telemetry with payment_confirmed event
        telemetry = [
            {
                "event_type": "payment_confirmed",
                "timestamp": "2026-01-02T10:00:00Z",
                "message": "Payment confirmed",
                "metadata": {"intake_id": intake_id, "product_id": "cmmc_l1"},
            },
        ]
        
        telemetry_path = memory_dir / "telemetry.jsonl"
        with telemetry_path.open("w", encoding="utf-8") as f:
            for evt in telemetry:
                f.write(json.dumps(evt) + "\n")
        
        with patch("services.durable_storage.active_data_root", return_value=data_dir):
            from services.project_observability import get_project_observability
            result = get_project_observability(intake_id)
        
        timeline = result.get("timeline", [])
        event_types = [e["event_type"] for e in timeline]
        assert "payment_confirmed" in event_types


class TestIntegrationCommercialWorkflow:
    """Integration tests for full commercial workflow via API."""
    
    def test_full_commercial_workflow(self, fb_env, anon_client: TestClient, client: TestClient):
        """Complete commercial workflow: upload → payment link → confirm → kickoff."""
        # 1. Upload
        up = anon_client.post(
            "/api/intake/upload",
            files=[("files", ("doc.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"))],
            data={"email": "commercial@test.com", "company": "CommercialCo"},
        )
        assert up.status_code == 200
        iid = up.json()["intake_id"]
        
        # 2. Send payment link
        link = client.post(
            "/api/operator/intake/action",
            json={"intake_id": iid, "action": "send_payment_link", "product_id": "cmmc_l1"},
        )
        assert link.status_code == 200
        
        # 3. Verify kickoff is blocked
        blocked = client.post(
            "/api/operator/intake/action",
            json={"intake_id": iid, "action": "kickoff_project"},
        )
        assert blocked.status_code == 402
        
        # 4. Confirm payment
        confirm = client.post(
            "/api/operator/intake/action",
            json={"intake_id": iid, "action": "confirm_payment_received"},
        )
        assert confirm.status_code == 200
        body = confirm.json()
        assert body["ok"] is True
        assert body["kickoff_ready"] is True
        assert body["payment"]["payment_received_at_utc"]
        
        # 5. Verify kickoff now works
        kickoff = client.post(
            "/api/operator/intake/action",
            json={"intake_id": iid, "action": "kickoff_project"},
        )
        assert kickoff.status_code == 200
        assert kickoff.json()["project_id"]
    
    def test_observability_after_payment_confirmation(
        self, fb_env, anon_client: TestClient, client: TestClient
    ):
        """Observability reflects payment state after confirmation."""
        # Upload and setup
        up = anon_client.post(
            "/api/intake/upload",
            files=[("files", ("obs.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
            data={"email": "obs-pay@test.com"},
        )
        iid = up.json()["intake_id"]
        
        # Send payment link
        client.post(
            "/api/operator/intake/action",
            json={"intake_id": iid, "action": "send_payment_link", "product_id": "cmmc_l1"},
        )
        
        # Check observability before confirmation
        obs1 = client.get(f"/api/operator/project-observability/{iid}")
        assert obs1.status_code == 200
        payment1 = obs1.json().get("payment", {})
        assert payment1.get("payment_link_sent") is True
        assert payment1.get("payment_confirmed") is False
        
        # Confirm payment
        client.post(
            "/api/operator/intake/action",
            json={"intake_id": iid, "action": "confirm_payment_received"},
        )
        
        # Check observability after confirmation
        obs2 = client.get(f"/api/operator/project-observability/{iid}")
        assert obs2.status_code == 200
        payment2 = obs2.json().get("payment", {})
        assert payment2.get("payment_confirmed") is True
        assert payment2.get("kickoff_blocked_by_payment") is False

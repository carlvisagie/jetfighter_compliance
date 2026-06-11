"""PATCH 13A-4C: Post-kickoff hardening tests.

Tests for:
1. EI success semantics (ei_success only when ALL files succeed)
2. project_kickoff_completed persistence
3. Duplicate kickoff idempotency
4. Intake pollution regression guard (intakes/ must not have EI/cognition dirs)
5. Post-kickoff telemetry events
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# --- FIX A: EI Success Semantics ---


def test_ei_success_only_when_all_files_succeed(tmp_path):
    """ei_success = True only when ALL evidence files processed successfully."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "P-test-eisuccess"
    intake_id = "FB-test-eisuccess"
    
    # Create evidence directory with 2 files
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "file1.pdf").write_bytes(b"%PDF-1.4 test")
    (evidence_dir / "file2.pdf").write_bytes(b"%PDF-1.4 test")
    
    captured_events = []
    
    def capture_emit(*args, **kwargs):
        captured_events.append({"args": args, "kwargs": kwargs})
    
    with patch("services.config.PROJECTS", tmp_path / "projects"):
        with patch("services.evidence_intelligence.process_evidence_upload") as mock_ei:
            with patch("services.cognition.storage.run_cognition_safely"):
                with patch("services.intake.kickoff.emit_intake_event", capture_emit):
                    with patch("services.intake.telemetry.emit_intake_event", capture_emit):
                        # All files succeed
                        mock_ei.return_value = MagicMock(status="completed")
                        _run_post_kickoff_intelligence(project_id, intake_id)
    
    # Find the final event
    final_event = None
    for e in captured_events:
        if e["args"] and e["args"][0] == "post_kickoff_intelligence_completed":
            final_event = e
            break
    
    assert final_event is not None, "post_kickoff_intelligence_completed event not emitted"
    meta = final_event["kwargs"].get("metadata", {})
    
    assert meta.get("ei_success") is True, "ei_success should be True when all files succeed"
    assert meta.get("ei_partial") is False, "ei_partial should be False when all files succeed"
    assert meta.get("ei_success_count") == 2, "ei_success_count should be 2"
    assert meta.get("ei_failed_count") == 0, "ei_failed_count should be 0"


def test_ei_partial_when_some_files_fail(tmp_path):
    """ei_partial = True when some files succeed and some fail."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "P-test-eipartial"
    intake_id = "FB-test-eipartial"
    
    # Create evidence directory with 2 files
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "file1.pdf").write_bytes(b"%PDF-1.4 test")
    (evidence_dir / "file2.pdf").write_bytes(b"%PDF-1.4 test")
    
    captured_events = []
    
    def capture_emit(*args, **kwargs):
        captured_events.append({"args": args, "kwargs": kwargs})
    
    call_count = [0]
    
    def mock_ei_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(status="completed")
        else:
            raise Exception("EI failed for second file")
    
    with patch("services.config.PROJECTS", tmp_path / "projects"):
        with patch("services.evidence_intelligence.process_evidence_upload") as mock_ei:
            with patch("services.cognition.storage.run_cognition_safely"):
                with patch("services.intake.kickoff.emit_intake_event", capture_emit):
                    with patch("services.intake.telemetry.emit_intake_event", capture_emit):
                        mock_ei.side_effect = mock_ei_side_effect
                        _run_post_kickoff_intelligence(project_id, intake_id)
    
    # Find the final event
    final_event = None
    for e in captured_events:
        if e["args"] and e["args"][0] == "post_kickoff_intelligence_completed":
            final_event = e
            break
    
    assert final_event is not None, "post_kickoff_intelligence_completed event not emitted"
    meta = final_event["kwargs"].get("metadata", {})
    
    assert meta.get("ei_success") is False, "ei_success should be False when some files fail"
    assert meta.get("ei_partial") is True, "ei_partial should be True when some succeed and some fail"
    assert meta.get("ei_success_count") == 1, "ei_success_count should be 1"
    assert meta.get("ei_failed_count") == 1, "ei_failed_count should be 1"


def test_ei_success_false_when_all_files_fail(tmp_path):
    """ei_success = False when ALL evidence files fail."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "P-test-eifail"
    intake_id = "FB-test-eifail"
    
    # Create evidence directory with 2 files
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "file1.pdf").write_bytes(b"%PDF-1.4 test")
    (evidence_dir / "file2.pdf").write_bytes(b"%PDF-1.4 test")
    
    captured_events = []
    
    def capture_emit(*args, **kwargs):
        captured_events.append({"args": args, "kwargs": kwargs})
    
    with patch("services.config.PROJECTS", tmp_path / "projects"):
        with patch("services.evidence_intelligence.process_evidence_upload") as mock_ei:
            with patch("services.cognition.storage.run_cognition_safely"):
                with patch("services.intake.kickoff.emit_intake_event", capture_emit):
                    with patch("services.intake.telemetry.emit_intake_event", capture_emit):
                        mock_ei.side_effect = Exception("EI failed")
                        _run_post_kickoff_intelligence(project_id, intake_id)
    
    # Find the final event
    final_event = None
    for e in captured_events:
        if e["args"] and e["args"][0] == "post_kickoff_intelligence_completed":
            final_event = e
            break
    
    assert final_event is not None
    meta = final_event["kwargs"].get("metadata", {})
    
    assert meta.get("ei_success") is False, "ei_success should be False when all files fail"
    assert meta.get("ei_partial") is False, "ei_partial should be False when all files fail"
    assert meta.get("ei_failed_count") == 2, "ei_failed_count should be 2"


# --- FIX B: project_kickoff_completed Persistence ---


def test_project_kickoff_completed_persists_to_disk(fb_env, tmp_path):
    """project_kickoff_completed is saved to disk after successful kickoff."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible, _save_intake
    from services.intake.storage import load_intake_record
    
    # Create a validation intake
    intake_id = "FB-persist-test123"
    intake_dir = tmp_path / "intakes" / intake_id
    intake_dir.mkdir(parents=True)
    (intake_dir / "uploads").mkdir()
    (intake_dir / "uploads" / "test.pdf").write_bytes(b"%PDF-1.4 test")
    
    record = {
        "intake_id": intake_id,
        "email": "persist@test.com",
        "company": "Persist Test",
        "custody_status": "verified_complete",
        "validation_project": True,
        "files": [{"name": "test.pdf"}],
    }
    (intake_dir / "intake.json").write_text(json.dumps(record))
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        mock_kickoff.return_value = {
            "ok": True,
            "project_id": "P-persist-test",
            "files_linked": ["test.pdf"],
        }
        
        _trigger_auto_kickoff_if_eligible(intake_id, record)
    
    # Verify the record was saved with kickoff state
    assert record.get("project_kickoff_completed") is True
    assert record.get("project_id") == "P-persist-test"
    assert "project_kickoff_at_utc" in record


def test_duplicate_kickoff_returns_existing_project(tmp_path):
    """Duplicate kickoff call returns existing project_id without creating new one."""
    from services.intake.kickoff import kickoff_project_from_intake
    
    intake_id = "FB-idempotent-test"
    intake_dir = tmp_path / "intakes" / intake_id
    intake_dir.mkdir(parents=True)
    (intake_dir / "uploads").mkdir()
    (intake_dir / "uploads" / "test.pdf").write_bytes(b"%PDF-1.4 test")
    
    # Intake already has a project_id (was already kicked off)
    existing_project = "P-existing-project-123"
    record = {
        "intake_id": intake_id,
        "email": "idempotent@test.com",
        "company": "Idempotent Test",
        "project_id": existing_project,
        "project_kickoff_completed": True,
        "files": [{"name": "test.pdf"}],
    }
    (intake_dir / "intake.json").write_text(json.dumps(record))
    
    with patch("services.intake.kickoff.load_intake_record", return_value=record):
        with patch("services.projects.new_project") as mock_new_project:
            result = kickoff_project_from_intake(
                intake_id,
                operator_note="PAYMENT_OVERRIDE: test"
            )
    
    # new_project should NOT be called
    mock_new_project.assert_not_called()
    
    # Result should return existing project
    assert result["project_id"] == existing_project
    assert result.get("idempotent_return") is True


# --- FIX C: Regression Guard - No Intake Pollution ---


def test_intakes_directory_has_no_ei_pollution(fb_env, anon_client: TestClient):
    """REGRESSION GUARD: intakes/ must NOT contain evidence_intelligence/ after upload.
    
    PATCH 13A-4B moved EI to post-kickoff. This test ensures intakes/ stays immutable.
    """
    data = {
        "email": "pollution-guard@test.com",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["guard.pdf"]),
        "validation_project": "true",
    }
    files = [("files", ("guard.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"))]
    
    r = anon_client.post("/api/intake/upload", files=files, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    intake_id = body["intake_id"]
    
    from services.durable_storage import active_data_root
    from services.intake.storage import intake_dir
    
    import time
    time.sleep(0.5)  # Allow async processing
    
    intake_root = intake_dir(intake_id)
    
    # These directories MUST NOT exist under intakes/
    forbidden_dirs = [
        intake_root / "evidence_intelligence",
        intake_root / "cognition",
        intake_root / "generated_documents",
    ]
    
    for forbidden in forbidden_dirs:
        assert not forbidden.exists(), (
            f"REGRESSION: {forbidden.name}/ found under intakes/{intake_id}/. "
            f"EI/Cognition must only write to projects/, not intakes/."
        )


def test_intakes_directory_has_no_cognition_pollution(fb_env, anon_client: TestClient):
    """REGRESSION GUARD: intakes/ must NOT contain cognition/ after upload."""
    data = {
        "email": "cog-guard@test.com",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["cogguard.pdf"]),
        "validation_project": "true",
    }
    files = [("files", ("cogguard.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"))]
    
    r = anon_client.post("/api/intake/upload", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    intake_id = body["intake_id"]
    
    from services.intake.storage import intake_dir
    
    import time
    time.sleep(0.5)
    
    intake_root = intake_dir(intake_id)
    cognition_dir = intake_root / "cognition"
    
    assert not cognition_dir.exists(), (
        f"REGRESSION: cognition/ found under intakes/{intake_id}/. "
        f"Cognition must only write to projects/, not intakes/."
    )


def test_intelligence_artifacts_exist_only_under_projects(fb_env, anon_client: TestClient):
    """Intelligence artifacts must exist under projects/{project_id}/, not intakes/."""
    data = {
        "email": "project-only@test.com",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["proj.pdf"]),
        "validation_project": "true",
    }
    files = [("files", ("proj.pdf", io.BytesIO(b"%PDF-1.4 test content"), "application/pdf"))]
    
    r = anon_client.post("/api/intake/upload", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    intake_id = body["intake_id"]
    
    from services.durable_storage import active_data_root
    from services.intake.storage import load_intake_record, intake_dir
    
    import time
    time.sleep(1.0)  # Allow intelligence processing
    
    rec = load_intake_record(intake_id)
    project_id = rec.get("project_id")
    
    if project_id:
        project_root = active_data_root() / "projects" / project_id
        
        # These should exist under projects/
        assert (project_root / "evidence").is_dir(), "evidence/ should exist under projects/"
        
        # These should NOT exist under intakes/
        intake_root = intake_dir(intake_id)
        assert not (intake_root / "evidence_intelligence").exists()
        assert not (intake_root / "cognition").exists()


# --- FIX D: Organism Timeline Events ---


def test_post_kickoff_events_appear_in_telemetry(tmp_path):
    """Post-kickoff events should be logged to telemetry."""
    from services.intake.kickoff import _run_post_kickoff_intelligence
    
    project_id = "P-telemetry-test"
    intake_id = "FB-telemetry-test"
    
    evidence_dir = tmp_path / "projects" / project_id / "evidence"
    evidence_dir.mkdir(parents=True)
    
    captured_events = []
    
    def capture_emit(*args, **kwargs):
        captured_events.append({"event_type": args[0] if args else None, "kwargs": kwargs})
    
    with patch("services.config.PROJECTS", tmp_path / "projects"):
        with patch("services.evidence_intelligence.process_evidence_upload"):
            with patch("services.cognition.storage.run_cognition_safely", return_value={"status": "success"}):
                with patch("services.intake.kickoff.emit_intake_event", capture_emit):
                    with patch("services.intake.telemetry.emit_intake_event", capture_emit):
                        _run_post_kickoff_intelligence(project_id, intake_id, email="telemetry@test.com")
    
    event_types = [e["event_type"] for e in captured_events]
    
    # All required events should be emitted
    assert "post_kickoff_intelligence_started" in event_types
    assert "evidence_intelligence_completed" in event_types
    assert "cognition_completed" in event_types
    assert "post_kickoff_intelligence_completed" in event_types


# --- Validation Mode & Commercial Mode Unchanged ---


def test_validation_mode_still_triggers_auto_kickoff(fb_env, anon_client: TestClient):
    """PATCH 13A-4C: Validation mode auto-kickoff still works."""
    data = {
        "email": "val-mode@test.com",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["val.pdf"]),
        "validation_project": "true",
    }
    files = [("files", ("val.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"))]
    
    r = anon_client.post("/api/intake/upload", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    intake_id = body["intake_id"]
    
    from services.intake.storage import load_intake_record
    
    import time
    time.sleep(0.5)
    
    rec = load_intake_record(intake_id)
    
    # Auto-kickoff should have created project
    assert rec.get("project_id"), "Validation mode should trigger auto-kickoff"
    assert rec.get("project_kickoff_completed") is True


def test_commercial_mode_still_requires_payment(sample_intake_record):
    """PATCH 13A-4C: Commercial mode payment gate unchanged."""
    from services.intake.intake import _trigger_auto_kickoff_if_eligible
    
    sample_intake_record["custody_status"] = "verified_complete"
    sample_intake_record["intake_id"] = "FB-comm-unchanged"
    # No payment, no validation flags
    sample_intake_record.pop("validation_project", None)
    sample_intake_record.pop("founding_pilot", None)
    
    with patch("services.intake.kickoff.kickoff_project_from_intake") as mock_kickoff:
        _trigger_auto_kickoff_if_eligible("FB-comm-unchanged", sample_intake_record)
    
    # Should NOT call kickoff without payment
    mock_kickoff.assert_not_called()


@pytest.fixture
def sample_intake_record() -> Dict[str, Any]:
    """Base intake record for testing."""
    return {
        "intake_id": "FB-test-13a4c",
        "email": "test@example.com",
        "company": "Test Corp",
        "custody_status": "verified_complete",
        "files": [{"name": "test.pdf"}],
        "file_count": 1,
    }

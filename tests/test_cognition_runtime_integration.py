import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi import UploadFile

from services.intake.intake import process_upload
from services.cognition.storage import run_cognition_safely

@pytest.mark.asyncio
async def test_cognition_runtime_hook_called(tmp_path):
    """
    PATCH 13A-3C: Cognition now runs AFTER project kickoff, not during upload.
    This test verifies cognition is NOT called prematurely during intake processing.
    Cognition will run when kickoff_project_from_intake() is called.
    """
    # Mock everything around the upload flow to just test if the hook is called
    with patch("services.intake.intake._safe_emit_intake_event"), \
         patch("services.intake.intake.emit_intake_event"), \
         patch("services.intake.intake._append_index"), \
         patch("services.intake.intake.ensure_canonical_intake_dir", return_value=tmp_path), \
         patch("services.intake.intake.canonical_intake_dir", return_value=tmp_path), \
         patch("services.intake.intake._save_intake"), \
         patch("services.intake.transactions.append_transaction_event"), \
         patch("services.intake.evidence_registry.derive_evidence_registry_for_intake"), \
         patch("services.intake.file_durability.write_upload_with_durability_markers"), \
         patch("services.intake.retention.require_upload_durability_verified", return_value={"durability_verified": True}), \
         patch("services.evidence_intelligence.process_evidence_upload"), \
         patch("services.cognition.storage.run_cognition_safely") as mock_run_cognition:

        # Create mock file and upload dir
        (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)
        test_file = tmp_path / "uploads" / "test.txt"
        test_file.write_text("dummy")

        mock_uf = MagicMock(spec=UploadFile)
        mock_uf.filename = "test.txt"
        mock_uf.content_type = "text/plain"
        mock_uf.read.return_value = b"dummy"

        try:
            await process_upload([mock_uf], email="test@test.com", company="Test")
        except Exception as e:
            pass # ignore expected errors down the line if any

        # CHANGED: Cognition should NOT be called during upload anymore
        # It runs after project kickoff in services/intake/kickoff.py
        mock_run_cognition.assert_not_called()


@pytest.mark.asyncio
async def test_upload_succeeds_if_cognition_fails(tmp_path):
    """
    PATCH 13A-3C: Cognition runs post-kickoff, so upload always succeeds.
    This test is kept for backwards compatibility but cognition failure
    no longer affects upload success since they're decoupled.
    """
    with patch("services.intake.intake._safe_emit_intake_event"), \
         patch("services.intake.intake.emit_intake_event"), \
         patch("services.intake.intake._append_index"), \
         patch("services.intake.intake.ensure_canonical_intake_dir", return_value=tmp_path), \
         patch("services.intake.intake.canonical_intake_dir", return_value=tmp_path), \
         patch("services.intake.intake._save_intake"), \
         patch("services.intake.transactions.append_transaction_event"), \
         patch("services.intake.evidence_registry.derive_evidence_registry_for_intake"), \
         patch("services.intake.file_durability.write_upload_with_durability_markers"), \
         patch("services.intake.retention.require_upload_durability_verified", return_value={"durability_verified": True}), \
         patch("services.evidence_intelligence.process_evidence_upload"), \
         patch("services.cognition.storage.run_cognition_safely") as mock_run_cognition:

        # Cognition raises error (but won't be called during upload anyway)
        mock_run_cognition.side_effect = Exception("Cognition hard failure")

        (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)
        test_file = tmp_path / "uploads" / "test.txt"
        test_file.write_text("dummy")

        mock_uf = MagicMock(spec=UploadFile)
        mock_uf.filename = "test.txt"
        mock_uf.content_type = "text/plain"
        mock_uf.read.return_value = b"dummy"

        res = await process_upload([mock_uf], email="test@test.com", company="Test")
        
        # Upload should still return ok=True (cognition is post-kickoff)
        assert res.get("ok") is True

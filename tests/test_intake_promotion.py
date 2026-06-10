"""Test promotion of uploads from intake to evidence."""
from __future__ import annotations

import io
import json
from fastapi.testclient import TestClient

def _pdf(name: str, content: bytes = b"%PDF-1.4 minimal") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))

def test_intake_files_promoted_to_evidence(fb_env, anon_client: TestClient):
    """
    PATCH 13A-3C: Test full validation mode flow with auto-kickoff.
    Files are promoted during upload, cognition runs after auto-kickoff.
    
    Note: This test verifies that validation mode triggers auto-kickoff,
    which creates a project and runs intelligence processing automatically.
    """
    data = {
        "email": "promotion@example.com",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["promo.pdf"]),
        # Enable validation mode for auto-kickoff
        "validation_project": "true",
    }
    r = anon_client.post("/api/intake/upload", files=[_pdf("promo.pdf")], data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    iid = body["intake_id"]
    
    from services.durable_storage import active_data_root
    from services.intake.storage import load_intake_record
    import time
    
    # Auto-kickoff creates a project asynchronously
    # Give it a moment to complete and copy files
    time.sleep(1.0)  # Increase delay for async operations
    
    # Load the intake record to get the project_id
    intake_record = load_intake_record(iid)
    project_id = intake_record.get("project_id")
    assert project_id, f"Project ID not set after auto-kickoff. Intake record: {intake_record}"
    
    evidence_dir = active_data_root() / "projects" / project_id / "evidence"
    
    # Check if the file got promoted to evidence
    assert evidence_dir.is_dir(), "Evidence directory was not created."
    dest_path = evidence_dir / "promo.pdf"
    assert dest_path.is_file(), f"File was not promoted to {dest_path}"
    
    # The EI and Cognition should have run after auto-kickoff
    # Note: Evidence Intelligence may not create review_queue.jsonl in all cases
    
    # Check cognition (runs post-kickoff for validation projects)
    cognition_dir = active_data_root() / "projects" / project_id / "cognition"
    assert (cognition_dir / "cognition_summary.json").exists(), "Cognition did not run after auto-kickoff"

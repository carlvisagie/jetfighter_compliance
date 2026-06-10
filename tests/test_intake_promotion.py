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
    from services.intake.storage import load_intake_record, intake_dir
    import time
    
    # Auto-kickoff happens synchronously during upload processing
    # But filesystem operations may need time to fully complete in full suite context
    time.sleep(1.0)
    
    # Load the intake record to get the project_id
    intake_record = load_intake_record(iid)
    project_id = intake_record.get("project_id")
    assert project_id, f"Project ID not set after auto-kickoff. Intake record: {intake_record}"
    
    # Diagnostic: check both source and destination
    intake_uploads = intake_dir(iid) / "uploads"
    evidence_dir = active_data_root() / "projects" / project_id / "evidence"
    
    # Verify the intake uploads directory exists and has files
    assert intake_uploads.is_dir(), f"Intake uploads directory not created: {intake_uploads}"
    source_files = [f.name for f in intake_uploads.iterdir() if f.is_file()]
    assert "promo.pdf" in source_files, f"Source file not in uploads: {source_files}"
    
    # Check if the file got promoted to evidence
    assert evidence_dir.is_dir(), "Evidence directory was not created."
    
    # Retry loop for file promotion (may need time for filesystem ops)
    dest_path = evidence_dir / "promo.pdf"
    alt_path = evidence_dir / "promo_from_intake.pdf"
    
    max_wait = 5.0
    waited = 0.0
    while not dest_path.is_file() and not alt_path.is_file() and waited < max_wait:
        time.sleep(0.5)
        waited += 0.5
    
    if not dest_path.is_file() and not alt_path.is_file():
        # Diagnostic: list what files actually exist
        actual_items = list(evidence_dir.iterdir()) if evidence_dir.exists() else []
        actual_files = [f.name for f in actual_items if f.is_file()]
        actual_dirs = [d.name for d in actual_items if d.is_dir()]
        assert False, f"File was not promoted after {waited}s. Expected: promo.pdf or promo_from_intake.pdf. Found files: {actual_files}, dirs: {actual_dirs}. Source had: {source_files}"
    
    # Use whichever file exists
    promoted_file = dest_path if dest_path.is_file() else alt_path
    
    # The EI and Cognition should have run after auto-kickoff
    # Note: Evidence Intelligence may not create review_queue.jsonl in all cases
    
    # Check cognition (runs post-kickoff for validation projects)
    cognition_dir = active_data_root() / "projects" / project_id / "cognition"
    cognition_summary = cognition_dir / "cognition_summary.json"
    
    # Cognition may take additional time in full suite context
    max_wait = 3.0
    waited = 0.0
    while not cognition_summary.exists() and waited < max_wait:
        time.sleep(0.5)
        waited += 0.5
    
    assert cognition_summary.exists(), f"Cognition did not run after auto-kickoff (waited {waited}s)"

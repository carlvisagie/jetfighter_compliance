"""Test promotion of uploads from intake to evidence."""
from __future__ import annotations

import io
import json
from fastapi.testclient import TestClient

def _pdf(name: str, content: bytes = b"%PDF-1.4 minimal") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))

def test_intake_files_promoted_to_evidence(fb_env, anon_client: TestClient):
    data = {
        "email": "promotion@example.com",
        "expected_file_count": "1",
        "expected_file_names": json.dumps(["promo.pdf"]),
    }
    r = anon_client.post("/api/intake/upload", files=[_pdf("promo.pdf")], data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    iid = body["intake_id"]
    
    from services.durable_storage import active_data_root
    evidence_dir = active_data_root() / "projects" / iid / "evidence"
    
    # Check if the file got promoted to evidence
    assert evidence_dir.is_dir(), "Evidence directory was not created."
    dest_path = evidence_dir / "promo.pdf"
    assert dest_path.is_file(), f"File was not promoted to {dest_path}"
    
    # The EI and Cognition should have run and handled failures safely
    intel_dir = active_data_root() / "projects" / iid / "evidence_intelligence"
    # Even if EI failed, it should have a review queue item
    assert (intel_dir / "review_queue.jsonl").exists(), "Review queue not written for blind EI"
    
    # Check cognition
    cognition_dir = active_data_root() / "projects" / iid / "cognition"
    assert (cognition_dir / "cognition_summary.json").exists(), "Cognition did not run safely"

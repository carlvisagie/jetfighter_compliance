from __future__ import annotations
import json
from fastapi.testclient import TestClient

def test_retroactive_processing_sweep(fb_env, anon_client: TestClient):
    import io
    # Create an intake manually
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("test.pdf", io.BytesIO(b"%PDF-1.4 minimal"), "application/pdf"))],
        data={"email": "sweep@example.com", "expected_file_count": "1", "expected_file_names": json.dumps(["test.pdf"])},
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    
    from services.durable_storage import active_data_root
    
    # Remove cognition files to simulate staleness
    cog_summary = active_data_root() / "projects" / iid / "cognition" / "cognition_summary.json"
    if cog_summary.exists():
        cog_summary.unlink()
        
    # Run sweep
    from services.evidence_intelligence.freshness import sweep_intakes_for_staleness
    res = sweep_intakes_for_staleness()
    
    # Verify it was reprocessed
    assert any(s["intake_id"] == iid for s in res["stale"]), "Intake should be marked stale"
    assert any(r["intake_id"] == iid for r in res["reprocessed"]), "Intake should be reprocessed"
    
    # Verify cognition ran
    assert cog_summary.exists(), "Cognition should have run during sweep"

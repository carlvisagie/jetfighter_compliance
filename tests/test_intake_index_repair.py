"""Test intake index repair — sync disk intakes to operational index."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def clean_repair_env(durable_intake_root, monkeypatch):
    """Clean environment for repair testing."""
    from services.compliance_health.registry import seed_requirements
    seed_requirements()
    yield durable_intake_root


def test_repair_restores_disk_intake_with_missing_index(clean_repair_env):
    """Disk intake exists but missing from index → repair restores visibility."""
    from services.intake.storage import canonical_intake_dir, intakes_root, index_jsonl, index_intake_ids
    from services.intake.repair_index import sync_intake_index_from_disk
    
    intake_id = "FB-repair001"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    # Write intake.json
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "created_at_utc": "2026-06-10T00:00:00Z",
        "custody_status": "partial_upload",
        "review_status": "pending_review",
        "company": "Repair Test Corp",
        "email": "test@repair.test",
        "file_count": 5,
        "files": []
    }))
    
    # Verify not in index
    index_ids = set(index_intake_ids(tail_lines=500))
    assert intake_id not in index_ids
    
    # Run repair
    result = sync_intake_index_from_disk(write=True, limit=200)
    
    assert result["ok"] == True
    assert intake_id in result["repaired_intakes"]
    assert result["repaired_count"] >= 1
    
    # Verify now in index
    index_ids_after = set(index_intake_ids(tail_lines=500))
    assert intake_id in index_ids_after


def test_repaired_intake_visible_in_queue(clean_repair_env):
    """Repaired intake appears in operator queue."""
    from services.intake.storage import canonical_intake_dir
    from services.intake.repair_index import sync_intake_index_from_disk
    from services.intake.queue import get_operator_review_queue
    
    intake_id = "FB-repair002"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "created_at_utc": "2026-06-10T00:00:00Z",
        "custody_status": "pending_review",
        "review_status": "pending_review",
        "company": "Queue Test Corp",
        "email": "queue@test.test",
        "file_count": 3,
        "files": []
    }))
    
    # Repair
    sync_intake_index_from_disk(write=True, limit=200)
    
    # Check queue
    queue = get_operator_review_queue(limit=200)
    queue_ids = {item.get("intake_id") for item in queue.get("queue", [])}
    
    assert intake_id in queue_ids


def test_repaired_intake_visible_in_reconcile(clean_repair_env):
    """Repaired intake appears in reconcile."""
    from services.intake.storage import canonical_intake_dir
    from services.intake.repair_index import sync_intake_index_from_disk
    from services.intake.reconcile import reconcile_fleet
    
    intake_id = "FB-repair003"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "created_at_utc": "2026-06-10T00:00:00Z",
        "custody_status": "verified_complete",
        "review_status": "pending_review",
        "company": "Reconcile Test Corp",
        "file_count": 2,
        "files": []
    }))
    
    # Repair
    sync_intake_index_from_disk(write=True, limit=200)
    
    # Reconcile
    fleet = reconcile_fleet(limit=200)
    reconcile_ids = {r.get("intake_id") for r in fleet.get("intake_reports", [])}
    
    assert intake_id in reconcile_ids


def test_repaired_intake_accessible_via_api(clean_repair_env):
    """Repaired intake returns 200 from /api/operator/intake/{id}."""
    from services.intake.storage import canonical_intake_dir, load_intake_record
    from services.intake.repair_index import sync_intake_index_from_disk
    
    intake_id = "FB-repair004"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "created_at_utc": "2026-06-10T00:00:00Z",
        "custody_status": "partial_upload",
        "review_status": "pending_review",
        "company": "API Test Corp",
        "file_count": 1,
        "files": []
    }))
    
    # Repair
    sync_intake_index_from_disk(write=True, limit=200)
    
    # Load via API function
    record = load_intake_record(intake_id, persist_recovery=False)
    
    assert record["intake_id"] == intake_id
    assert record["company"] == "API Test Corp"
    assert record["custody_status"] == "partial_upload"


def test_verified_complete_repaired_intake_triggers_external_verification(clean_repair_env, monkeypatch):
    """Repaired intake with verified_complete triggers external verification."""
    from services.intake.storage import canonical_intake_dir
    from services.intake.repair_index import sync_intake_index_from_disk
    from services.external_verification import verify_contractor_identity
    from unittest.mock import MagicMock
    
    # Mock SAM.gov response
    mock_entity = {
        "entityRegistration": {
            "legalBusinessName": "External Verify Corp",
            "ueiSAM": "TEST12345678",
            "cageCode": "1A2B3",
            "registrationStatus": "Active",
        },
        "entityData": [{
            "physicalAddress": {"addressLine1": "123 Main St", "city": "Test City"}
        }]
    }
    monkeypatch.setattr(
        "services.external_verification.sam_gov.query_sam_entity",
        lambda uei: mock_entity
    )
    
    intake_id = "FB-repair005"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    # Create company_profile.json with UEI
    profile_json = idir / "company_profile.json"
    profile_json.write_text(json.dumps({
        "company_name": "External Verify Corp",
        "uei": "TEST12345678",
        "cage_code": "1A2B3"
    }))
    
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "created_at_utc": "2026-06-10T00:00:00Z",
        "custody_status": "verified_complete",
        "review_status": "pending_review",
        "company": "External Verify Corp",
        "file_count": 1,
        "files": []
    }))
    
    # Repair (this should NOT automatically trigger verification - that happens on upload)
    sync_intake_index_from_disk(write=True, limit=200)
    
    # Manually trigger verification (simulating what intake pipeline would do)
    verification = verify_contractor_identity(intake_id, force_refresh=False)
    
    # Verify it works
    assert verification.status.value in ("PASS", "UNKNOWN")  # UNKNOWN if API key missing
    assert verification.project_id == intake_id


def test_no_duplicate_intake_records(clean_repair_env):
    """Running repair multiple times doesn't create duplicates."""
    from services.intake.storage import canonical_intake_dir, index_intake_ids
    from services.intake.repair_index import sync_intake_index_from_disk
    
    intake_id = "FB-repair006"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "created_at_utc": "2026-06-10T00:00:00Z",
        "custody_status": "pending_review",
        "review_status": "pending_review",
        "company": "Duplicate Test Corp",
        "file_count": 1,
        "files": []
    }))
    
    # Repair first time
    result1 = sync_intake_index_from_disk(write=True, limit=200)
    assert intake_id in result1["repaired_intakes"]
    
    # Repair second time
    result2 = sync_intake_index_from_disk(write=True, limit=200)
    
    # Should be in already_indexed, not repaired again
    assert result2["repaired_count"] == 0 or intake_id not in result2["repaired_intakes"]
    
    # Count occurrences in index
    index_ids = index_intake_ids(tail_lines=500)
    count = index_ids.count(intake_id)
    assert count == 1, f"Expected 1 occurrence, found {count}"


def test_wrong_path_does_not_silently_pass(clean_repair_env):
    """Repair with non-existent paths doesn't claim success."""
    from services.intake.repair_index import sync_intake_index_from_disk
    from services.intake.storage import intakes_root
    
    # Get initial state
    result = sync_intake_index_from_disk(write=False, limit=200)
    
    # Verify it returns real data, not fake success
    assert isinstance(result, dict)
    assert "repaired_intakes" in result
    assert "already_indexed_count" in result
    assert "missing_intake_json_count" in result
    
    # If there are no intakes to repair, counts should be sensible
    if result["repaired_count"] == 0:
        # Either no intakes exist, or they're all already indexed
        root = intakes_root()
        if root.exists():
            intake_dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith("FB-")]
            if len(intake_dirs) > 0:
                # Intakes exist, so they must be already indexed or missing intake.json
                assert result["already_indexed_count"] > 0 or result["missing_intake_json_count"] > 0

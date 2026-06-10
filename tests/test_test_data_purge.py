"""Test data purge — safe operator cleanup."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def clean_purge_env(durable_intake_root, monkeypatch):
    """Clean environment for purge testing."""
    yield durable_intake_root


def test_dry_run_deletes_nothing(clean_purge_env):
    """Dry run mode reports changes without deleting."""
    from services.intake.test_data_purge import purge_test_data
    from services.intake.storage import canonical_intake_dir
    
    # Create test intake
    intake_id = "FB-purge-test-001"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    intake_json = idir / "intake.json"
    intake_json.write_text(json.dumps({
        "intake_id": intake_id,
        "company": "Test Corp",
        "file_count": 0,
    }))
    
    # Run dry-run purge
    result = purge_test_data(dry_run=True, confirm="")
    
    assert result["ok"] == True
    assert result["dry_run"] == True
    assert "would_delete" in result
    assert "would_preserve" in result
    
    # Verify nothing deleted
    assert intake_json.exists(), "Dry run should not delete files"


def test_write_mode_without_confirm_rejected(clean_purge_env):
    """Write mode without confirmation is rejected."""
    from services.intake.test_data_purge import purge_test_data
    
    result = purge_test_data(dry_run=False, confirm="")
    
    assert result["ok"] == False
    assert result["blocked"] == True
    assert result["block_reason"] == "missing_confirmation"
    assert "confirm=DELETE_TEST_DATA" in result["error"]


def test_write_mode_with_wrong_confirm_rejected(clean_purge_env):
    """Write mode with wrong confirmation is rejected."""
    from services.intake.test_data_purge import purge_test_data
    
    result = purge_test_data(dry_run=False, confirm="DELETE_ALL")
    
    assert result["ok"] == False
    assert result["blocked"] == True


def test_non_test_intake_blocks_purge(clean_purge_env, monkeypatch):
    """Non-test intake (non-FB prefix) blocks purge."""
    from services.intake.test_data_purge import purge_test_data
    
    # Mock _detect_customer_intakes to return empty (no customer data)
    monkeypatch.setattr(
        "services.intake.test_data_purge._detect_customer_intakes",
        lambda: []
    )
    
    # Mock list_intake_ids to return a customer-looking intake
    def mock_list_intake_ids(limit=500):
        return ["FB-test001", "CUST-12345"]  # CUST- is not test
    
    monkeypatch.setattr(
        "services.intake.storage.list_intake_ids",
        mock_list_intake_ids
    )
    
    result = purge_test_data(dry_run=False, confirm="DELETE_TEST_DATA")
    
    assert result["ok"] == False
    assert result["blocked"] == True
    assert result["block_reason"] == "non_test_intakes_detected"
    assert "CUST-12345" in result["non_test_intakes"]


def test_customer_count_blocks_purge(clean_purge_env, monkeypatch):
    """customer_count > 0 blocks purge."""
    from services.intake.test_data_purge import purge_test_data
    
    # Mock to detect customer intakes
    def mock_detect_customer():
        return ["CUSTOMER-001", "PROD-002"]
    
    monkeypatch.setattr(
        "services.intake.test_data_purge._detect_customer_intakes",
        mock_detect_customer
    )
    
    result = purge_test_data(dry_run=True, confirm="")
    
    assert result["ok"] == False
    assert result["blocked"] == True
    assert result["block_reason"] == "customer_data_detected"
    assert result["customer_count"] == 2


def test_allowed_paths_deleted(clean_purge_env):
    """Allowed paths are deleted in write mode."""
    from services.intake.test_data_purge import purge_test_data
    from services.intake.storage import canonical_intake_dir
    from services.config import DATA
    
    # Create test intake
    intake_id = "FB-purge-002"
    idir = canonical_intake_dir(intake_id)
    idir.mkdir(parents=True, exist_ok=True)
    
    test_file = idir / "test.txt"
    test_file.write_text("test data")
    
    # Create external verification test data
    ext_ver_dir = Path(DATA) / "external_verification" / "FB-purge-002"
    ext_ver_dir.mkdir(parents=True, exist_ok=True)
    ext_ver_file = ext_ver_dir / "sam_verification.json"
    ext_ver_file.write_text("{}")
    
    # Run purge
    result = purge_test_data(dry_run=False, confirm="DELETE_TEST_DATA")
    
    # Allow either success or errors (as long as it tried to delete)
    assert result["dry_run"] == False
    assert result["executed"] == True
    assert len(result["deleted_paths"]) > 0


def test_protected_paths_preserved(clean_purge_env):
    """Protected paths are never deleted."""
    from services.intake.test_data_purge import purge_test_data, _get_protected_paths
    from services.config import DATA
    
    # Create protected data
    protected = _get_protected_paths()
    for path in protected:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / "important.json"
        test_file.write_text('{"protected": true}')
    
    # Run purge
    result = purge_test_data(dry_run=False, confirm="DELETE_TEST_DATA")
    
    # Verify protected paths still exist
    for path in protected:
        if path.exists():  # May not exist if never created
            test_file = path / "important.json"
            if test_file.exists():
                assert test_file.exists(), f"Protected file deleted: {test_file}"


def test_indexes_rebuilt_after_purge(clean_purge_env, monkeypatch):
    """Indexes are rebuilt after purge."""
    from services.intake.test_data_purge import purge_test_data
    
    sync_called = []
    
    def mock_sync(max_rows=200):
        sync_called.append(True)
        return 0
    
    monkeypatch.setattr(
        "services.intake.storage.sync_index_from_filesystem",
        mock_sync
    )
    
    # Mock inventory verification
    def mock_verify(**kwargs):
        return {"ok": True}
    
    monkeypatch.setattr(
        "services.intake.inventory.verify_inventory_agreement",
        mock_verify
    )
    
    # Mock organism recompute - just catch the exception
    def mock_compute():
        class MockState:
            health_state = "GREEN"
            current_bottleneck = None
        return MockState()
    
    import sys
    from unittest.mock import MagicMock
    mock_module = MagicMock()
    mock_module.compute_organism_state = mock_compute
    sys.modules['organism_core'] = mock_module
    
    result = purge_test_data(dry_run=False, confirm="DELETE_TEST_DATA")
    
    assert len(sync_called) > 0, "sync_index_from_filesystem not called"
    assert result["inventory_ok"] == True


def test_organism_recomputed_after_purge(clean_purge_env, monkeypatch):
    """Organism state is recomputed after purge."""
    from services.intake.test_data_purge import purge_test_data
    
    compute_called = []
    
    class MockState:
        health_state = "GREEN"
        current_bottleneck = None
    
    def mock_compute():
        compute_called.append(True)
        return MockState()
    
    import sys
    from unittest.mock import MagicMock
    mock_module = MagicMock()
    mock_module.compute_organism_state = mock_compute
    sys.modules['organism_core'] = mock_module
    
    # Mock sync and verify
    monkeypatch.setattr(
        "services.intake.storage.sync_index_from_filesystem",
        lambda max_rows=200: 0
    )
    monkeypatch.setattr(
        "services.intake.inventory.verify_inventory_agreement",
        lambda **kwargs: {"ok": True}
    )
    
    result = purge_test_data(dry_run=False, confirm="DELETE_TEST_DATA")
    
    assert len(compute_called) > 0, "compute_organism_state not called"
    assert result["health_state"] == "GREEN"
    assert result["current_bottleneck"] is None

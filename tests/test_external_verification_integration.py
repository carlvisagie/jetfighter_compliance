"""Integration tests for External Verification in Intake Pipeline (PATCH 13A-2)."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from services.external_verification import get_verification, verify_contractor_identity
from services.compliance_health.registry import get_requirement
from services.compliance_health.schemas import RequirementStatus


@pytest.fixture
def clean_intake_integration(tmp_path, monkeypatch):
    """Clean state for intake integration testing."""
    import services.config
    monkeypatch.setattr(services.config, "DATA", tmp_path / "data")
    # Initialize compliance health requirements
    from services.compliance_health.registry import seed_requirements
    seed_requirements()
    yield tmp_path


def test_verified_intake_triggers_external_verification(clean_intake_integration, monkeypatch, client):
    """Test that reaching verified_complete triggers external verification."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    # Mock SAM.gov API response
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "TEST123UEI456",
                "cageCode": "TEST1",
                "entityName": "Test Trigger Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    # Create test intake with company_profile.json
    from services.intake.storage import ensure_canonical_intake_dir
    intake_id = "FB-trigger-test"
    intake_dir = ensure_canonical_intake_dir(intake_id)
    
    profile = {
        "legal_name": "Test Trigger Company LLC",
        "uei": "TEST123UEI456",
        "cage_code": "TEST1",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    # Simulate intake reaching verified_complete
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        from services.intake.intake import _trigger_external_verification_if_complete
        
        record = {
            "intake_id": intake_id,
            "custody_status": "verified_complete",
        }
        
        # Trigger should run
        _trigger_external_verification_if_complete(record)
    
    # Verify that verification was created
    verification = get_verification(intake_id)
    assert verification is not None
    assert verification.project_id == intake_id
    assert verification.status.value == "PASS"
    
    # Verify that compliance health was updated
    sam_req = get_requirement("sam_registration")
    assert sam_req is not None
    assert sam_req.status == RequirementStatus.PASS


def test_missing_api_key_does_not_block_pipeline(clean_intake_integration, monkeypatch):
    """Test that missing SAM_GOV_API_KEY results in UNKNOWN but doesn't block intake."""
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    
    from services.intake.storage import ensure_canonical_intake_dir
    intake_id = "FB-no-api-key"
    intake_dir = ensure_canonical_intake_dir(intake_id)
    
    profile = {
        "legal_name": "Test No API Company",
        "uei": "NOAPI123",
        "cage_code": "TEST1",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    # Trigger verification without API key
    from services.intake.intake import _trigger_external_verification_if_complete
    
    record = {
        "intake_id": intake_id,
        "custody_status": "verified_complete",
    }
    
    # Should not raise exception
    _trigger_external_verification_if_complete(record)
    
    # Verify that verification was created with UNKNOWN status
    verification = get_verification(intake_id)
    assert verification is not None
    assert verification.status.value == "UNKNOWN"
    assert verification.confidence == 0.0
    
    # Compliance health should be UNKNOWN (not PASS, not FAIL)
    sam_req = get_requirement("sam_registration")
    assert sam_req.status == RequirementStatus.UNKNOWN
    uei_req = get_requirement("uei_verification")
    assert uei_req.status == RequirementStatus.UNKNOWN
    cage_req = get_requirement("cage_verification")
    assert cage_req.status == RequirementStatus.UNKNOWN


def test_exact_match_updates_compliance_health_to_pass(clean_intake_integration, monkeypatch):
    """Test that exact SAM.gov match updates compliance health requirements to PASS."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "EXACT123UEI456",
                "cageCode": "EXACT",
                "entityName": "Exact Match Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    from services.intake.storage import ensure_canonical_intake_dir
    intake_id = "FB-exact-match"
    intake_dir = ensure_canonical_intake_dir(intake_id)
    
    profile = {
        "legal_name": "Exact Match Company LLC",
        "uei": "EXACT123UEI456",
        "cage_code": "EXACT",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        verification = verify_contractor_identity(intake_id)
    
    assert verification.status.value == "PASS"
    
    # Check all three requirements
    sam_req = get_requirement("sam_registration")
    assert sam_req.status == RequirementStatus.PASS
    assert sam_req.confidence > 0.8
    
    uei_req = get_requirement("uei_verification")
    assert uei_req.status == RequirementStatus.PASS
    
    cage_req = get_requirement("cage_verification")
    assert cage_req.status == RequirementStatus.PASS


def test_mismatch_updates_compliance_health_to_fail(clean_intake_integration, monkeypatch):
    """Test that UEI/CAGE mismatch updates compliance health requirements to FAIL."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "WRONG123UEI456",  # Different from claimed
                "cageCode": "WRONG",  # Different from claimed
                "entityName": "Mismatch Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    from services.intake.storage import ensure_canonical_intake_dir
    intake_id = "FB-mismatch"
    intake_dir = ensure_canonical_intake_dir(intake_id)
    
    profile = {
        "legal_name": "Mismatch Company LLC",
        "uei": "CLAIMED123UEI",
        "cage_code": "CLAIM",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        verification = verify_contractor_identity(intake_id)
    
    assert verification.status.value == "FAIL"
    
    # UEI and CAGE should be FAIL
    uei_req = get_requirement("uei_verification")
    assert uei_req.status == RequirementStatus.FAIL
    
    cage_req = get_requirement("cage_verification")
    assert cage_req.status == RequirementStatus.FAIL


def test_endpoint_returns_persisted_result(clean_intake_integration, monkeypatch, client):
    """Test that operator endpoint returns the persisted verification result."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "ENDPOINT123UEI",
                "cageCode": "ENDPT",
                "entityName": "Endpoint Test Company",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {
                    "addressLine1": "123 Test St",
                    "city": "Springfield",
                    "stateOrProvinceCode": "VA",
                    "zipCode": "22150",
                },
            }
        }
    }
    
    from services.intake.storage import ensure_canonical_intake_dir
    intake_id = "FB-endpoint-test"
    intake_dir = ensure_canonical_intake_dir(intake_id)
    
    profile = {
        "legal_name": "Endpoint Test Company",
        "uei": "ENDPOINT123UEI",
        "cage_code": "ENDPT",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    # Create verification
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        verification = verify_contractor_identity(intake_id)
    
    # Call operator endpoint (client is already authenticated)
    response = client.get(f"/api/operator/external-verification/{intake_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["project_id"] == intake_id
    assert data["status"] == "PASS"
    assert data["sam_status"] == "ACTIVE"
    assert data["uei_status"] == "PASS"
    assert data["cage_status"] == "PASS"
    assert data["uei_claimed"] == "ENDPOINT123UEI"
    assert data["cage_claimed"] == "ENDPT"
    assert data["matched_legal_name"] == "Endpoint Test Company"
    assert "123 Test St" in data["matched_address"]
    assert data["active_registration"] is True
    assert data["confidence"] > 0.8


def test_endpoint_returns_404_for_no_verification(clean_intake_integration, client):
    """Test that endpoint returns 404 when no verification exists."""
    # Try to get non-existent verification (client is already authenticated)
    response = client.get("/api/operator/external-verification/FB-nonexistent")
    
    assert response.status_code == 404
    assert "verification" in response.json()["detail"].lower()


def test_no_fake_pass_in_pipeline(clean_intake_integration, monkeypatch):
    """Test that pipeline never generates fake PASS values."""
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    
    from services.intake.storage import ensure_canonical_intake_dir
    intake_id = "FB-no-fake-pass"
    intake_dir = ensure_canonical_intake_dir(intake_id)
    
    profile = {
        "legal_name": "No Fake Pass Company",
        "uei": "NOFAKE123",
        "cage_code": "FAKE1",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    # Trigger without API key
    from services.intake.intake import _trigger_external_verification_if_complete
    
    record = {
        "intake_id": intake_id,
        "custody_status": "verified_complete",
    }
    
    _trigger_external_verification_if_complete(record)
    
    verification = get_verification(intake_id)
    
    # Without API key, should be UNKNOWN, never PASS
    assert verification.status.value != "PASS"
    assert verification.status.value == "UNKNOWN"
    
    # Compliance health should not be PASS
    sam_req = get_requirement("sam_registration")
    assert sam_req.status != RequirementStatus.PASS
    
    uei_req = get_requirement("uei_verification")
    assert uei_req.status != RequirementStatus.PASS
    
    cage_req = get_requirement("cage_verification")
    assert cage_req.status != RequirementStatus.PASS


def test_trigger_only_fires_on_verified_complete(clean_intake_integration):
    """Test that trigger only runs when custody_status is verified_complete."""
    from services.intake.intake import _trigger_external_verification_if_complete
    
    # Try with partial_upload status
    record = {
        "intake_id": "FB-partial",
        "custody_status": "partial_upload",
    }
    
    _trigger_external_verification_if_complete(record)
    
    # Should not create verification
    verification = get_verification("FB-partial")
    assert verification is None
    
    # Try with verified_complete
    from services.intake.storage import ensure_canonical_intake_dir
    intake_dir = ensure_canonical_intake_dir("FB-complete")
    profile = {"legal_name": "Complete Company", "uei": "COMPLETE123"}
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    record = {
        "intake_id": "FB-complete",
        "custody_status": "verified_complete",
    }
    
    _trigger_external_verification_if_complete(record)
    
    # Should create verification
    verification = get_verification("FB-complete")
    assert verification is not None

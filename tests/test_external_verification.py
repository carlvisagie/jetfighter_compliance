"""Tests for External Verification (PATCH 13A-1)."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from services.external_verification import (
    verify_contractor_identity,
    get_verification,
    ExternalEntityVerification,
    VerificationStatus,
    SAMRegistrationStatus,
    ExclusionStatus,
)
from services.external_verification.sam_gov import (
    verify_sam_registration,
    is_api_configured,
)
from services.external_verification.storage import (
    save_verification,
    load_verification,
)
from services.compliance_health.registry import (
    load_requirements,
    get_requirement,
)


@pytest.fixture
def clean_external_verification(tmp_path, monkeypatch):
    """Clean external verification state for testing."""
    import services.config
    monkeypatch.setattr(services.config, "DATA", tmp_path / "data")
    yield tmp_path


def test_missing_api_key_returns_unknown(clean_external_verification, monkeypatch):
    """Test that missing SAM_GOV_API_KEY results in UNKNOWN status."""
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    
    result = verify_sam_registration(
        uei_claimed="ABC123DEF456",
        cage_claimed="1A2B3",
        legal_name_claimed="Test Company LLC",
    )
    
    assert result["sam_status"] == SAMRegistrationStatus.UNKNOWN
    assert result["uei_status"] == VerificationStatus.UNKNOWN
    assert result["cage_status"] == VerificationStatus.UNKNOWN
    assert result["registration_status"] == VerificationStatus.UNKNOWN
    assert result["source_checked_utc"] is None
    assert len(result["issues"]) == 1
    assert "API key not configured" in result["issues"][0]["detail"]


def test_missing_claimed_uei_returns_unknown(clean_external_verification, monkeypatch):
    """Test that missing claimed UEI results in UNKNOWN status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    result = verify_sam_registration(
        uei_claimed=None,
        cage_claimed="1A2B3",
        legal_name_claimed="Test Company LLC",
    )
    
    assert result["uei_status"] == VerificationStatus.UNKNOWN
    assert result["source_checked_utc"] is None
    assert any("No UEI claimed" in issue["detail"] for issue in result["issues"])


def test_exact_sam_match_returns_pass(clean_external_verification, monkeypatch):
    """Test that exact SAM.gov match results in PASS status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    # Mock SAM.gov API response (exact match)
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "ABC123DEF456",
                "cageCode": "1A2B3",
                "entityName": "Test Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {
                    "addressLine1": "123 Main St",
                    "city": "Springfield",
                    "stateOrProvinceCode": "VA",
                    "zipCode": "22150",
                },
            }
        }
    }
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["sam_status"] == SAMRegistrationStatus.ACTIVE
    assert result["uei_status"] == VerificationStatus.PASS
    assert result["cage_status"] == VerificationStatus.PASS
    assert result["registration_status"] == VerificationStatus.PASS
    assert result["active_registration"] is True
    assert result["exclusions_status"] == ExclusionStatus.CLEAR
    assert result["matched_legal_name"] == "Test Company LLC"
    assert result["source_checked_utc"] is not None
    assert len([i for i in result["issues"] if i["severity"] == "critical"]) == 0


def test_legal_name_mismatch_returns_warning(clean_external_verification, monkeypatch):
    """Test that legal name mismatch creates warning but doesn't fail verification."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "ABC123DEF456",
                "cageCode": "1A2B3",
                "entityName": "Test Company Incorporated",  # Different from claimed
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["uei_status"] == VerificationStatus.PASS
    assert result["cage_status"] == VerificationStatus.PASS
    assert any(
        "Legal name does not exactly match" in issue["detail"]
        and issue["severity"] == "warning"
        for issue in result["issues"]
    )


def test_uei_mismatch_returns_fail(clean_external_verification, monkeypatch):
    """Test that UEI mismatch results in FAIL status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "WRONG123UEI456",  # Different from claimed
                "cageCode": "1A2B3",
                "entityName": "Test Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["uei_status"] == VerificationStatus.FAIL
    assert any(
        "UEI mismatch" in issue["detail"]
        and issue["severity"] == "critical"
        for issue in result["issues"]
    )


def test_cage_mismatch_returns_fail(clean_external_verification, monkeypatch):
    """Test that CAGE mismatch results in FAIL status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "ABC123DEF456",
                "cageCode": "WRONG",  # Different from claimed
                "entityName": "Test Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["cage_status"] == VerificationStatus.FAIL
    assert any(
        "CAGE code mismatch" in issue["detail"]
        and issue["severity"] == "critical"
        for issue in result["issues"]
    )


def test_inactive_registration_returns_fail(clean_external_verification, monkeypatch):
    """Test that inactive SAM registration results in FAIL status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "ABC123DEF456",
                "cageCode": "1A2B3",
                "entityName": "Test Company LLC",
                "registrationStatus": "INACTIVE",  # Not active
                "physicalAddress": {},
            }
        }
    }
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["sam_status"] == SAMRegistrationStatus.INACTIVE
    assert result["registration_status"] == VerificationStatus.FAIL
    assert result["active_registration"] is False
    assert any(
        "registration is INACTIVE" in issue["detail"]
        and issue["severity"] == "critical"
        for issue in result["issues"]
    )


def test_uei_not_found_returns_fail(clean_external_verification, monkeypatch):
    """Test that UEI not found in SAM.gov results in FAIL status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value={"status": "not_found", "uei": "ABC123DEF456"}):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["sam_status"] == SAMRegistrationStatus.NOT_FOUND
    assert result["uei_status"] == VerificationStatus.FAIL
    assert result["registration_status"] == VerificationStatus.FAIL
    assert any(
        "UEI not found in SAM.gov" in issue["detail"]
        and issue["severity"] == "critical"
        for issue in result["issues"]
    )


def test_api_failure_returns_unknown(clean_external_verification, monkeypatch):
    """Test that SAM.gov API failure results in UNKNOWN status."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=None):
        result = verify_sam_registration(
            uei_claimed="ABC123DEF456",
            cage_claimed="1A2B3",
            legal_name_claimed="Test Company LLC",
        )
    
    assert result["sam_status"] == SAMRegistrationStatus.UNKNOWN
    assert result["uei_status"] == VerificationStatus.UNKNOWN
    assert result["source_checked_utc"] is not None
    assert any("API request failed or timed out" in issue["detail"] for issue in result["issues"])


def test_verification_storage_persistence(clean_external_verification):
    """Test that verification results persist correctly."""
    verification = ExternalEntityVerification(
        project_id="TEST-001",
        legal_name_claimed="Test Company",
        uei_claimed="ABC123",
        cage_claimed="1A2B3",
        sam_status=SAMRegistrationStatus.ACTIVE,
        uei_status=VerificationStatus.PASS,
        cage_status=VerificationStatus.PASS,
        registration_status=VerificationStatus.PASS,
        status=VerificationStatus.PASS,
        confidence=0.9,
    )
    
    # Save
    path = save_verification(verification)
    assert path.is_file()
    
    # Load
    loaded = load_verification("TEST-001")
    assert loaded is not None
    assert loaded.project_id == "TEST-001"
    assert loaded.uei_claimed == "ABC123"
    assert loaded.status == VerificationStatus.PASS


def test_no_fake_pass_values(clean_external_verification, monkeypatch):
    """Test that system never generates fake PASS values."""
    monkeypatch.delenv("SAM_GOV_API_KEY", raising=False)
    
    # Without API key, everything should be UNKNOWN, not PASS
    result = verify_sam_registration(
        uei_claimed="ABC123DEF456",
        cage_claimed="1A2B3",
        legal_name_claimed="Test Company LLC",
    )
    
    assert result["uei_status"] != VerificationStatus.PASS
    assert result["cage_status"] != VerificationStatus.PASS
    assert result["registration_status"] != VerificationStatus.PASS
    assert result["sam_status"] != SAMRegistrationStatus.ACTIVE
    
    # Verify compute_status never fakes PASS
    verification = ExternalEntityVerification(
        project_id="TEST-001",
        uei_claimed="ABC123",
        sam_status=SAMRegistrationStatus.UNKNOWN,
        uei_status=VerificationStatus.UNKNOWN,
        cage_status=VerificationStatus.UNKNOWN,
        registration_status=VerificationStatus.UNKNOWN,
    )
    
    assert verification.compute_status() != VerificationStatus.PASS


def test_feeds_compliance_health_registry(clean_external_verification, monkeypatch):
    """Test that verification results feed compliance health registry."""
    monkeypatch.setenv("SAM_GOV_API_KEY", "test-key-123")
    
    # Create test project with company_profile.json
    data_dir = clean_external_verification / "data"
    intake_dir = data_dir / "intake" / "TEST-FEED"
    intake_dir.mkdir(parents=True, exist_ok=True)
    
    profile = {
        "legal_name": "Test Company LLC",
        "uei": "ABC123DEF456",
        "cage_code": "1A2B3",
    }
    (intake_dir / "company_profile.json").write_text(json.dumps(profile), encoding="utf-8")
    
    # Mock SAM.gov API response
    mock_entity = {
        "coreData": {
            "entityInformation": {
                "ueiSAM": "ABC123DEF456",
                "cageCode": "1A2B3",
                "entityName": "Test Company LLC",
                "registrationStatus": "ACTIVE",
                "physicalAddress": {},
            }
        }
    }
    
    with patch("services.external_verification.sam_gov.query_sam_entity", return_value=mock_entity):
        # Run verification
        verification = verify_contractor_identity("TEST-FEED")
    
    assert verification.status == VerificationStatus.PASS
    assert verification.confidence > 0.8
    
    # Check compliance health registry was updated
    sam_req = get_requirement("sam_registration")
    uei_req = get_requirement("uei_verification")
    cage_req = get_requirement("cage_verification")
    
    assert sam_req is not None
    assert sam_req.status.value == "PASS"
    assert sam_req.confidence > 0.8
    
    assert uei_req is not None
    assert uei_req.status.value == "PASS"
    
    assert cage_req is not None
    assert cage_req.status.value == "PASS"


def test_compute_status_logic(clean_external_verification):
    """Test status computation logic."""
    # FAIL: Component failed
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        uei_status=VerificationStatus.FAIL,
        cage_status=VerificationStatus.PASS,
        registration_status=VerificationStatus.PASS,
        sam_status=SAMRegistrationStatus.ACTIVE,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_status() == VerificationStatus.FAIL
    
    # FAIL: Excluded
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        uei_status=VerificationStatus.PASS,
        cage_status=VerificationStatus.PASS,
        registration_status=VerificationStatus.PASS,
        sam_status=SAMRegistrationStatus.ACTIVE,
        exclusions_status=ExclusionStatus.EXCLUDED,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_status() == VerificationStatus.FAIL
    
    # UNKNOWN: No source check
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        uei_status=VerificationStatus.UNKNOWN,
        cage_status=VerificationStatus.UNKNOWN,
        registration_status=VerificationStatus.UNKNOWN,
        source_checked_utc=None,
    )
    assert v.compute_status() == VerificationStatus.UNKNOWN
    
    # UNKNOWN: Missing claimed UEI
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed=None,
        uei_status=VerificationStatus.UNKNOWN,
        cage_status=VerificationStatus.UNKNOWN,
        registration_status=VerificationStatus.UNKNOWN,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_status() == VerificationStatus.UNKNOWN
    
    # PASS: All components passed
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        uei_status=VerificationStatus.PASS,
        cage_status=VerificationStatus.PASS,
        registration_status=VerificationStatus.PASS,
        sam_status=SAMRegistrationStatus.ACTIVE,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_status() == VerificationStatus.PASS


def test_compute_confidence_logic(clean_external_verification):
    """Test confidence computation logic."""
    # No verification
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        source_checked_utc=None,
    )
    assert v.compute_confidence() == 0.0
    
    # FAIL: High confidence
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        status=VerificationStatus.FAIL,
        uei_status=VerificationStatus.FAIL,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_confidence() == 0.95
    
    # UNKNOWN: No confidence
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        status=VerificationStatus.UNKNOWN,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_confidence() == 0.0
    
    # PASS: Full verification
    v = ExternalEntityVerification(
        project_id="TEST",
        uei_claimed="ABC",
        status=VerificationStatus.PASS,
        uei_status=VerificationStatus.PASS,
        cage_status=VerificationStatus.PASS,
        registration_status=VerificationStatus.PASS,
        sam_status=SAMRegistrationStatus.ACTIVE,
        source_checked_utc="2026-06-09T20:00:00Z",
    )
    assert v.compute_confidence() == 0.9

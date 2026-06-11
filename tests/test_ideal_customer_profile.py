"""PATCH 13A-12: Tests for Ideal Customer Profile and Customer Intelligence."""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def icp_env(monkeypatch, tmp_path):
    """Set up isolated environment for ICP tests."""
    data = tmp_path / "data"
    data.mkdir()
    intel = data / "acquisition" / "intelligence"
    intel.mkdir(parents=True)
    
    monkeypatch.setattr("services.config.DATA", data)
    return data


def test_evidenced_value_known_state():
    """EvidencedValue should properly track KNOWN state."""
    from services.acquisition.ideal_customer_profile import EvidencedValue, SignalState
    
    ev = EvidencedValue(
        value=1000000,
        source="USASpending",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    
    assert ev.value == 1000000
    assert ev.source == "USASpending"
    assert ev.confidence == 0.95
    assert ev.state == SignalState.KNOWN


def test_evidenced_value_unknown_state():
    """EvidencedValue.unknown() should create UNKNOWN state with no value."""
    from services.acquisition.ideal_customer_profile import EvidencedValue, SignalState
    
    ev = EvidencedValue.unknown("contract_value")
    
    assert ev.value is None
    assert ev.source == "none"
    assert ev.confidence == 0.0
    assert ev.state == SignalState.UNKNOWN


def test_customer_intelligence_record_default_unknown():
    """CustomerIntelligenceRecord should start with all fields UNKNOWN."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord()
    
    # All intelligence fields should be UNKNOWN by default
    assert record.company_name.state == SignalState.UNKNOWN
    assert record.uei.state == SignalState.UNKNOWN
    assert record.contract_value.state == SignalState.UNKNOWN
    assert record.dod_exposure.state == SignalState.UNKNOWN
    assert record.cmmc_likelihood.state == SignalState.UNKNOWN


def test_intelligence_completeness_empty_record():
    """Empty record should have very low intelligence completeness."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    
    record = CustomerIntelligenceRecord()
    completeness = record.compute_intelligence_completeness()
    
    assert completeness == 0, "Empty record should have 0% completeness"


def test_intelligence_completeness_partial_record():
    """Partial record should have proportional completeness."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord()
    
    # Add company name (10 points)
    record.company_name = EvidencedValue(
        value="Test Corp",
        source="manual",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    # Add UEI (10 points)
    record.uei = EvidencedValue(
        value="ABC123",
        source="USASpending",
        confidence=0.99,
        state=SignalState.KNOWN,
    )
    
    completeness = record.compute_intelligence_completeness()
    assert completeness == 20, "Company name (10) + UEI (10) = 20%"


def test_icp_match_no_data():
    """Record with no data should not match any ICP tier."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        ICPTier,
    )
    
    record = CustomerIntelligenceRecord()
    icp = record.get_icp_match()
    
    assert icp["tier"] == ICPTier.NO_MATCH.value
    assert icp["recommendation"] in ("IGNORE", "ENRICH")


def test_icp_match_tier_3():
    """Record with only contract count should match Tier 3."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        ICPTier,
    )
    
    record = CustomerIntelligenceRecord()
    record.contract_count = EvidencedValue(
        value=5,
        source="USASpending",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    icp = record.get_icp_match()
    
    # Should at least be Tier 3 (federal award recipient)
    assert icp["tier"] in (ICPTier.TIER_3.value, ICPTier.TIER_2.value, ICPTier.TIER_1.value)
    assert "is_federal_award_recipient" in icp.get("criteria_met", []) or \
           "is_government_contractor" in icp.get("criteria_met", []) or \
           "is_active_federal_contractor" in icp.get("criteria_met", [])


def test_create_intelligence_from_discovery(icp_env):
    """Discovery should create minimal intelligence record with honest UNKNOWN states."""
    from services.acquisition.ideal_customer_profile import (
        create_intelligence_from_discovery,
        SignalState,
    )
    
    record = create_intelligence_from_discovery(
        company_name="Test Defense Corp",
        uei="XYZ789",
        location="Virginia",
        source="usaspending_public_api",
    )
    
    # Known fields should be KNOWN
    assert record.company_name.state == SignalState.KNOWN
    assert record.company_name.value == "Test Defense Corp"
    
    assert record.uei.state == SignalState.KNOWN
    assert record.uei.value == "XYZ789"
    
    # Unknown fields should be UNKNOWN
    assert record.contract_value.state == SignalState.UNKNOWN
    assert record.dod_exposure.state == SignalState.UNKNOWN
    assert record.cmmc_likelihood.state == SignalState.UNKNOWN


def test_icp_definition_structure():
    """ICP definition should have proper structure."""
    from services.acquisition.ideal_customer_profile import get_icp_definition
    
    icp = get_icp_definition()
    
    assert "version" in icp
    assert "tier_1" in icp
    assert "tier_2" in icp
    assert "tier_3" in icp
    
    # Tier 1 should be highest priority
    assert icp["tier_1"]["name"] == "Highest Priority"
    assert "criteria" in icp["tier_1"]


def test_contactability_score_no_contact():
    """No contact info should result in zero contactability."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    
    record = CustomerIntelligenceRecord()
    contactability = record.compute_contactability()
    
    assert contactability == 0


def test_contactability_score_with_email():
    """Email should contribute to contactability."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord()
    record.contact_email = EvidencedValue(
        value="ceo@testcorp.com",
        source="manual",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    contactability = record.compute_contactability()
    
    # Business email = 40 + 20 = 60
    assert contactability >= 60


def test_ability_to_pay_unknown():
    """Unknown contract value should result in zero ability to pay."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    
    record = CustomerIntelligenceRecord()
    ability = record.compute_ability_to_pay()
    
    assert ability == 0, "Unknown contract value = unknown ability to pay"


def test_ability_to_pay_known_value():
    """Known contract value should compute ability to pay."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord()
    record.contract_value = EvidencedValue(
        value=2_500_000,
        source="USASpending",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    
    ability = record.compute_ability_to_pay()
    
    # $2.5M should give high ability score
    assert ability >= 80


def test_record_serialization(icp_env):
    """CustomerIntelligenceRecord should serialize and deserialize correctly."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord()
    record.record_id = "INT-TEST-001"
    record.company_name = EvidencedValue(
        value="Serialize Corp",
        source="test",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    # Serialize
    data = record.to_dict()
    
    # Deserialize
    restored = CustomerIntelligenceRecord.from_dict(data)
    
    assert restored.record_id == "INT-TEST-001"
    assert restored.company_name.value == "Serialize Corp"
    assert restored.company_name.state == SignalState.KNOWN


def test_intelligence_summary_empty(icp_env):
    """Empty intelligence store should return zeros."""
    from services.acquisition.ideal_customer_profile import get_intelligence_summary
    
    summary = get_intelligence_summary()
    
    assert summary["total_records"] == 0
    assert summary["contactable"] == 0
    assert summary["average_completeness"] == 0

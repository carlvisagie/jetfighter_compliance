"""Tests for PATCH 13A-19: Decision Maker Intelligence Engine.

Validates:
1. Procurement relevance scoring (title tiers)
2. Decision maker extraction
3. Decision maker metrics
4. DECISION_MAKER_READY recommendation
5. No outreach during enrichment (safety)
"""
import pytest
from pathlib import Path
from datetime import datetime, timezone


def test_title_relevance_scoring():
    """Test procurement relevance scoring for different titles."""
    from services.acquisition.decision_maker_intelligence import (
        compute_title_relevance_score,
        get_title_tier,
    )
    
    # Tier 1 titles (score 100)
    assert compute_title_relevance_score("President") == 100
    assert compute_title_relevance_score("Owner") == 100
    assert compute_title_relevance_score("CEO") == 100
    assert compute_title_relevance_score("Chief Executive Officer") == 100
    assert compute_title_relevance_score("Founder") == 100
    assert compute_title_relevance_score("Managing Member") == 100
    
    # Tier 2 titles (score 75)
    assert compute_title_relevance_score("Contracts Manager") == 75
    assert compute_title_relevance_score("Compliance Manager") == 75
    assert compute_title_relevance_score("Quality Manager") == 75
    assert compute_title_relevance_score("Operations Manager") == 75
    
    # Tier 3 titles (score 50)
    assert compute_title_relevance_score("Office Manager") == 50
    assert compute_title_relevance_score("General Contact") == 50
    
    # Unknown titles (score 25)
    assert compute_title_relevance_score("Software Developer") == 25
    
    # No title (score 0)
    assert compute_title_relevance_score("") == 0
    assert compute_title_relevance_score(None) == 0


def test_title_tier_assignment():
    """Test tier assignment based on title."""
    from services.acquisition.decision_maker_intelligence import get_title_tier
    
    assert get_title_tier("President") == "TIER_1"
    assert get_title_tier("Owner") == "TIER_1"
    assert get_title_tier("Contracts Manager") == "TIER_2"
    assert get_title_tier("Compliance Director") == "TIER_2"
    assert get_title_tier("Office Manager") == "TIER_3"
    assert get_title_tier("Software Engineer") == "OTHER"
    assert get_title_tier("") == "NONE"


def test_decision_maker_metrics_computation(monkeypatch, tmp_path):
    """Test computation of decision maker metrics."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.decision_maker_intelligence import (
        compute_decision_maker_metrics,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create test records
    
    # Record 1: Has decision maker (tier 1)
    record1 = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp 1", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record1.decision_maker_name = EvidencedValue(
        value="John Smith",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record1.decision_maker_title = EvidencedValue(
        value="President",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record1.contact_email = EvidencedValue(
        value="john@test.com",
        source="Website",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    save_intelligence_record(record1)
    
    # Record 2: Has decision maker (tier 2)
    record2 = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp 2", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record2.decision_maker_name = EvidencedValue(
        value="Jane Doe",
        source="Website",
        confidence=0.7,
        state=SignalState.KNOWN,
    )
    record2.decision_maker_title = EvidencedValue(
        value="Contracts Manager",
        source="Website",
        confidence=0.7,
        state=SignalState.KNOWN,
    )
    save_intelligence_record(record2)
    
    # Record 3: No decision maker
    record3 = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp 3", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    save_intelligence_record(record3)
    
    # Compute metrics
    metrics = compute_decision_maker_metrics()
    
    assert metrics["decision_maker_entities"] == 2
    assert metrics["procurement_relevant_entities"] == 2
    assert metrics["decision_maker_ready_entities"] == 1  # Record 1 has email + high confidence


def test_decision_maker_recommendation(monkeypatch, tmp_path):
    """Test DECISION_MAKER_READY recommendation criteria."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.decision_maker_intelligence import (
        compute_decision_maker_recommendation,
        DecisionMakerRecommendation,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # DECISION_MAKER_READY: all criteria met
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.decision_maker_name = EvidencedValue(
        value="John Smith",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record.decision_maker_title = EvidencedValue(
        value="President",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record.contact_email = EvidencedValue(
        value="john@test.com",
        source="Website",
        confidence=0.85,
        state=SignalState.KNOWN,
    )
    
    recommendation, reasoning = compute_decision_maker_recommendation(record)
    assert recommendation == DecisionMakerRecommendation.DECISION_MAKER_READY
    assert "TIER_1" in reasoning
    
    # Has email but no decision maker
    record2 = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp 2", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record2.contact_email = EvidencedValue(
        value="info@test.com",
        source="Website",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    recommendation2, reasoning2 = compute_decision_maker_recommendation(record2)
    assert recommendation2 == DecisionMakerRecommendation.CONTACTABLE
    
    # Has website but no contact/decision maker
    record3 = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp 3", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record3.website = EvidencedValue(
        value="https://example.com",
        source="Discovery",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    recommendation3, reasoning3 = compute_decision_maker_recommendation(record3)
    assert recommendation3 == DecisionMakerRecommendation.ENRICH


def test_procurement_relevant_report(monkeypatch, tmp_path):
    """Test procurement relevant report generation."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.decision_maker_intelligence import (
        generate_procurement_relevant_report,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create test record
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.decision_maker_name = EvidencedValue(
        value="John Smith",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record.decision_maker_title = EvidencedValue(
        value="President",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record.contact_email = EvidencedValue(
        value="john@test.com",
        source="Website",
        confidence=0.85,
        state=SignalState.KNOWN,
    )
    record.contract_value = EvidencedValue(
        value=1500000,
        source="USASpending",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    save_intelligence_record(record)
    
    # Generate report
    report = generate_procurement_relevant_report(limit=20)
    
    assert report["ok"] is True
    assert report["total_records"] == 1
    assert len(report["top_procurement_relevant"]) == 1
    
    top = report["top_procurement_relevant"][0]
    assert top["company"] == "Test Corp"
    assert top["decision_maker"] == "John Smith"
    assert top["title"] == "President"
    assert top["title_tier"] == "TIER_1"
    assert top["contact_email"] == "john@test.com"
    assert top["recommendation"] == "DECISION_MAKER_READY"
    
    # Verify organism answer
    assert report["organism_answer"]["question"] == "Who specifically should we contact?"
    assert report["organism_answer"]["answer"] is not None


def test_no_outreach_during_enrichment(monkeypatch, tmp_path):
    """SAFETY: Verify no outreach occurs during decision maker enrichment."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.decision_maker_intelligence import (
        enrich_decision_maker_intelligence,
        enrich_all_decision_maker_intelligence,
    )
    
    # Track any outreach attempts
    outreach_attempts = []
    
    def mock_outreach(*args, **kwargs):
        outreach_attempts.append((args, kwargs))
        raise AssertionError("OUTREACH ATTEMPTED - SAFETY VIOLATION")
    
    # Patch any potential outreach functions
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: None)
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create test record
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.website = EvidencedValue(
        value="https://example.com",
        source="Discovery",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    save_intelligence_record(record)
    
    # Enrichment should not send any outreach
    result = enrich_decision_maker_intelligence(record)
    
    # Verify no outreach attempts
    assert len(outreach_attempts) == 0, "SAFETY VIOLATION: Outreach was attempted"
    
    # Result should still be valid
    assert result is not None
    assert result.record_id == record.record_id


def test_unknown_remains_unknown():
    """Verify UNKNOWN fields remain UNKNOWN - no inference or guessing."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    
    # Create record with minimal data
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    
    # Decision maker fields should be UNKNOWN by default
    assert record.decision_maker_name.state == SignalState.UNKNOWN
    assert record.decision_maker_title.state == SignalState.UNKNOWN
    assert record.owner_name.state == SignalState.UNKNOWN
    assert record.president_name.state == SignalState.UNKNOWN
    assert record.ceo_name.state == SignalState.UNKNOWN
    assert record.founder_name.state == SignalState.UNKNOWN
    assert record.contracts_manager.state == SignalState.UNKNOWN
    assert record.compliance_manager.state == SignalState.UNKNOWN
    assert record.quality_manager.state == SignalState.UNKNOWN
    assert record.operations_manager.state == SignalState.UNKNOWN
    assert record.leadership_count.state == SignalState.UNKNOWN
    assert record.organization_type.state == SignalState.UNKNOWN
    
    # Values should be None or empty
    assert record.decision_maker_name.value is None
    assert record.decision_maker_title.value is None


def test_decision_maker_record_serialization():
    """Test that decision maker fields serialize correctly."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.decision_maker_name = EvidencedValue(
        value="John Smith",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    record.decision_maker_title = EvidencedValue(
        value="President",
        source="Website",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    
    # Serialize
    data = record.to_dict()
    
    # Check decision maker fields are in serialized data
    assert "decision_maker_name" in data
    assert data["decision_maker_name"]["value"] == "John Smith"
    assert data["decision_maker_name"]["state"] == "KNOWN"
    
    assert "decision_maker_title" in data
    assert data["decision_maker_title"]["value"] == "President"
    
    # Deserialize
    restored = CustomerIntelligenceRecord.from_dict(data)
    
    assert restored.decision_maker_name.value == "John Smith"
    assert restored.decision_maker_name.state == SignalState.KNOWN
    assert restored.decision_maker_title.value == "President"

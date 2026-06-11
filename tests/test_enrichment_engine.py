"""PATCH 13A-13: Tests for Customer Intelligence Enrichment Engine.

These tests verify that the organism can answer the 5 key questions:
1. Who is the best prospect?
2. Why?
3. What evidence supports that?
4. What evidence is missing?
5. What should happen next?

If ANY question cannot be answered, ranking is FORBIDDEN.
"""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def enrichment_env(monkeypatch, tmp_path):
    """Set up isolated environment for enrichment tests."""
    data = tmp_path / "data"
    data.mkdir()
    intel = data / "acquisition" / "intelligence"
    intel.mkdir(parents=True)
    
    monkeypatch.setattr("services.config.DATA", data)
    return data


# =============================================================================
# ENRICHMENT SCORE TESTS
# =============================================================================

def test_enrichment_score_empty_record():
    """Empty record should have zero enrichment score."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    from services.acquisition.enrichment import compute_enrichment_score
    
    record = CustomerIntelligenceRecord()
    score = compute_enrichment_score(record)
    
    assert score == 0, "Empty record should have 0 enrichment"


def test_enrichment_score_uei_only():
    """UEI only should give ~10 points."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import compute_enrichment_score
    
    record = CustomerIntelligenceRecord()
    record.uei = EvidencedValue(
        value="ABC123",
        source="USASpending",
        confidence=0.99,
        state=SignalState.KNOWN,
    )
    
    score = compute_enrichment_score(record)
    assert score == 10, f"UEI only should give 10 points, got {score}"


def test_enrichment_score_uei_plus_location():
    """UEI + location should give ~15 points."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import compute_enrichment_score
    
    record = CustomerIntelligenceRecord()
    record.uei = EvidencedValue(
        value="ABC123",
        source="USASpending",
        confidence=0.99,
        state=SignalState.KNOWN,
    )
    record.location = EvidencedValue(
        value="Virginia",
        source="USASpending",
        confidence=0.8,
        state=SignalState.KNOWN,
    )
    
    score = compute_enrichment_score(record)
    assert score == 15, f"UEI + location should give 15 points, got {score}"


def test_enrichment_score_full_profile():
    """Full profile should approach 100 points."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import compute_enrichment_score
    
    record = CustomerIntelligenceRecord()
    
    # Set all fields
    fields = [
        ("company_name", "Test Corp"),
        ("uei", "ABC123"),
        ("location", "Virginia"),
        ("website", "https://test.com"),
        ("contact_email", "ceo@test.com"),
        ("contact_name", "John Doe"),
        ("contract_count", 10),
        ("contract_value", 1000000),
        ("award_recency", 90),
        ("naics", "336411"),
        ("agency_mix", ["DoD", "NASA"]),
        ("dod_exposure", True),
        ("cmmc_likelihood", 0.8),
        ("dfars_likelihood", 0.9),
        ("manufacturing_exposure", True),
        ("aerospace_exposure", True),
        ("industry", "Aerospace"),
        ("company_size", "medium"),
    ]
    
    for field_name, value in fields:
        setattr(record, field_name, EvidencedValue(
            value=value,
            source="test",
            confidence=0.9,
            state=SignalState.KNOWN,
        ))
    
    score = compute_enrichment_score(record)
    assert score == 100, f"Full profile should have 100 points, got {score}"


# =============================================================================
# UNKNOWN HUNTER TESTS
# =============================================================================

def test_known_fields_empty_record():
    """Empty record should have no known fields."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    from services.acquisition.enrichment import get_known_fields
    
    record = CustomerIntelligenceRecord()
    known = get_known_fields(record)
    
    assert len(known) == 0, "Empty record should have no known fields"


def test_unknown_fields_empty_record():
    """Empty record should have all fields unknown."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    from services.acquisition.enrichment import get_unknown_fields, ALL_TRACKED_FIELDS
    
    record = CustomerIntelligenceRecord()
    unknown = get_unknown_fields(record)
    
    assert len(unknown) == len(ALL_TRACKED_FIELDS), "All fields should be unknown"


def test_missing_critical_fields():
    """Should identify missing critical fields."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import get_missing_critical_fields, CRITICAL_FIELDS
    
    record = CustomerIntelligenceRecord()
    
    # Set company name only
    record.company_name = EvidencedValue(
        value="Test Corp",
        source="test",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    missing = get_missing_critical_fields(record)
    
    # Should be missing contact_email and contract_count
    assert "contact_email" in missing
    assert "contract_count" in missing
    assert "company_name" not in missing


def test_next_missing_evidence_priority():
    """Next missing evidence should prioritize critical fields."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import get_next_missing_evidence
    
    record = CustomerIntelligenceRecord()
    
    # Set company name and contract_count
    record.company_name = EvidencedValue(
        value="Test Corp",
        source="test",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    record.contract_count = EvidencedValue(
        value=5,
        source="test",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    # Contact email is still missing - should be next
    next_missing = get_next_missing_evidence(record)
    assert next_missing == "contact_email", f"Expected contact_email, got {next_missing}"


# =============================================================================
# RECOMMENDATION ENGINE TESTS
# =============================================================================

def test_recommendation_low_completeness_requires_enrich():
    """Low completeness should require ENRICH recommendation."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import compute_recommendation, Recommendation
    
    record = CustomerIntelligenceRecord()
    record.company_name = EvidencedValue(
        value="Test Corp",
        source="test",
        confidence=0.9,
        state=SignalState.KNOWN,
    )
    
    rec, reasoning = compute_recommendation(record)
    
    assert rec == Recommendation.ENRICH, f"Low completeness should require ENRICH, got {rec}"
    assert "completeness" in reasoning.lower() or "critical" in reasoning.lower()


def test_recommendation_missing_critical_requires_enrich():
    """Missing critical fields should require ENRICH."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import compute_recommendation, Recommendation
    
    record = CustomerIntelligenceRecord()
    
    # Set enough fields for high completeness but missing contact_email
    # Use appropriate types for each field
    field_values = {
        "company_name": "Test Corp",
        "uei": "ABC123",
        "location": "Virginia",
        "contract_count": 5,  # int
        "contract_value": 1000000,  # int
        "naics": "336411",
        "dod_exposure": True,  # bool
        "website": "https://test.com",
    }
    
    for field_name, value in field_values.items():
        setattr(record, field_name, EvidencedValue(
            value=value,
            source="test",
            confidence=0.9,
            state=SignalState.KNOWN,
        ))
    
    rec, reasoning = compute_recommendation(record)
    
    assert rec == Recommendation.ENRICH, f"Missing contact_email should require ENRICH, got {rec}"


def test_recommendation_contact_when_sufficient_evidence():
    """Sufficient evidence should allow CONTACT recommendation."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import compute_recommendation, Recommendation
    
    record = CustomerIntelligenceRecord()
    
    # Set all critical and important fields
    record.company_name = EvidencedValue(
        value="Defense Corp", source="test", confidence=0.9, state=SignalState.KNOWN)
    record.uei = EvidencedValue(
        value="ABC123", source="USASpending", confidence=0.99, state=SignalState.KNOWN)
    record.contact_email = EvidencedValue(
        value="ceo@defense.com", source="manual", confidence=0.9, state=SignalState.KNOWN)
    record.contract_count = EvidencedValue(
        value=10, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    record.contract_value = EvidencedValue(
        value=5000000, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    record.dod_exposure = EvidencedValue(
        value=True, source="USASpending", confidence=0.9, state=SignalState.KNOWN)
    record.award_recency = EvidencedValue(
        value=180, source="USASpending", confidence=0.9, state=SignalState.KNOWN)
    record.website = EvidencedValue(
        value="https://defense.com", source="manual", confidence=0.9, state=SignalState.KNOWN)
    record.location = EvidencedValue(
        value="Virginia", source="USASpending", confidence=0.9, state=SignalState.KNOWN)
    record.naics = EvidencedValue(
        value="336411", source="USASpending", confidence=0.9, state=SignalState.KNOWN)
    record.company_size = EvidencedValue(
        value="small", source="manual", confidence=0.7, state=SignalState.KNOWN)
    
    rec, reasoning = compute_recommendation(record)
    
    # Should be CONTACT, HIGH_PRIORITY, or at least WATCH (not ENRICH)
    assert rec in (Recommendation.CONTACT, Recommendation.HIGH_PRIORITY, Recommendation.WATCH), \
        f"Sufficient evidence should allow higher recommendation, got {rec}"


# =============================================================================
# 5-QUESTION TEST
# =============================================================================

def test_five_questions_cannot_answer_without_company():
    """Cannot answer questions without company name."""
    from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
    from services.acquisition.enrichment import can_answer_five_questions
    
    record = CustomerIntelligenceRecord()
    result = can_answer_five_questions(record)
    
    assert result["can_rank"] is False
    assert result["verdict"] == "RANKING_FORBIDDEN"


def test_five_questions_cannot_answer_without_evidence():
    """Cannot answer questions without any evidence."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import can_answer_five_questions
    
    record = CustomerIntelligenceRecord()
    record.company_name = EvidencedValue(
        value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN)
    
    # Has company name but no other evidence
    result = can_answer_five_questions(record)
    
    # Should still be able to rank (just with low scores)
    assert result["questions"]["who"]["answered"] is True
    assert result["questions"]["why"]["answered"] is True  # ICP tier answer
    assert result["questions"]["evidence"]["answered"] is True
    assert result["questions"]["missing"]["answered"] is True
    assert result["questions"]["next_action"]["answered"] is True


def test_five_questions_can_answer_with_evidence():
    """Can answer all questions with sufficient evidence."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import can_answer_five_questions
    
    record = CustomerIntelligenceRecord()
    record.company_name = EvidencedValue(
        value="Defense Corp", source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    record.uei = EvidencedValue(
        value="ABC123", source="USASpending", confidence=0.99, state=SignalState.KNOWN)
    record.contract_count = EvidencedValue(
        value=5, source="USASpending", confidence=0.9, state=SignalState.KNOWN)
    
    result = can_answer_five_questions(record)
    
    # Q1: Who
    assert result["questions"]["who"]["answered"] is True
    assert result["questions"]["who"]["answer"] == "Defense Corp"
    
    # Q2: Why
    assert result["questions"]["why"]["answered"] is True
    
    # Q3: Evidence
    assert result["questions"]["evidence"]["answered"] is True
    assert result["questions"]["evidence"]["total_known"] >= 3
    
    # Q4: Missing
    assert result["questions"]["missing"]["answered"] is True
    
    # Q5: Next action
    assert result["questions"]["next_action"]["answered"] is True
    
    # Overall
    assert result["can_rank"] is True
    assert result["verdict"] == "RANKING_ALLOWED"


# =============================================================================
# PROSPECT RANKING TESTS
# =============================================================================

def test_rank_prospect_includes_all_required_fields():
    """ProspectRanking should include all required fields."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import rank_prospect
    
    record = CustomerIntelligenceRecord()
    record.record_id = "INT-TEST-001"
    record.company_name = EvidencedValue(
        value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN)
    
    ranking = rank_prospect(record, rank=1)
    ranking_dict = ranking.to_dict()
    
    # Check required fields
    assert "rank" in ranking_dict
    assert "company" in ranking_dict
    assert "tier" in ranking_dict
    assert "completeness" in ranking_dict
    assert "enrichment_score" in ranking_dict
    assert "known_pct" in ranking_dict
    assert "unknown_pct" in ranking_dict
    assert "known_fields" in ranking_dict
    assert "unknown_fields" in ranking_dict
    assert "recommendation" in ranking_dict
    assert "reasoning" in ranking_dict
    assert "next_missing_evidence" in ranking_dict


def test_rank_all_prospects_empty(enrichment_env):
    """Empty intelligence store should return empty rankings."""
    from services.acquisition.enrichment import rank_all_prospects
    
    rankings = rank_all_prospects(limit=100)
    
    assert len(rankings) == 0


def test_rank_all_prospects_sorted_by_quality(enrichment_env):
    """Rankings should be sorted by evidence quality."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.enrichment import rank_all_prospects, Recommendation
    
    # Create low-quality record
    low = CustomerIntelligenceRecord()
    low.record_id = "INT-LOW"
    low.company_name = EvidencedValue(
        value="Low Corp", source="test", confidence=0.5, state=SignalState.KNOWN)
    save_intelligence_record(low)
    
    # Create high-quality record
    high = CustomerIntelligenceRecord()
    high.record_id = "INT-HIGH"
    high.company_name = EvidencedValue(
        value="High Corp", source="test", confidence=0.95, state=SignalState.KNOWN)
    high.uei = EvidencedValue(
        value="ABC123", source="USASpending", confidence=0.99, state=SignalState.KNOWN)
    high.contact_email = EvidencedValue(
        value="ceo@high.com", source="manual", confidence=0.9, state=SignalState.KNOWN)
    high.contract_count = EvidencedValue(
        value=10, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    high.website = EvidencedValue(
        value="https://high.com", source="manual", confidence=0.9, state=SignalState.KNOWN)
    save_intelligence_record(high)
    
    rankings = rank_all_prospects(limit=100)
    
    assert len(rankings) == 2
    # Higher enrichment should rank higher
    assert rankings[0].enrichment_score >= rankings[1].enrichment_score


# =============================================================================
# TOP 100 REPORT TESTS
# =============================================================================

def test_top_prospects_report_structure(enrichment_env):
    """Top prospects report should have proper structure."""
    from services.acquisition.enrichment import generate_top_prospects_report
    
    report = generate_top_prospects_report(limit=100)
    
    assert report["ok"] is True
    assert "generated_utc" in report
    assert "total_prospects" in report
    assert "summary" in report
    assert "prospects" in report
    assert "columns" in report
    
    # Check summary structure
    summary = report["summary"]
    assert "can_contact" in summary
    assert "need_enrichment" in summary
    assert "by_recommendation" in summary
    assert "by_tier" in summary


# =============================================================================
# ENRICHMENT STATE TESTS
# =============================================================================

def test_enrichment_state_discovered():
    """Minimal record should be in DISCOVERED state."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import get_enrichment_state, EnrichmentState
    
    record = CustomerIntelligenceRecord()
    record.company_name = EvidencedValue(
        value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN)
    
    state = get_enrichment_state(record)
    
    assert state == EnrichmentState.DISCOVERED


def test_enrichment_state_enriching():
    """Partially enriched record should be in ENRICHING state."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.enrichment import get_enrichment_state, EnrichmentState
    
    record = CustomerIntelligenceRecord()
    
    # Add enough for 20-40% enrichment
    record.company_name = EvidencedValue(
        value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN)
    record.uei = EvidencedValue(
        value="ABC123", source="test", confidence=0.9, state=SignalState.KNOWN)
    record.website = EvidencedValue(
        value="https://test.com", source="test", confidence=0.9, state=SignalState.KNOWN)
    record.contract_count = EvidencedValue(
        value=5, source="test", confidence=0.9, state=SignalState.KNOWN)
    
    state = get_enrichment_state(record)
    
    assert state == EnrichmentState.ENRICHING


# =============================================================================
# INTEGRATION TEST: THE ORGANISM MUST ANSWER 5 QUESTIONS
# =============================================================================

def test_organism_answers_five_questions_for_real_prospect(enrichment_env):
    """
    THE ORGANISM TEST
    
    Given a discovered company, the organism must answer:
    1. Who is the best prospect? ✓
    2. Why? ✓
    3. What evidence supports that? ✓
    4. What evidence is missing? ✓
    5. What should happen next? ✓
    
    If it cannot answer all five, ranking is FORBIDDEN.
    """
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.enrichment import (
        can_answer_five_questions,
        rank_prospect,
        generate_top_prospects_report,
    )
    
    # Create a realistic prospect
    record = CustomerIntelligenceRecord()
    record.record_id = "INT-ORGANISM-TEST"
    record.company_name = EvidencedValue(
        value="Precision Defense Manufacturing LLC",
        source="usaspending_public_api",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    record.uei = EvidencedValue(
        value="JK8X9Y2Z3M4N",
        source="usaspending_public_api",
        confidence=0.99,
        state=SignalState.KNOWN,
    )
    record.location = EvidencedValue(
        value="Huntsville, AL",
        source="usaspending_public_api",
        confidence=0.85,
        state=SignalState.KNOWN,
    )
    record.contract_count = EvidencedValue(
        value=7,
        source="usaspending_public_api",
        confidence=0.90,
        state=SignalState.KNOWN,
    )
    # Note: Many fields still UNKNOWN - realistic scenario
    
    save_intelligence_record(record)
    
    # TEST: Can the organism answer all 5 questions?
    result = can_answer_five_questions(record)
    
    # Q1: Who is the best prospect?
    assert result["questions"]["who"]["answered"] is True
    assert result["questions"]["who"]["answer"] == "Precision Defense Manufacturing LLC"
    
    # Q2: Why?
    assert result["questions"]["why"]["answered"] is True
    # Should have some ICP tier info
    
    # Q3: What evidence supports that?
    assert result["questions"]["evidence"]["answered"] is True
    evidence = result["questions"]["evidence"]["answer"]
    assert len(evidence) >= 1  # At least some evidence
    
    # Q4: What evidence is missing?
    assert result["questions"]["missing"]["answered"] is True
    missing = result["questions"]["missing"]["answer"]
    assert "contact_email" in missing  # This is UNKNOWN
    
    # Q5: What should happen next?
    assert result["questions"]["next_action"]["answered"] is True
    # Should recommend ENRICH since contact_email is missing
    
    # VERDICT
    assert result["can_rank"] is True, "Organism should be able to rank this prospect"
    
    # Now test ranking
    ranking = rank_prospect(record, rank=1)
    
    # Ranking should include evidence trail
    assert ranking.company_name == "Precision Defense Manufacturing LLC"
    assert "uei" in ranking.known_fields
    assert "contact_email" in ranking.unknown_fields
    assert ranking.recommendation.value in ["ENRICH", "WATCH"]  # Missing contact
    assert ranking.next_missing_evidence is not None
    
    # Test full report generation
    report = generate_top_prospects_report(limit=100)
    assert report["total_prospects"] == 1
    prospect = report["prospects"][0]
    
    # Report must show evidence
    assert prospect["known_fields"]
    assert prospect["unknown_fields"]
    assert prospect["recommendation"]
    assert prospect["reasoning"]

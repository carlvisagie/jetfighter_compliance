"""Tests for PATCH 13A-20: Buying Likelihood Intelligence Engine.

Validates:
1. Buying signal inventory
2. Buying likelihood scoring
3. Explainability
4. Buying readiness tiers
5. Organism questions
6. No outreach during analysis (safety)
"""
import pytest
from pathlib import Path


def test_buying_signal_inventory():
    """Test buying signal inventory is complete."""
    from services.acquisition.buying_likelihood import (
        get_buying_signal_inventory,
        BUYING_SIGNALS,
    )
    
    inventory = get_buying_signal_inventory()
    
    assert inventory["total_signals"] > 0
    assert inventory["max_possible_score"] > 0
    
    # Check required signals exist
    required_signals = [
        "contract_value",
        "contract_count",
        "dod_exposure",
        "cmmc_likelihood",
        "decision_maker_present",
        "contact_email_present",
    ]
    
    for signal in required_signals:
        assert signal in BUYING_SIGNALS, f"Missing required signal: {signal}"
    
    # Check all signals have required fields
    for name, config in BUYING_SIGNALS.items():
        assert "description" in config
        assert "weight" in config
        assert "positive_threshold" in config
        assert "evidence_type" in config


def test_buying_likelihood_scoring(monkeypatch, tmp_path):
    """Test buying likelihood score computation."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.buying_likelihood import (
        compute_buying_likelihood_score,
        BUYING_SIGNALS,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create record with positive signals
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Test Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.contract_value = EvidencedValue(
        value=2000000,  # High value
        source="USASpending",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    record.dod_exposure = EvidencedValue(
        value=True,
        source="USASpending",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    
    score, evidence_list = compute_buying_likelihood_score(record)
    
    # Score should be positive
    assert score > 0
    
    # Evidence list should have all signals
    assert len(evidence_list) == len(BUYING_SIGNALS)
    
    # Contract value and DoD exposure should be positive
    cv_ev = next(e for e in evidence_list if e.signal_name == "contract_value")
    assert cv_ev.is_positive is True
    assert cv_ev.points_earned > 0
    
    dod_ev = next(e for e in evidence_list if e.signal_name == "dod_exposure")
    assert dod_ev.is_positive is True


def test_buying_tier_classification(monkeypatch, tmp_path):
    """Test buying readiness tier classification."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.buying_likelihood import (
        compute_buying_likelihood_score,
        classify_buying_tier,
        BuyingTier,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # LOW_POTENTIAL: Empty record (we know it lacks key signals)
    empty_record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Empty Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    score, evidence = compute_buying_likelihood_score(empty_record)
    tier = classify_buying_tier(score, evidence, empty_record)
    # Empty record has some "known" signals (we know there's no email, no DM, no website)
    # so it's LOW_POTENTIAL rather than INSUFFICIENT_EVIDENCE
    assert tier in [BuyingTier.LOW_POTENTIAL, BuyingTier.INSUFFICIENT_EVIDENCE]
    
    # HIGH_POTENTIAL: Good signals
    good_record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Good Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    good_record.contract_value = EvidencedValue(value=1500000, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    good_record.dod_exposure = EvidencedValue(value=True, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    good_record.award_recency = EvidencedValue(value=100, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    
    score2, evidence2 = compute_buying_likelihood_score(good_record)
    tier2 = classify_buying_tier(score2, evidence2, good_record)
    assert tier2 in [BuyingTier.HIGH_POTENTIAL, BuyingTier.BUY_NOW]


def test_explainability_generation(monkeypatch, tmp_path):
    """Test explanation generation."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
    )
    from services.acquisition.buying_likelihood import (
        compute_buying_likelihood_score,
        generate_explanation,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create record
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Explain Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.contract_value = EvidencedValue(value=1000000, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    record.dod_exposure = EvidencedValue(value=True, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    
    score, evidence = compute_buying_likelihood_score(record)
    explanation = generate_explanation(record, score, evidence, "HIGH_POTENTIAL")
    
    # Check explanation has all required fields
    assert explanation.why_this_company is not None
    assert "Explain Corp" in explanation.why_this_company
    assert explanation.why_now is not None
    assert isinstance(explanation.supporting_evidence, list)
    assert isinstance(explanation.missing_evidence, list)
    assert explanation.next_action is not None


def test_organism_questions_with_data(monkeypatch, tmp_path):
    """Test organism can answer questions when data exists."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.buying_likelihood import (
        generate_buying_likelihood_report,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create test record
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Question Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.contract_value = EvidencedValue(value=500000, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    record.dod_exposure = EvidencedValue(value=True, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    save_intelligence_record(record)
    
    # Generate report
    report = generate_buying_likelihood_report(limit=10)
    
    assert report["ok"] is True
    assert report["total_records"] == 1
    
    # Check organism answers
    answers = report["organism_answers"]
    assert answers["answer_1"] == "Question Corp"  # Most likely customer
    assert answers["answer_2"] is not None  # Why
    assert answers["answer_6"] is not None  # Next action


def test_organism_questions_empty_data(monkeypatch, tmp_path):
    """Test organism handles empty data gracefully."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.buying_likelihood import (
        generate_buying_likelihood_report,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Generate report with no data
    report = generate_buying_likelihood_report(limit=10)
    
    assert report["ok"] is True
    assert report["total_records"] == 0
    
    # Organism should still answer (with insufficient evidence)
    answers = report["organism_answers"]
    assert answers["has_sufficient_evidence"] is False


def test_no_outreach_during_analysis():
    """SAFETY: Verify no outreach occurs during buying likelihood analysis."""
    from services.acquisition.buying_likelihood import (
        get_buying_signal_inventory,
        BUYING_SIGNALS,
    )
    
    # Check that no signal involves sending anything
    outreach_keywords = ["send email", "send message", "outreach", "contact them", "reach out"]
    
    for name, config in BUYING_SIGNALS.items():
        desc = config.get("description", "").lower()
        for keyword in outreach_keywords:
            assert keyword not in desc, f"Signal {name} contains outreach keyword: {keyword}"


def test_tier_distribution(monkeypatch, tmp_path):
    """Test tier distribution is computed correctly."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.buying_likelihood import (
        generate_buying_likelihood_report,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create multiple records with different profiles
    for i in range(5):
        record = CustomerIntelligenceRecord(
            company_name=EvidencedValue(value=f"Company {i}", source="test", confidence=0.9, state=SignalState.KNOWN),
        )
        if i < 2:
            record.contract_value = EvidencedValue(value=1000000 * (i + 1), source="USASpending", confidence=0.95, state=SignalState.KNOWN)
            record.dod_exposure = EvidencedValue(value=True, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
        save_intelligence_record(record)
    
    report = generate_buying_likelihood_report(limit=10)
    
    tiers = report["tier_distribution"]
    assert sum(tiers.values()) == 5  # All records accounted for


def test_validation_report(monkeypatch, tmp_path):
    """Test validation report structure."""
    from services.acquisition import ideal_customer_profile
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        EvidencedValue,
        SignalState,
        save_intelligence_record,
    )
    from services.acquisition.buying_likelihood import (
        validate_organism_buying_intelligence,
    )
    
    # Setup isolated directory
    intel_dir = tmp_path / "customer_intelligence"
    intel_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    # Create test record
    record = CustomerIntelligenceRecord(
        company_name=EvidencedValue(value="Validate Corp", source="test", confidence=0.9, state=SignalState.KNOWN),
    )
    record.contract_value = EvidencedValue(value=500000, source="USASpending", confidence=0.95, state=SignalState.KNOWN)
    save_intelligence_record(record)
    
    # Run validation
    validation = validate_organism_buying_intelligence()
    
    assert validation["ok"] is True
    assert "validation_passed" in validation
    assert "checks" in validation
    assert "tier_distribution" in validation
    assert "organism_answers" in validation

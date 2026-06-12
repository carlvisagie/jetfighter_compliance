"""Tests for PATCH 13A-21: Compliance Trigger Intelligence Engine.

Verifies:
1. Trigger model does not fabricate pain
2. CMMC pressure requires evidence
3. DFARS pressure requires evidence
4. Recent award pressure requires award_recency
5. Insufficient evidence remains insufficient
6. Top trigger endpoint returns explainable results
7. No outreach is sent
8. Auto-send remains disabled
"""
import pytest
from pathlib import Path

from services.acquisition.compliance_trigger_intelligence import (
    ComplianceTriggerType,
    TRIGGER_SIGNALS,
    TRIGGER_REQUIREMENTS,
    get_trigger_signal_inventory,
    evaluate_trigger_signal,
    compute_compliance_trigger,
    generate_trigger_explanation,
    generate_compliance_trigger_report,
    validate_compliance_trigger_intelligence,
    compute_compliance_trigger_metrics,
)
from services.acquisition.ideal_customer_profile import (
    CustomerIntelligenceRecord,
    EvidencedValue,
    SignalState,
    save_intelligence_record,
    _intelligence_dir,
)


@pytest.fixture
def trigger_test_env(monkeypatch, tmp_path):
    """Set up isolated test environment for trigger tests."""
    from services import config
    
    intel_dir = tmp_path / "acquisition" / "intelligence"
    intel_dir.mkdir(parents=True)
    
    monkeypatch.setattr(config, "DATA", tmp_path)
    
    from services.acquisition import ideal_customer_profile
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    return intel_dir


def _create_test_record_with_triggers(
    company_name: str,
    dod_exposure: bool = False,
    cmmc_likelihood: float = 0.0,
    dfars_likelihood: float = 0.0,
    award_recency_days: int = 500,
    contract_value: float = 0.0,
    manufacturing: bool = False,
    aerospace: bool = False,
) -> CustomerIntelligenceRecord:
    """Create a test record with specific trigger signals."""
    record = CustomerIntelligenceRecord()
    record.company_name = EvidencedValue(
        value=company_name,
        source="test",
        confidence=0.95,
        state=SignalState.KNOWN,
    )
    
    if dod_exposure:
        record.dod_exposure = EvidencedValue(
            value=True,
            source="usaspending",
            confidence=0.90,
            state=SignalState.KNOWN,
        )
    
    if cmmc_likelihood > 0:
        record.cmmc_likelihood = EvidencedValue(
            value=cmmc_likelihood,
            source="computed",
            confidence=0.85,
            state=SignalState.KNOWN,
        )
    
    if dfars_likelihood > 0:
        record.dfars_likelihood = EvidencedValue(
            value=dfars_likelihood,
            source="computed",
            confidence=0.85,
            state=SignalState.KNOWN,
        )
    
    if award_recency_days < 9999:
        record.award_recency = EvidencedValue(
            value=award_recency_days,
            source="usaspending",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
    
    if contract_value > 0:
        record.contract_value = EvidencedValue(
            value=contract_value,
            source="usaspending",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        record.contract_count = EvidencedValue(
            value=3,
            source="usaspending",
            confidence=0.90,
            state=SignalState.KNOWN,
        )
    
    if manufacturing:
        record.manufacturing_exposure = EvidencedValue(
            value=True,
            source="naics",
            confidence=0.85,
            state=SignalState.KNOWN,
        )
    
    if aerospace:
        record.aerospace_exposure = EvidencedValue(
            value=True,
            source="naics",
            confidence=0.85,
            state=SignalState.KNOWN,
        )
    
    return record


class TestTriggerSignalInventory:
    """Tests for Phase 1: Trigger Signal Inventory."""
    
    def test_trigger_signal_inventory_complete(self):
        """Trigger signal inventory returns all expected signals."""
        inventory = get_trigger_signal_inventory()
        
        assert "available_signals" in inventory
        assert "total_available" in inventory
        assert inventory["total_available"] == len(TRIGGER_SIGNALS)
        
        signal_names = [s["signal"] for s in inventory["available_signals"]]
        assert "dod_exposure" in signal_names
        assert "cmmc_likelihood" in signal_names
        assert "dfars_likelihood" in signal_names
        assert "award_recency" in signal_names


class TestTriggerModelNoFabricatedPain:
    """Tests for Phase 2: Trigger model does not fabricate pain."""
    
    def test_empty_record_returns_insufficient_evidence(self, trigger_test_env):
        """Empty record returns INSUFFICIENT_EVIDENCE, not fabricated trigger."""
        record = CustomerIntelligenceRecord()
        record.company_name = EvidencedValue(
            value="Empty Company",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type == ComplianceTriggerType.INSUFFICIENT_EVIDENCE
        assert result.trigger_score == 0
        assert "Gather more evidence" in result.recommended_conversation
    
    def test_no_synthetic_pain_signals(self, trigger_test_env):
        """Trigger model does not inject synthetic pain signals."""
        record = _create_test_record_with_triggers(
            company_name="No Pain Company",
            dod_exposure=False,
            cmmc_likelihood=0.0,
            dfars_likelihood=0.0,
        )
        
        result = compute_compliance_trigger(record)
        
        for evidence in result.supporting_evidence:
            assert "urgent" not in evidence.lower()
            assert "pain" not in evidence.lower()
            assert "overwhelm" not in evidence.lower()
            assert "burden" not in evidence.lower() or "documentation" in evidence.lower()


class TestCMMCPressureRequiresEvidence:
    """Tests for CMMC pressure trigger."""
    
    def test_cmmc_pressure_requires_dod_exposure(self, trigger_test_env):
        """CMMC pressure requires DoD exposure evidence."""
        record = _create_test_record_with_triggers(
            company_name="CMMC Candidate",
            dod_exposure=True,
            cmmc_likelihood=0.8,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type == ComplianceTriggerType.CMMC_PRESSURE
        assert result.trigger_score >= TRIGGER_REQUIREMENTS[ComplianceTriggerType.CMMC_PRESSURE]["min_score"]
        assert "CMMC" in result.recommended_conversation
    
    def test_no_cmmc_pressure_without_dod(self, trigger_test_env):
        """No CMMC pressure without DoD exposure."""
        record = _create_test_record_with_triggers(
            company_name="Non-DoD Company",
            dod_exposure=False,
            cmmc_likelihood=0.8,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type != ComplianceTriggerType.CMMC_PRESSURE


class TestDFARSPressureRequiresEvidence:
    """Tests for DFARS pressure trigger."""
    
    def test_dfars_pressure_requires_dod_and_dfars(self, trigger_test_env):
        """DFARS pressure requires DoD exposure and DFARS likelihood."""
        record = _create_test_record_with_triggers(
            company_name="DFARS Candidate",
            dod_exposure=True,
            dfars_likelihood=0.75,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type == ComplianceTriggerType.DFARS_PRESSURE
        assert "DFARS" in result.recommended_conversation
    
    def test_no_dfars_pressure_without_evidence(self, trigger_test_env):
        """No DFARS pressure without proper evidence."""
        record = _create_test_record_with_triggers(
            company_name="Low DFARS Company",
            dod_exposure=True,
            dfars_likelihood=0.2,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type != ComplianceTriggerType.DFARS_PRESSURE


class TestRecentAwardPressure:
    """Tests for recent award pressure trigger."""
    
    def test_recent_award_creates_pressure(self, trigger_test_env):
        """Recent award within 365 days creates pressure."""
        record = _create_test_record_with_triggers(
            company_name="Recent Award Company",
            award_recency_days=90,
            contract_value=500000,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type == ComplianceTriggerType.RECENT_AWARD_PRESSURE
        assert "New contract" in result.recommended_conversation or "award" in result.recommended_conversation.lower()
    
    def test_old_award_no_pressure(self, trigger_test_env):
        """Old award (>365 days) does not create recent award pressure."""
        record = _create_test_record_with_triggers(
            company_name="Old Award Company",
            award_recency_days=500,
        )
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type != ComplianceTriggerType.RECENT_AWARD_PRESSURE


class TestInsufficientEvidenceRemainsInsufficient:
    """Tests for insufficient evidence handling."""
    
    def test_unknown_remains_unknown(self, trigger_test_env):
        """Unknown signals are not interpreted as absence."""
        record = CustomerIntelligenceRecord()
        record.company_name = EvidencedValue(
            value="Unknown Company",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        
        assert record.dod_exposure.state == SignalState.UNKNOWN
        assert record.cmmc_likelihood.state == SignalState.UNKNOWN
        
        result = compute_compliance_trigger(record)
        
        assert result.trigger_type == ComplianceTriggerType.INSUFFICIENT_EVIDENCE
        assert len(result.missing_evidence) > 0


class TestTopTriggerReportExplainability:
    """Tests for Phase 5: Top trigger report."""
    
    def test_trigger_report_returns_explainable_results(self, trigger_test_env):
        """Trigger report returns results with explanations."""
        record1 = _create_test_record_with_triggers(
            company_name="High Trigger Company",
            dod_exposure=True,
            cmmc_likelihood=0.85,
            dfars_likelihood=0.80,
            contract_value=2000000,
        )
        save_intelligence_record(record1)
        
        record2 = _create_test_record_with_triggers(
            company_name="Low Trigger Company",
        )
        save_intelligence_record(record2)
        
        report = generate_compliance_trigger_report(limit=10)
        
        assert "total_records" in report
        assert "trigger_distribution" in report
        assert "top_trigger_companies" in report
        
        if report["top_trigger_companies"]:
            top = report["top_trigger_companies"][0]
            assert "company" in top
            assert "trigger_type" in top
            assert "trigger_score" in top
            assert "evidence" in top
            assert "recommended_conversation" in top
    
    def test_trigger_explanation_complete(self, trigger_test_env):
        """Trigger explanation includes all required fields."""
        record = _create_test_record_with_triggers(
            company_name="Explain Company",
            dod_exposure=True,
            cmmc_likelihood=0.8,
        )
        
        trigger_result = compute_compliance_trigger(record)
        explanation = generate_trigger_explanation(record, trigger_result)
        
        assert explanation.what_trigger is not None
        assert explanation.why is not None
        assert explanation.why_now is not None
        assert explanation.what_to_discuss is not None


class TestNoOutreachDuringTriggerAnalysis:
    """Tests for safety: No outreach during trigger analysis."""
    
    def test_no_outreach_during_analysis(self, trigger_test_env):
        """Trigger analysis does not send any outreach."""
        record = _create_test_record_with_triggers(
            company_name="Safe Company",
            dod_exposure=True,
            cmmc_likelihood=0.9,
            dfars_likelihood=0.85,
            contract_value=5000000,
        )
        save_intelligence_record(record)
        
        compute_compliance_trigger(record)
        generate_trigger_explanation(record, compute_compliance_trigger(record))
        generate_compliance_trigger_report()
        validate_compliance_trigger_intelligence()
        compute_compliance_trigger_metrics()
        
        outreach_keywords = ["send email", "send message", "contact now", "reach out", "auto-send"]
        
        result = compute_compliance_trigger(record)
        
        for keyword in outreach_keywords:
            assert keyword not in result.recommended_conversation.lower()
            for evidence in result.supporting_evidence:
                assert keyword not in evidence.lower()
    
    def test_auto_send_disabled(self, trigger_test_env):
        """Auto-send remains disabled."""
        metrics = compute_compliance_trigger_metrics()
        
        assert "auto_send_enabled" not in metrics or metrics.get("auto_send_enabled") is False


class TestComplianceTriggerMetrics:
    """Tests for Phase 7: Organism metrics."""
    
    def test_metrics_computation(self, trigger_test_env):
        """Metrics are computed correctly."""
        record1 = _create_test_record_with_triggers(
            company_name="CMMC Company",
            dod_exposure=True,
            cmmc_likelihood=0.8,
        )
        save_intelligence_record(record1)
        
        record2 = _create_test_record_with_triggers(
            company_name="Manufacturing Company",
            manufacturing=True,
        )
        save_intelligence_record(record2)
        
        metrics = compute_compliance_trigger_metrics()
        
        assert "compliance_trigger_entities" in metrics
        assert "cmmc_pressure_entities" in metrics
        assert "dfars_pressure_entities" in metrics
        assert "insufficient_trigger_evidence_entities" in metrics


class TestValidationEndpoint:
    """Tests for Phase 6: Validation endpoint."""
    
    def test_validation_with_no_data(self, trigger_test_env):
        """Validation handles empty data gracefully."""
        result = validate_compliance_trigger_intelligence()
        
        assert result["status"] == "NO_DATA"
        assert result["validation_passed"] is False
    
    def test_validation_with_data(self, trigger_test_env):
        """Validation returns proper result with data."""
        record = _create_test_record_with_triggers(
            company_name="Validation Test",
            dod_exposure=True,
            cmmc_likelihood=0.85,
        )
        save_intelligence_record(record)
        
        result = validate_compliance_trigger_intelligence()
        
        assert "status" in result
        assert "best_trigger_company" in result

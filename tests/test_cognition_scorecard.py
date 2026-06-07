import pytest
from services.cognition.schemas import (
    AwarenessState,
    CognitionMetrics,
    ValidationReport,
    ValidationFact,
    ValidationInference,
    ValidationGeneration,
    ValidationAssumption,
    ValidationRequest,
    ValidationHumanReview,
    OrganismScorecard,
    LaunchGate
)
from services.cognition.scorecard import calculate_scorecard, evaluate_launch_gate

def test_calculate_scorecard():
    state = AwarenessState(
        knows=["foo"],
        confidence_level=0.9,
        contradictions=[],
        stale_info=[]
    )
    
    metrics = CognitionMetrics(
        workload_elimination_percentage=80.0,
        generation_count=4,
        request_count=1
    )
    
    validation = ValidationReport(
        project_id="test",
        timestamp_utc="now",
        documents_generated=[
            ValidationGeneration(
                document_type="ssp",
                source_evidence=[],
                inferred_facts=[],
                unresolved_fields=[],
                confidence_score=0.9
            )
        ],
        requests=[
            ValidationRequest(
                gap_id="mfa",
                reason_not_inferred="no",
                reason_not_generated="no",
                exact_evidence_required="screenshot"
            )
        ],
        inferences_made=[],
        assumptions=[],
        human_review_items=[],
        confidence_summary=0.9,
        safety_warnings=[]
    )
    
    scorecard = calculate_scorecard(state, metrics, validation)
    
    assert scorecard.awareness_score == 100.0
    assert scorecard.reasoning_score == 90.0
    assert scorecard.generation_score == 80.0
    assert scorecard.validation_score == 100.0
    assert scorecard.reliability_score == 100.0
    assert scorecard.workload_elimination_score == 80.0
    assert scorecard.explainability_score == 100.0
    assert scorecard.overall_maturity_score > 90.0

def test_launch_gate_passes():
    scorecard = OrganismScorecard(
        reliability_score=100.0
    )
    metrics = CognitionMetrics(
        workload_elimination_percentage=80.0
    )
    validation = ValidationReport(
        project_id="test",
        timestamp_utc="now",
        confidence_summary=0.9,
        safety_warnings=[],
        documents_generated=[],
        inferences_made=[],
        requests=[
            ValidationRequest(
                gap_id="foo",
                reason_not_inferred="r",
                reason_not_generated="r",
                exact_evidence_required="e"
            )
        ],
        human_review_items=[]
    )
    
    gate = evaluate_launch_gate(scorecard, metrics, validation)
    
    assert gate.ready_for_pilot is True
    assert len(gate.blocking_items) == 0

def test_launch_gate_fails():
    scorecard = OrganismScorecard(
        reliability_score=95.0  # Fails < 99.0
    )
    metrics = CognitionMetrics(
        workload_elimination_percentage=60.0 # Fails < 75.0
    )
    validation = ValidationReport(
        project_id="test",
        timestamp_utc="now",
        confidence_summary=0.9,
        safety_warnings=["Contradiction"], # decision accuracy penalty
        documents_generated=[
            ValidationGeneration(
                document_type="ssp",
                source_evidence=[],
                inferred_facts=[],
                unresolved_fields=[],
                confidence_score=0.5 # false confidence if not flagged
            )
        ],
        inferences_made=[],
        requests=[
            ValidationRequest(
                gap_id="foo",
                reason_not_inferred="r",
                reason_not_generated="r",
                exact_evidence_required="" # false request
            )
        ],
        human_review_items=[] # Not flagging the low conf generation
    )
    
    gate = evaluate_launch_gate(scorecard, metrics, validation)
    
    assert gate.ready_for_pilot is False
    assert len(gate.blocking_items) > 0
    
    results = gate.gate_results
    assert results["workload_elimination"] == 60.0
    assert results["decision_accuracy"] < 100.0
    assert results["false_confidence"] > 0.0
    assert results["false_request"] > 0.0
    assert results["reliability"] == 95.0

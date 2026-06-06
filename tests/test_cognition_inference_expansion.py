import json
from pathlib import Path
from unittest.mock import patch
import pytest

from services.cognition.schemas import AwarenessState, ResolutionStrategy
from services.cognition.reasoning import evaluate_gap_resolution

def test_ssp_poam_evaluates_to_partial():
    state = AwarenessState(knows=["cloud_provider:AWS", "technology:react"], confidence_level=0.9)
    gap = {"gap_id": "ssp_poam", "label": "SSP"}
    
    res = evaluate_gap_resolution(gap, state)
    
    assert res.strategy == ResolutionStrategy.PARTIAL
    assert res.target_document_type == "ssp"
    assert "network_architecture" in res.missing_fields
    assert len(res.evidence_used) == 2
    assert "cloud_provider:AWS" in res.evidence_used
    assert "Diagrams" in res.reason_unresolved

def test_incident_response_evaluates_to_generate_with_crowdstrike():
    state = AwarenessState(knows=["technology:CrowdStrike", "email:admin@test.com"], confidence_level=0.9)
    gap = {"gap_id": "incident_response", "label": "IR Plan"}
    
    res = evaluate_gap_resolution(gap, state)
    
    assert res.strategy == ResolutionStrategy.GENERATE
    assert res.target_document_type == "incident_response_plan"
    assert "technology:CrowdStrike" in res.evidence_used
    assert "incident_response_coordinator_name" in res.missing_fields
    assert "No person entity found" in res.reason_unresolved

def test_access_control_evaluates_to_generate_if_entra_id_present_else_partial():
    # Entra ID present
    state = AwarenessState(knows=["technology:Microsoft Entra ID"], confidence_level=0.9)
    gap = {"gap_id": "access_control", "label": "Access Control"}
    
    res = evaluate_gap_resolution(gap, state)
    assert res.strategy == ResolutionStrategy.GENERATE
    assert "technology:Microsoft Entra ID" in res.evidence_used
    assert len(res.missing_fields) == 0

    # No IAM tools detected
    state_no_iam = AwarenessState(knows=["technology:Not IAM"], confidence_level=0.9)
    res_partial = evaluate_gap_resolution(gap, state_no_iam)
    assert res_partial.strategy == ResolutionStrategy.PARTIAL
    assert "iam_platform" in res_partial.missing_fields
    assert "No centralized IAM detected" in res_partial.reasoning
    assert "IAM platform details not found" in res_partial.reason_unresolved

def test_training_record_generates_partial_policy():
    state = AwarenessState(knows=["technology:KnowBe4"], confidence_level=0.9)
    gap = {"gap_id": "training_record", "label": "Training"}
    
    res = evaluate_gap_resolution(gap, state)
    assert res.strategy == ResolutionStrategy.PARTIAL
    assert res.target_document_type == "training_policy"
    assert "training_completion_logs" in res.missing_fields
    assert "technology:KnowBe4" in res.evidence_used
    assert "Physical training records cannot be inferred" in res.reason_unresolved

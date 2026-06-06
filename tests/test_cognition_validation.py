import pytest
import json
from pathlib import Path
from unittest.mock import patch
from services.cognition.schemas import (
    AwarenessState,
    GapResolution,
    ResolutionStrategy
)
from services.cognition.document_generation.schemas import GeneratedDocument, ProvenanceTrace
from services.cognition.validation import build_validation_report

def test_validation_report_separates_facts_and_inferences():
    state = AwarenessState(knows=["technology: AWS", "email: admin@test.com"], confidence_level=0.9)
    resolutions = [
        GapResolution(
            gap_id="ssp_gap",
            strategy=ResolutionStrategy.GENERATE,
            confidence=0.8,
            target_document_type="ssp",
            reasoning="Sufficient evidence to generate SSP",
            evidence_used=["technology: AWS"]
        )
    ]
    
    report = build_validation_report("proj_1", state, resolutions, [])
    
    assert len(report.facts_used) == 2
    assert report.facts_used[0].fact == "technology: AWS"
    
    assert len(report.inferences_made) == 1
    assert report.inferences_made[0].inference == "Sufficient evidence to generate SSP"
    assert report.inferences_made[0].basis == ["technology: AWS"]

def test_validation_report_requests_explain_why():
    state = AwarenessState(knows=[], confidence_level=0.9)
    resolutions = [
        GapResolution(
            gap_id="mfa_gap",
            strategy=ResolutionStrategy.REQUEST,
            confidence=0.9,
            target_document_type="mfa_screenshot",
            reasoning="Physical evidence required",
            reason_unresolved="Screenshot of MFA configuration needed"
        )
    ]
    
    report = build_validation_report("proj_1", state, resolutions, [])
    
    assert len(report.requests) == 1
    assert report.requests[0].gap_id == "mfa_gap"
    assert report.requests[0].reason_not_inferred == "Physical evidence required"
    assert report.requests[0].exact_evidence_required == "Screenshot of MFA configuration needed"

def test_validation_report_low_confidence_requires_review():
    state = AwarenessState(knows=[], confidence_level=0.9)
    resolutions = [
        GapResolution(
            gap_id="policy_gap",
            strategy=ResolutionStrategy.GENERATE,
            confidence=0.5, # low confidence
            target_document_type="policy",
            reasoning="Guessing based on weak signals"
        )
    ]
    
    doc = GeneratedDocument(
        doc_id="gen_1",
        doc_type="policy",
        title="Policy",
        content_markdown="Test",
        is_partial=False,
        provenance=[
            ProvenanceTrace(source_file="profile.json", source_type="inferred_fact", confidence=0.5)
        ]
    )
    
    report = build_validation_report("proj_1", state, resolutions, [doc])
    
    assert len(report.human_review_items) == 2
    # One for inference, one for generation
    item_types = [item.item_type for item in report.human_review_items]
    assert "inference" in item_types
    assert "generation" in item_types
    
    for item in report.human_review_items:
        assert item.confidence == 0.5

def test_validation_report_generation_includes_provenance():
    state = AwarenessState(knows=[], confidence_level=0.9)
    doc = GeneratedDocument(
        doc_id="gen_1",
        doc_type="policy",
        title="Policy",
        content_markdown="Test",
        is_partial=False,
        provenance=[
            ProvenanceTrace(source_file="profile.json", source_type="inferred_fact", confidence=0.9)
        ]
    )
    
    report = build_validation_report("proj_1", state, [], [doc])
    
    assert len(report.documents_generated) == 1
    gen = report.documents_generated[0]
    assert gen.document_type == "policy"
    assert "profile.json" in gen.source_evidence
    assert "inferred_fact" in gen.inferred_facts


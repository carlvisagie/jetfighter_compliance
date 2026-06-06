import pytest
from unittest.mock import patch

from services.cognition.schemas import GapResolution, ResolutionStrategy, AwarenessState
from services.cognition.document_generation.schemas import GeneratedDocument, ProvenanceTrace
from services.cognition.document_generation.engine import generate_inferred_document, generate_documents_for_resolutions
from services.cognition.document_generation.provenance import verify_inference_provenance
from services.cognition.document_generation.registry import build_generated_document_path, generated_document_to_markdown, build_document_registry_event

def test_generate_inferred_document_full():
    state = AwarenessState(knows=["technology: firewall"], confidence_level=0.9)
    res = GapResolution(
        gap_id="ssp", 
        strategy=ResolutionStrategy.GENERATE, 
        confidence=0.9, 
        target_document_type="ssp", 
        reasoning="Can draft"
    )
    
    doc = generate_inferred_document(res, state)
    assert not doc.is_partial
    assert not doc.unresolved_fields
    assert "DRAFT / REVIEW REQUIRED" in doc.content_markdown
    assert "technology: firewall" in doc.content_markdown
    assert len(doc.provenance) > 0

def test_generate_inferred_document_partial():
    state = AwarenessState(knows=["domain: cmmc"], confidence_level=0.8)
    res = GapResolution(
        gap_id="policy", 
        strategy=ResolutionStrategy.PARTIAL, 
        confidence=0.7, 
        target_document_type="policy", 
        missing_fields=["company_officer"],
        reasoning="Partial"
    )
    
    doc = generate_inferred_document(res, state)
    assert doc.is_partial
    assert "company_officer" in doc.unresolved_fields
    assert "[ ] company_officer" in doc.content_markdown
    assert "DRAFT / REVIEW REQUIRED" in doc.content_markdown

def test_request_resolution_fails():
    state = AwarenessState(knows=[], confidence_level=0.5)
    res = GapResolution(
        gap_id="mfa", 
        strategy=ResolutionStrategy.REQUEST, 
        confidence=0.9, 
        target_document_type="mfa", 
        reasoning="Requires photo"
    )
    
    with pytest.raises(ValueError):
        generate_inferred_document(res, state)

def test_verify_inference_provenance_success():
    state = AwarenessState(knows=["fact A"], confidence_level=0.9)
    res = GapResolution(
        gap_id="ssp", 
        strategy=ResolutionStrategy.GENERATE, 
        confidence=0.9, 
        target_document_type="ssp", 
        reasoning="Can draft"
    )
    doc = generate_inferred_document(res, state)
    assert verify_inference_provenance(doc, state) is True

def test_verify_inference_provenance_fails_no_provenance():
    state = AwarenessState(knows=["fact A"], confidence_level=0.9)
    # create doc directly to bypass schema checks temporarily
    # Schema enforces provenance natively, but we hack it for testing provenance module independently
    doc = GeneratedDocument(
        doc_id="1", doc_type="test", title="t", content_markdown="c",
        is_partial=False, unresolved_fields=[], 
        provenance=[ProvenanceTrace(source_file="a", source_type="b", confidence=0.9)]
    )
    doc.provenance = []
    with pytest.raises(ValueError, match="Empty provenance"):
        verify_inference_provenance(doc, state)

def test_verify_inference_provenance_fails_untraceable_claims():
    state = AwarenessState(knows=[], confidence_level=0.9)
    doc = GeneratedDocument(
        doc_id="1", doc_type="test", title="t", 
        content_markdown="- Based on evidence: Fake Fact",
        is_partial=False, unresolved_fields=[], 
        provenance=[ProvenanceTrace(source_file="a", source_type="b", confidence=0.9)]
    )
    with pytest.raises(ValueError, match="Generated claim not traceable"):
        verify_inference_provenance(doc, state)

def test_generate_documents_for_resolutions_multiple():
    state = AwarenessState(knows=["fact A"], confidence_level=0.9)
    res1 = GapResolution(gap_id="g1", strategy=ResolutionStrategy.GENERATE, confidence=0.9, target_document_type="d1", reasoning="1")
    res2 = GapResolution(gap_id="g2", strategy=ResolutionStrategy.PARTIAL, confidence=0.9, target_document_type="d2", missing_fields=["a"], reasoning="2")
    res3 = GapResolution(gap_id="g3", strategy=ResolutionStrategy.REQUEST, confidence=0.9, target_document_type="d3", reasoning="3")
    
    docs = generate_documents_for_resolutions([res1, res2, res3], state)
    assert len(docs) == 2
    assert docs[0].doc_type == "d1"
    assert docs[1].doc_type == "d2"
    assert docs[1].is_partial

def test_generate_documents_for_resolutions_safe_fail():
    state = AwarenessState(knows=["fact A"], confidence_level=0.9)
    res1 = GapResolution(gap_id="g1", strategy=ResolutionStrategy.GENERATE, confidence=0.9, target_document_type="d1", reasoning="1")
    res2 = GapResolution(gap_id="g2", strategy=ResolutionStrategy.GENERATE, confidence=0.9, target_document_type="d2", reasoning="2")
    
    with patch("services.cognition.document_generation.engine.generate_inferred_document") as mock_gen:
        mock_gen.side_effect = [
            GeneratedDocument(doc_id="1", doc_type="d1", title="t", content_markdown="c", is_partial=False, provenance=[ProvenanceTrace(source_file="a", source_type="b", confidence=0.9)]),
            Exception("Fail safe test")
        ]
        
        docs = generate_documents_for_resolutions([res1, res2], state)
        assert len(docs) == 1
        assert docs[0].doc_type == "d1"

def test_registry_helpers():
    doc = GeneratedDocument(
        doc_id="d123", doc_type="test", title="t", content_markdown="# Test",
        is_partial=False, provenance=[ProvenanceTrace(source_file="a", source_type="b", confidence=0.9)]
    )
    
    path = build_generated_document_path("proj_1", doc.doc_id)
    assert path == "data/projects/proj_1/generated/d123.md"
    
    md = generated_document_to_markdown(doc)
    assert md == "# Test"
    
    event = build_document_registry_event(doc, "proj_1")
    assert event["project_id"] == "proj_1"
    assert event["doc_id"] == "d123"
    assert event["doc_type"] == "test"
    assert event["provenance_count"] == 1

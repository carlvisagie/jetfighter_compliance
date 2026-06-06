import pytest
from pydantic import ValidationError

from services.cognition.schemas import (
    AwarenessState,
    CognitionSummary,
    CustomerDraft,
    GapResolution,
    MemoryReasoning,
    NextAction,
    ResolutionStrategy,
)
from services.cognition.document_generation.schemas import (
    GeneratedDocument,
    ProvenanceTrace,
)


def test_confidence_bounds():
    # ProvenanceTrace
    with pytest.raises(ValidationError):
        ProvenanceTrace(source_file="a", source_type="b", confidence=1.5)
    
    # AwarenessState
    with pytest.raises(ValidationError):
        AwarenessState(confidence_level=-0.1)

    # GapResolution
    with pytest.raises(ValidationError):
        GapResolution(
            gap_id="1",
            strategy=ResolutionStrategy.GENERATE,
            confidence=1.1,
            target_document_type="a",
            reasoning="b"
        )


def test_generated_document_provenance_enforced():
    with pytest.raises(ValidationError, match="GENERATED documents must have provenance"):
        GeneratedDocument(
            doc_id="1",
            doc_type="test",
            title="t",
            content_markdown="c",
            is_partial=False,
            unresolved_fields=[],
            provenance=[]
        )


def test_partial_document_unresolved_fields():
    with pytest.raises(ValidationError, match="PARTIAL documents must list unresolved_fields"):
        GeneratedDocument(
            doc_id="1",
            doc_type="test",
            title="t",
            content_markdown="c",
            is_partial=True,
            unresolved_fields=[], 
            provenance=[ProvenanceTrace(source_file="a", source_type="b", confidence=0.9)]
        )


def test_request_items_must_explain_reasoning():
    with pytest.raises(ValidationError, match="REQUEST items must explain why"):
        GapResolution(
            gap_id="1",
            strategy=ResolutionStrategy.REQUEST,
            confidence=0.5,
            target_document_type="a",
            reasoning="   ",
            missing_fields=["x"]
        )


def test_partial_strategy_missing_fields():
    with pytest.raises(ValidationError, match="PARTIAL strategy must list missing_fields"):
        GapResolution(
            gap_id="1",
            strategy=ResolutionStrategy.PARTIAL,
            confidence=0.5,
            target_document_type="a",
            reasoning="needs more",
            missing_fields=[]
        )


def test_valid_models():
    p = ProvenanceTrace(source_file="a", source_type="b", confidence=0.9)
    doc = GeneratedDocument(
        doc_id="1",
        doc_type="test",
        title="t",
        content_markdown="c",
        is_partial=False,
        unresolved_fields=[],
        provenance=[p]
    )
    res = GapResolution(
        gap_id="1",
        strategy=ResolutionStrategy.GENERATE,
        confidence=0.9,
        target_document_type="a",
        reasoning="have data"
    )
    assert doc.doc_id == "1"
    assert res.gap_id == "1"

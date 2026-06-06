from typing import List
from datetime import datetime, timezone
from services.cognition.schemas import (
    AwarenessState,
    GapResolution,
    ResolutionStrategy,
    ValidationReport,
    ValidationFact,
    ValidationInference,
    ValidationGeneration,
    ValidationAssumption,
    ValidationRequest,
    ValidationHumanReview
)
from services.cognition.document_generation.schemas import GeneratedDocument

def build_validation_report(
    project_id: str,
    state: AwarenessState,
    resolutions: List[GapResolution],
    docs: List[GeneratedDocument]
) -> ValidationReport:
    facts = []
    for f in state.knows:
        facts.append(ValidationFact(fact=f, source="evidence_intelligence"))

    inferences = []
    generations = []
    assumptions = []
    requests = []
    review_items = []
    warnings = []

    # Map resolutions to appropriate validation categories
    for res in resolutions:
        if res.strategy in [ResolutionStrategy.GENERATE, ResolutionStrategy.PARTIAL]:
            # It's an inference if it has evidence and generated something
            inferences.append(ValidationInference(
                inference=res.reasoning,
                confidence=res.confidence,
                basis=res.evidence_used
            ))

            if res.confidence < 0.7:
                review_items.append(ValidationHumanReview(
                    item_type="inference",
                    item_id=res.gap_id,
                    reason="Low confidence inference requires manual review.",
                    confidence=res.confidence
                ))

            if res.strategy == ResolutionStrategy.PARTIAL:
                assumptions.append(ValidationAssumption(
                    assumption=f"Assuming generic fallback for {res.target_document_type} due to missing fields.",
                    reason=res.reason_unresolved or "Missing required evidence."
                ))
                
        elif res.strategy == ResolutionStrategy.REQUEST:
            requests.append(ValidationRequest(
                gap_id=res.gap_id,
                reason_not_inferred=res.reasoning,
                reason_not_generated=res.reasoning,
                exact_evidence_required=res.reason_unresolved or "Provide required documentary or physical evidence."
            ))

    for doc in docs:
        gen = ValidationGeneration(
            document_type=doc.doc_type,
            source_evidence=[p.source_file for p in doc.provenance],
            inferred_facts=[p.source_type for p in doc.provenance if p.source_type == "inferred_fact"],
            unresolved_fields=doc.unresolved_fields,
            confidence_score=0.0
        )
        # find matching resolution for confidence
        for res in resolutions:
            if res.target_document_type == doc.doc_type:
                gen.confidence_score = res.confidence
                break
                
        generations.append(gen)
        
        if gen.confidence_score < 0.7:
            review_items.append(ValidationHumanReview(
                item_type="generation",
                item_id=doc.doc_id,
                reason="Low confidence generation.",
                confidence=gen.confidence_score
            ))

    for contradiction in state.contradictions:
        review_items.append(ValidationHumanReview(
            item_type="contradiction",
            item_id=contradiction.get("field", "unknown"),
            reason=f"Conflicting values found: {contradiction.get('values')}",
            confidence=0.0
        ))
        warnings.append(f"Contradiction detected in {contradiction.get('field')}")

    return ValidationReport(
        project_id=project_id,
        timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        facts_used=facts,
        inferences_made=inferences,
        documents_generated=generations,
        assumptions=assumptions,
        requests=requests,
        human_review_items=review_items,
        confidence_summary=state.confidence_level,
        safety_warnings=warnings
    )

import uuid
from typing import List

from services.cognition.schemas import GapResolution, ResolutionStrategy, AwarenessState
from services.cognition.document_generation.schemas import GeneratedDocument, ProvenanceTrace

def generate_inferred_document(resolution: GapResolution, state: AwarenessState) -> GeneratedDocument:
    if resolution.strategy == ResolutionStrategy.REQUEST:
        raise ValueError(f"Cannot generate document for REQUEST strategy on gap {resolution.gap_id}")

    doc_id = f"gen_{uuid.uuid4().hex[:8]}"
    title = f"{resolution.target_document_type.upper()} Draft"
    
    content_lines = [
        f"# {title}",
        "**DRAFT / REVIEW REQUIRED**\n",
        f"This document was automatically generated for gap: {resolution.gap_id}.\n",
        "## Sourced Facts"
    ]
    
    provenance = []
    
    for fact in state.knows:
        content_lines.append(f"- Based on evidence: {fact}")
        provenance.append(ProvenanceTrace(
            source_file="profile.json",
            source_type="inferred_fact",
            confidence=0.9
        ))
    
    if not provenance:
        provenance.append(ProvenanceTrace(
            source_file="domain_knowledge",
            source_type="system_rule",
            confidence=0.8
        ))
        content_lines.append("- Based on evidence: generic domain template")

    unresolved_fields = []
    is_partial = False
    
    if resolution.strategy == ResolutionStrategy.PARTIAL:
        is_partial = True
        unresolved_fields = list(resolution.missing_fields)
        content_lines.append("\n## Unresolved Fields")
        for field in unresolved_fields:
            content_lines.append(f"- [ ] {field}")
            
    content_markdown = "\n".join(content_lines)
    
    return GeneratedDocument(
        doc_id=doc_id,
        doc_type=resolution.target_document_type,
        title=title,
        content_markdown=content_markdown,
        is_partial=is_partial,
        unresolved_fields=unresolved_fields,
        provenance=provenance
    )

def generate_documents_for_resolutions(resolutions: List[GapResolution], state: AwarenessState) -> List[GeneratedDocument]:
    generated = []
    for res in resolutions:
        if res.strategy == ResolutionStrategy.REQUEST:
            continue
        try:
            doc = generate_inferred_document(res, state)
            generated.append(doc)
        except Exception:
            pass
    return generated

from services.cognition.document_generation.schemas import GeneratedDocument
from services.cognition.schemas import AwarenessState

def verify_inference_provenance(doc: GeneratedDocument, state: AwarenessState) -> bool:
    if not doc.provenance:
        raise ValueError("Empty provenance")
    
    for p in doc.provenance:
        if p.confidence < 0.0 or p.confidence > 1.0:
            raise ValueError(f"Confidence {p.confidence} outside range 0.0-1.0")
            
    # For now, simplistic check mapping "- Based on evidence: FACT" lines to known facts
    lines = doc.content_markdown.split('\n')
    for line in lines:
        if line.startswith("- Based on evidence: ") and not line.endswith("generic domain template"):
            claim = line.replace("- Based on evidence: ", "").strip()
            if claim not in state.knows:
                raise ValueError(f"Generated claim not traceable to known_facts: {claim}")
                
    return True
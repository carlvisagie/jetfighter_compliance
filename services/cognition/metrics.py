from typing import List
from services.cognition.schemas import AwarenessState, GapResolution, ResolutionStrategy, CognitionMetrics

def calculate_hours_saved(target_document_type: str) -> float:
    doc = target_document_type.lower()
    if "ssp" in doc: return 10.0
    if "incident_response" in doc: return 5.0
    if "asset_inventory" in doc or "inventory" in doc: return 4.0
    if "access_control" in doc: return 3.0
    if "backup" in doc: return 2.5
    if "training" in doc: return 1.5
    if "policy" in doc: return 3.0
    return 2.0

def compute_metrics(state: AwarenessState, resolutions: List[GapResolution]) -> CognitionMetrics:
    total_gaps = len(resolutions)
    
    documents_generated = []
    documents_requested = []
    questions_avoided = []
    questions_asked = []
    
    generation_count = 0
    request_count = 0
    estimated_hours_saved = 0.0
    
    total_confidence = 0.0
    
    for res in resolutions:
        total_confidence += res.confidence
        
        if res.strategy in [ResolutionStrategy.GENERATE, ResolutionStrategy.PARTIAL]:
            documents_generated.append(res.target_document_type)
            questions_avoided.append(res.gap_id)
            generation_count += 1
            estimated_hours_saved += calculate_hours_saved(res.target_document_type)
        else:
            documents_requested.append(res.target_document_type)
            questions_asked.append(res.gap_id)
            request_count += 1

    workload_elimination = 0.0
    if total_gaps > 0:
        workload_elimination = (generation_count / total_gaps) * 100.0
        
    avg_confidence = (total_confidence / total_gaps) if total_gaps > 0 else 0.0

    inference_count = len(state.knows)
    
    return CognitionMetrics(
        workload_elimination_percentage=round(workload_elimination, 2),
        documents_generated=documents_generated,
        documents_requested=documents_requested,
        questions_avoided=questions_avoided,
        questions_asked=questions_asked,
        estimated_hours_saved=round(estimated_hours_saved, 2),
        confidence_score=round(avg_confidence, 2),
        inference_count=inference_count,
        generation_count=generation_count,
        request_count=request_count
    )

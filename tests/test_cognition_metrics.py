from services.cognition.metrics import compute_metrics, calculate_hours_saved
from services.cognition.schemas import AwarenessState, GapResolution, ResolutionStrategy

def test_calculate_hours_saved():
    assert calculate_hours_saved("ssp") == 10.0
    assert calculate_hours_saved("ssp_poam") == 10.0
    assert calculate_hours_saved("incident_response_plan") == 5.0
    assert calculate_hours_saved("asset_inventory") == 4.0
    assert calculate_hours_saved("access_control_policy") == 3.0
    assert calculate_hours_saved("backup_policy") == 2.5
    assert calculate_hours_saved("training_policy") == 1.5
    assert calculate_hours_saved("vendor_policy") == 3.0
    assert calculate_hours_saved("unknown_document") == 2.0

def test_compute_metrics():
    state = AwarenessState(
        knows=["fact1", "fact2", "fact3"],
        confidence_level=0.9
    )
    
    resolutions = [
        GapResolution(
            gap_id="ssp_gap",
            strategy=ResolutionStrategy.GENERATE,
            confidence=0.8,
            target_document_type="ssp",
            reasoning="Sufficient data",
            missing_fields=[]
        ),
        GapResolution(
            gap_id="access_control_gap",
            strategy=ResolutionStrategy.PARTIAL,
            confidence=0.6,
            target_document_type="access_control_policy",
            reasoning="Missing IAM",
            missing_fields=["iam_platform"]
        ),
        GapResolution(
            gap_id="mfa_gap",
            strategy=ResolutionStrategy.REQUEST,
            confidence=0.9,
            target_document_type="mfa_screenshot",
            reasoning="Physical evidence required",
            missing_fields=[]
        )
    ]
    
    metrics = compute_metrics(state, resolutions)
    
    # 2 out of 3 generated/partial
    assert metrics.workload_elimination_percentage == 66.67
    assert metrics.generation_count == 2
    assert metrics.request_count == 1
    assert len(metrics.documents_generated) == 2
    assert "ssp" in metrics.documents_generated
    assert "access_control_policy" in metrics.documents_generated
    assert len(metrics.questions_avoided) == 2
    
    assert len(metrics.documents_requested) == 1
    assert "mfa_screenshot" in metrics.documents_requested
    assert len(metrics.questions_asked) == 1
    assert "mfa_gap" in metrics.questions_asked
    
    # SSP (10) + Access Control (3) = 13.0
    assert metrics.estimated_hours_saved == 13.0
    
    # Average confidence: (0.8 + 0.6 + 0.9) / 3 = 0.77
    assert metrics.confidence_score == 0.77
    
    # 3 facts known
    assert metrics.inference_count == 3

def test_compute_metrics_empty():
    state = AwarenessState(knows=[], confidence_level=0.0)
    metrics = compute_metrics(state, [])
    
    assert metrics.workload_elimination_percentage == 0.0
    assert metrics.generation_count == 0
    assert metrics.request_count == 0
    assert metrics.estimated_hours_saved == 0.0
    assert metrics.confidence_score == 0.0
    assert metrics.inference_count == 0

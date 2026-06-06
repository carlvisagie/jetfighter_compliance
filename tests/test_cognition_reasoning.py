from services.cognition.schemas import AwarenessState, ResolutionStrategy
from services.cognition.reasoning import evaluate_gap_resolution, evaluate_all_gaps

def test_evaluate_gap_resolution_prefers_generate():
    state = AwarenessState(
        knows=["technology: network_architecture", "vendor: AWS"],
        confidence_level=0.9
    )
    gap = {"gap_id": "ssp", "label": "System Security Plan"}
    
    res = evaluate_gap_resolution(gap, state)
    assert res.strategy == ResolutionStrategy.GENERATE
    assert res.target_document_type == "ssp"

def test_evaluate_gap_resolution_returns_partial():
    state = AwarenessState(
        knows=["domain: cmmc"],
        confidence_level=0.8
    )
    gap = {"gap_id": "ssp", "label": "System Security Plan"}
    
    res = evaluate_gap_resolution(gap, state)
    assert res.strategy == ResolutionStrategy.PARTIAL
    assert "network_architecture" in res.missing_fields

def test_evaluate_gap_resolution_returns_request():
    state = AwarenessState(
        knows=[],
        confidence_level=0.0
    )
    # MFA screenshot is a physical evidence gap
    gap = {"gap_id": "mfa_screenshot", "label": "MFA Screenshot"}
    
    res = evaluate_gap_resolution(gap, state)
    assert res.strategy == ResolutionStrategy.REQUEST
    assert not res.missing_fields

def test_evaluate_all_gaps():
    state = AwarenessState(
        knows=["technology: network_architecture", "vendor: Okta"],
        confidence_level=0.9
    )
    gaps = [
        {"gap_id": "ssp", "label": "System Security Plan"},
        {"gap_id": "mfa_screenshot", "label": "MFA Screenshot"},
        {"gap_id": "policy", "label": "Access Control Policy"} # returns PARTIAL without company_officer
    ]
    
    resolutions = evaluate_all_gaps(gaps, state)
    assert len(resolutions) == 3
    
    strats = [r.strategy for r in resolutions]
    assert ResolutionStrategy.GENERATE in strats
    assert ResolutionStrategy.REQUEST in strats
    assert ResolutionStrategy.PARTIAL in strats

from services.cognition.schemas import AwarenessState, ResolutionStrategy
from services.cognition.reasoning import evaluate_gap_resolution, evaluate_all_gaps

def test_evaluate_gap_resolution_prefers_generate():
    state = AwarenessState(
        knows=["company_name: Test Co"],
        confidence_level=0.9
    )
    gap = {"gap_id": "policy", "label": "Security Policy"}
    
    res = evaluate_gap_resolution(gap, state)
    assert res.strategy == ResolutionStrategy.GENERATE
    assert res.target_document_type == "policy"

def test_evaluate_gap_resolution_returns_partial():
    state = AwarenessState(
        knows=["domain: cmmc", "technology: react"],
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
        knows=["technology: AWS", "company_name: Okta", "technology: Okta"],
        confidence_level=0.9
    )
    gaps = [
        {"gap_id": "ssp", "label": "System Security Plan"}, # returns PARTIAL
        {"gap_id": "mfa_screenshot", "label": "MFA Screenshot"}, # returns REQUEST
        {"gap_id": "access_control", "label": "Access Control"} # returns GENERATE because technology: Okta
    ]
    
    resolutions = evaluate_all_gaps(gaps, state)
    assert len(resolutions) == 3
    
    strats = [r.strategy for r in resolutions]
    assert ResolutionStrategy.GENERATE in strats
    assert ResolutionStrategy.REQUEST in strats
    assert ResolutionStrategy.PARTIAL in strats

def test_missing_company_name_blocks_generation():
    state = AwarenessState(
        knows=["technology: okta"],
        does_not_know=["company_name"],
        confidence_level=0.9
    )
    gaps = [{"gap_id": "access_control", "label": "Access Control"}]
    
    resolutions = evaluate_all_gaps(gaps, state)
    
    assert len(resolutions) > 0
    assert resolutions[0].gap_id == "missing_company_name"
    assert resolutions[0].strategy == ResolutionStrategy.REQUEST
    
    res = resolutions[1]
    
    assert res.strategy == ResolutionStrategy.PARTIAL
    assert "company_identity" in res.missing_fields
    assert res.reason_unresolved == "Company identity not established."

def test_technical_entities_alone_do_not_permit_generation():
    state = AwarenessState(
        knows=["technology: AWS", "technology: Azure"],
        does_not_know=["company_name"],
        confidence_level=0.9
    )
    gaps = [{"gap_id": "backup_evidence", "label": "Backup Policy"}]
    
    resolutions = evaluate_all_gaps(gaps, state)
    
    assert len(resolutions) > 0
    assert resolutions[0].gap_id == "missing_company_name"
    assert resolutions[0].strategy == ResolutionStrategy.REQUEST
    
    res = resolutions[1]
    
    assert res.strategy == ResolutionStrategy.PARTIAL
    assert "company_identity" in res.missing_fields
    assert res.reason_unresolved == "Company identity not established."

def test_verified_company_identity_restores_generation():
    state = AwarenessState(
        knows=["technology: AWS", "technology: Azure", "company_name: Acme"],
        does_not_know=[],
        confidence_level=0.9
    )
    gaps = [{"gap_id": "backup_evidence", "label": "Backup Policy"}]
    
    resolutions = evaluate_all_gaps(gaps, state)
    res = resolutions[0]
    
    assert res.strategy == ResolutionStrategy.GENERATE
    assert "company_identity" not in res.missing_fields

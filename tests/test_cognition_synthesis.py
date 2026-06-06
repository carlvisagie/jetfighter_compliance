from services.cognition.synthesis import synthesize_awareness

def test_synthesize_awareness_detects_known_facts():
    profile = {"primary_domain": "cmmc"}
    entities = [
        {"type": "vendor", "value": "Microsoft", "confidence": 0.9},
        {"type": "technology", "value": "Azure", "confidence": 0.3} # Low confidence, should be ignored
    ]
    classifications = []
    
    state = synthesize_awareness(profile, classifications, entities, [], [], [])
    assert any("Microsoft" in k for k in state.knows)
    assert not any("Azure" in k for k in state.knows)
    assert any("domain: cmmc" in k for k in state.knows)
    assert state.confidence_level > 0.0

def test_synthesize_awareness_detects_contradictions():
    profile = {
        "company_name_candidates": [
            {"value": "Acme Corp", "status": "conflicting"},
            {"value": "Acme LLC", "status": "conflicting"}
        ]
    }
    review_queue = [
        {
            "kind": "conflicting_extraction",
            "field": "phone",
            "candidates": ["555-1234", "555-9876"]
        }
    ]
    
    state = synthesize_awareness(profile, [], [], [], review_queue, [])
    assert len(state.contradictions) == 2
    
    fields = [c["field"] for c in state.contradictions]
    assert "company_name" in fields
    assert "phone" in fields

def test_synthesize_awareness_marks_unknowns():
    profile = {
        "company_name": "Apex",
        # missing emails and phones
    }
    state = synthesize_awareness(profile, [], [], [], [], [])
    
    assert "company_name" not in state.does_not_know
    assert "emails" in state.does_not_know
    assert "phones" in state.does_not_know

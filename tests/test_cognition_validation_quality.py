import json
import pytest
from organism_core import SignalBundle
from services.organism_state.checks import CognitionValidationCheck
from services.organism_state.collectors import CognitionValidationCollector

def test_cognition_validation_no_data():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {"available": False})
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is True
    assert res.severity.name == "INFO"
    assert "No cognition validation data" in res.detail

def test_cognition_validation_no_projects():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {
        "available": True,
        "projects_checked": 0,
        "malformed_reports": 0,
        "generated_without_validation": 0
    })
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is True
    assert res.severity.name == "INFO"
    assert "No projects" in res.detail

def test_cognition_validation_healthy():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {
        "available": True,
        "projects_checked": 12,
        "avg_confidence": 0.83,
        "projects_with_human_review": 0,
        "projects_with_safety_warnings": 0,
        "malformed_reports": 0,
        "generated_without_validation": 0
    })
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is True
    assert res.severity.name == "INFO"
    assert "healthy" in res.detail
    assert "12 project(s) checked" in res.detail

def test_cognition_validation_human_review():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {
        "available": True,
        "projects_checked": 12,
        "avg_confidence": 0.83,
        "projects_with_human_review": 3,
        "projects_with_safety_warnings": 0,
        "malformed_reports": 0,
        "generated_without_validation": 0
    })
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is False
    assert res.severity.name == "AMBER"
    assert "requires review" in res.detail
    assert "3 project(s)" in res.detail

def test_cognition_validation_safety_warnings():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {
        "available": True,
        "projects_checked": 1,
        "avg_confidence": 0.83,
        "projects_with_human_review": 0,
        "projects_with_safety_warnings": 1,
        "malformed_reports": 0,
        "generated_without_validation": 0
    })
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is False
    assert res.severity.name == "RED"
    assert "safety_warnings" in res.detail

def test_cognition_validation_malformed():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {
        "available": True,
        "projects_checked": 0,
        "avg_confidence": 0.0,
        "projects_with_human_review": 0,
        "projects_with_safety_warnings": 0,
        "malformed_reports": 1,
        "generated_without_validation": 0
    })
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is False
    assert res.severity.name == "RED"
    assert "malformed" in res.detail

def test_cognition_validation_generated_without_validation():
    bundle = SignalBundle()
    bundle.add("cognition_validation", {
        "available": True,
        "projects_checked": 0,
        "avg_confidence": 0.0,
        "projects_with_human_review": 0,
        "projects_with_safety_warnings": 0,
        "malformed_reports": 0,
        "generated_without_validation": 2
    })
    check = CognitionValidationCheck()
    res = check.evaluate(bundle)
    assert res.ok is False
    assert res.severity.name == "RED"
    assert "generated documents without a validation report" in res.detail

def test_cognition_validation_collector(tmp_path, monkeypatch):
    import services.durable_storage as ds
    
    # Mock durable storage root
    monkeypatch.setattr(ds, "active_data_root", lambda: tmp_path)
    
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    
    p1 = projects_dir / "p1" / "cognition"
    p1.mkdir(parents=True)
    (p1 / "validation_report.json").write_text(json.dumps({
        "confidence_summary": 0.8,
        "human_review_items": [],
        "safety_warnings": []
    }))
    
    p2 = projects_dir / "p2" / "cognition"
    p2.mkdir(parents=True)
    (p2 / "validation_report.json").write_text(json.dumps({
        "confidence_summary": 0.9,
        "human_review_items": [{"id": 1}],
        "safety_warnings": []
    }))
    
    p3 = projects_dir / "p3" / "cognition"
    p3.mkdir(parents=True)
    (p3 / "validation_report.json").write_text("not json")
    
    p4 = projects_dir / "p4" / "cognition"
    p4.mkdir(parents=True)
    (p4 / "cognition_summary.json").write_text(json.dumps({
        "generated_documents": [{"id": 1}]
    }))
    
    col = CognitionValidationCollector()
    res = col.collect()
    
    assert res["available"] is True
    assert res["projects_checked"] == 2
    assert abs(res["avg_confidence"] - 0.85) < 0.001
    assert res["projects_with_human_review"] == 1
    assert res["projects_with_safety_warnings"] == 0
    assert res["malformed_reports"] == 1
    assert res["generated_without_validation"] == 1

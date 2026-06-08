import pytest
from organism_core import SignalBundle
from services.organism_state.checks import ComplianceIntelligenceHealthCheck, Severity

def test_compliance_intelligence_health_green():
    check = ComplianceIntelligenceHealthCheck()
    bundle = SignalBundle()
    bundle.add("compliance_intelligence_status", {
        "available": True,
        "high_severity_pending": 0,
        "medium_severity_pending": 0,
        "sources_stale": 0,
        "failed_compliance_cycle": False
    })
    result = check.evaluate(bundle)
    assert result.ok is True
    assert result.severity == Severity.INFO
    assert "GREEN" in result.detail

def test_compliance_intelligence_health_amber():
    check = ComplianceIntelligenceHealthCheck()
    bundle = SignalBundle()
    bundle.add("compliance_intelligence_status", {
        "available": True,
        "high_severity_pending": 0,
        "medium_severity_pending": 2,
        "sources_stale": 0,
        "failed_compliance_cycle": False
    })
    result = check.evaluate(bundle)
    assert result.ok is False
    assert result.severity == Severity.AMBER
    assert "AMBER" in result.detail

def test_compliance_intelligence_health_red_high_severity():
    check = ComplianceIntelligenceHealthCheck()
    bundle = SignalBundle()
    bundle.add("compliance_intelligence_status", {
        "available": True,
        "high_severity_pending": 1,
        "medium_severity_pending": 0,
        "sources_stale": 0,
        "failed_compliance_cycle": False
    })
    result = check.evaluate(bundle)
    assert result.ok is False
    assert result.severity == Severity.RED
    assert "RED" in result.detail

def test_compliance_intelligence_health_red_stale_source():
    check = ComplianceIntelligenceHealthCheck()
    bundle = SignalBundle()
    bundle.add("compliance_intelligence_status", {
        "available": True,
        "high_severity_pending": 0,
        "medium_severity_pending": 0,
        "sources_stale": 1,
        "failed_compliance_cycle": False
    })
    result = check.evaluate(bundle)
    assert result.ok is False
    assert result.severity == Severity.RED
    assert "RED" in result.detail

def test_compliance_intelligence_health_red_failed_cycle():
    check = ComplianceIntelligenceHealthCheck()
    bundle = SignalBundle()
    bundle.add("compliance_intelligence_status", {
        "available": True,
        "high_severity_pending": 0,
        "medium_severity_pending": 0,
        "sources_stale": 0,
        "failed_compliance_cycle": True
    })
    result = check.evaluate(bundle)
    assert result.ok is False
    assert result.severity == Severity.RED
    assert "RED" in result.detail

def test_compliance_intelligence_recommendation():
    from services.organism_state.recommendations import _compliance_intel_action
    
    # Failed cycle
    assert "Check compliance_intel telemetry" in _compliance_intel_action(
        ComplianceIntelligenceHealthCheck().evaluate(SignalBundle({"compliance_intelligence_status": {"available": True, "failed_compliance_cycle": True}}))
    )
    
    # Stale source
    assert "Stale sources detected" in _compliance_intel_action(
        ComplianceIntelligenceHealthCheck().evaluate(SignalBundle({"compliance_intelligence_status": {"available": True, "sources_stale": 1}}))
    )
    
    # High severity
    assert "high-severity compliance intelligence items" in _compliance_intel_action(
        ComplianceIntelligenceHealthCheck().evaluate(SignalBundle({"compliance_intelligence_status": {"available": True, "high_severity_pending": 1}}))
    )
    
    # Medium severity
    assert "pending compliance intelligence items" in _compliance_intel_action(
        ComplianceIntelligenceHealthCheck().evaluate(SignalBundle({"compliance_intelligence_status": {"available": True, "medium_severity_pending": 1}}))
    )
    
    # Green
    assert "Compliance intelligence healthy." in _compliance_intel_action(
        ComplianceIntelligenceHealthCheck().evaluate(SignalBundle({"compliance_intelligence_status": {"available": True}}))
    )

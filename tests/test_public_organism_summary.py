"""Test public organism summary endpoint."""
import pytest


def test_public_organism_summary_no_auth_required(anon_client):
    """Public organism summary must be accessible without authentication."""
    r = anon_client.get("/api/public/organism/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "health_state" in body
    assert body["health_state"] in ("GREEN", "AMBER", "RED", "UNKNOWN")


def test_public_organism_summary_sanitizes_data(anon_client):
    """Public organism summary must not expose customer IDs or internal paths."""
    r = anon_client.get("/api/public/organism/summary")
    assert r.status_code == 200
    body = r.json()
    
    # Convert response to string for inspection
    response_str = str(body)
    
    # Must NOT contain internal paths
    assert "/var/data" not in response_str or "[DATA_ROOT]" in response_str
    
    # Must NOT contain customer IDs (unless redacted)
    if "FB-" in response_str:
        assert "[REDACTED]" in response_str
    
    # Must NOT contain full git commit (only short SHA)
    git_commit = body.get("git_commit", "")
    assert len(git_commit) <= 7


def test_public_organism_summary_returns_required_fields(anon_client):
    """Public organism summary must include all required health fields."""
    r = anon_client.get("/api/public/organism/summary")
    assert r.status_code == 200
    body = r.json()
    
    required_fields = [
        "ok",
        "health_state",
        "current_bottleneck",
        "next_recommended_action",
        "checks",
        "metrics",
    ]
    
    for field in required_fields:
        assert field in body, f"Missing required field: {field}"
    
    # Verify metrics structure
    metrics = body["metrics"]
    assert "intake_count" in metrics
    assert "queue_depth" in metrics
    assert "project_count" in metrics
    assert "evidence_count" in metrics


def test_public_organism_summary_check_structure(anon_client):
    """Public organism summary checks must have sanitized structure."""
    r = anon_client.get("/api/public/organism/summary")
    assert r.status_code == 200
    body = r.json()
    
    checks = body.get("checks", [])
    assert isinstance(checks, list)
    
    for check in checks:
        assert "name" in check
        assert "ok" in check
        assert "severity" in check
        assert "detail" in check
        
        # Evidence must be redacted (not included in public summary)
        assert "evidence" not in check


def test_public_organism_summary_no_secrets(anon_client):
    """Public organism summary must not expose any secrets."""
    r = anon_client.get("/api/public/organism/summary")
    assert r.status_code == 200
    response_str = str(r.json())
    
    # Must NOT contain these sensitive patterns
    forbidden_patterns = [
        "password",
        "secret",
        "api_key",
        "token",
        "OPS_PASSWORD",
        "OPS_API_KEY",
        "RESEND_API_KEY",
    ]
    
    response_lower = response_str.lower()
    for pattern in forbidden_patterns:
        assert pattern.lower() not in response_lower, f"Exposed secret pattern: {pattern}"

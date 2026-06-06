import os

import pytest


def test_health_ready(anon_client):
    r = anon_client.get("/health/ready")
    assert r.status_code == 200
    j = r.json()
    assert "checks" in j
    assert j["checks"]["data_writable"] is True


def test_ops_routes_blocked_in_production(monkeypatch, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("OPS_API_KEY", raising=False)
    r = anon_client.post(
        "/events/payment/test",
        json={"order_id": "X", "email": "x@y.com", "name": "X", "skus": ["T"]},
    )
    assert r.status_code == 403


def test_ops_routes_with_key(monkeypatch, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPS_API_KEY", "test-ops-key")
    r = anon_client.post(
        "/events/payment/test",
        json={"order_id": "X2", "email": "x2@y.com", "name": "X", "skus": ["T"]},
        headers={"X-Ops-Key": "test-ops-key"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_evidence_rejects_without_token(anon_client):
    """SEC-003: unauthenticated uploads rejected with 403 before project lookup."""
    r = anon_client.post(
        "/api/evidence/register?project_id=INVALID&media_type=document&owner=test",
        files={"file": ("a.txt", b"hi", "text/plain")},
    )
    # Token check runs first (auth before project existence) → 403 not 400
    assert r.status_code == 403


def test_startup_warnings_flag_missing_email_provider(monkeypatch):
    """REGRESSION GUARD — in production, the startup self-check must
    surface a CRITICAL warning when neither SMTP nor Resend is wired.

    The 2026-06-04 revenue-pipeline audit flagged silent payment-link
    failure as the top first-customer embarrassment: link "generated"
    but never sent because no provider is configured. This guard
    pins the warning so the operator sees the gap at boot.
    """
    from services import production

    monkeypatch.setenv("ENVIRONMENT", "production")
    # Force every email config off.
    monkeypatch.setattr(production.SETTINGS, "smtp_enabled", False, raising=False)
    monkeypatch.setattr(production.SETTINGS, "smtp_host", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "smtp_user", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "smtp_pass", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "resend_api_key", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "resend_from_email", "", raising=False)

    warnings = production.startup_warnings()
    assert any("no email provider" in w.lower() for w in warnings), (
        "missing-provider warning must be surfaced; got %r" % (warnings,)
    )
    assert production.email_provider_configured() is False


def test_startup_warnings_clear_when_resend_configured(monkeypatch):
    """Resend alone is enough — no warning required."""
    from services import production

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(production.SETTINGS, "smtp_enabled", False, raising=False)
    monkeypatch.setattr(production.SETTINGS, "smtp_host", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "smtp_user", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "smtp_pass", "", raising=False)
    monkeypatch.setattr(production.SETTINGS, "resend_api_key", "re_xxx", raising=False)
    monkeypatch.setattr(
        production.SETTINGS, "resend_from_email", "ops@example.com", raising=False
    )

    assert production.email_provider_configured() is True
    warnings = production.startup_warnings()
    assert not any("no email provider" in w.lower() for w in warnings)

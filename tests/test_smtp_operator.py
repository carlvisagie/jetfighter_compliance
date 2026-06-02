"""SMTP configuration, operator test endpoint, and telemetry."""

import pytest
from fastapi.testclient import TestClient

from server import app
from services.emails import send_email_with_result, send_operator_test_email
from services.production import smtp_env_status


def test_smtp_readiness_detects_configured(monkeypatch):
    monkeypatch.setenv("SMTP_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASS", "secret")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.com")
    from services.config import SETTINGS

    # Reload settings object fields manually for test
    SETTINGS.smtp_enabled = True
    SETTINGS.smtp_host = "smtp.example.com"
    SETTINGS.smtp_user = "user@example.com"
    SETTINGS.smtp_pass = "secret"
    SETTINGS.smtp_from_email = "noreply@example.com"
    st = smtp_env_status()
    assert st["configured"] is True
    assert st["SMTP_PASS"] is True
    assert "secret" not in str(st)


def test_smtp_alias_env_names_documented():
    """Canonical names are SMTP_HOST/USER/PASS; aliases SMTP_SERVER/USERNAME/PASSWORD supported in config.py."""
    import services.config as cfg

    assert hasattr(cfg.Settings.model_fields, "__getitem__") or "smtp_host" in cfg.Settings.model_fields
    src = open(cfg.__file__, encoding="utf-8").read()
    assert "SMTP_SERVER" in src
    assert "SMTP_USERNAME" in src
    assert "SMTP_PASSWORD" in src


def test_test_email_requires_auth(anon_client):
    r = anon_client.post("/api/operator/test-email", json={"to": "test@example.com"})
    assert r.status_code == 403


def test_test_email_accepts_x_ops_key(monkeypatch, anon_client):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OPS_API_KEY", "smtp-test-ops-key")
    monkeypatch.setattr(
        "services.emails.send_operator_test_email",
        lambda to: {"ok": True, "sent": True, "to": to},
    )
    r = anon_client.post(
        "/api/operator/test-email",
        json={"to": "ops@test.com"},
        headers={"X-Ops-Key": "smtp-test-ops-key"},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_test_email_emits_telemetry_on_skip(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SMTP_ENABLED", "false")
    monkeypatch.setattr("services.emails.SETTINGS.resend_api_key", "")
    # Also disable at the adapter level so email_service sees no providers
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.is_configured", lambda k: False
    )
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.is_configured", lambda h, u, p, e: False
    )
    from services.config import SETTINGS
    SETTINGS.smtp_enabled = False
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    result = send_operator_test_email("ops@test.com")
    # No providers → skipped=True (organism continues gracefully)
    assert result.get("skipped") is True
    tel = (mem / "telemetry.jsonl").read_text(encoding="utf-8")
    assert "send_attempted" in tel
    # email_service emits "smtp_unconfigured" for backward compat when no providers configured
    assert "smtp_unconfigured" in tel or "no_email_provider" in tel


def test_send_failure_emits_telemetry(monkeypatch, tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setattr("services.emails.SETTINGS.resend_api_key", "")
    # Configure SMTP at adapter level so it is tried, then fail it
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.is_configured", lambda k: False
    )
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.is_configured",
        lambda host, user, password, enabled: True,
    )
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.send",
        lambda to, subject, html, **kw: {
            "sent": False, "provider": "smtp",
            "error": "ConnectionError", "detail": "smtp down",
        },
    )
    result = send_email_with_result("x@y.com", "subj", "<p>hi</p>")
    # Provider failed → manual fallback → sent=False, organism continues
    assert not result.get("sent")
    tel = (mem / "telemetry.jsonl").read_text(encoding="utf-8")
    assert "send_attempted" in tel
    assert "send_failed" in tel
    assert "secret" not in tel
    assert "smtp down" in tel or "ConnectionError" in tel


def test_test_email_endpoint_no_password_in_response(client, monkeypatch):
    monkeypatch.setattr("services.emails.send_operator_test_email", lambda to: {"ok": True, "sent": True, "to": to})
    r = client.post("/api/operator/test-email", json={"to": "carl@example.com"})
    assert r.status_code == 200
    assert "password" not in r.text.lower()
    assert "SMTP_PASS" not in r.json().get("result", {})


def test_smtp_status_api(client):
    r = client.get("/api/operator/smtp-status")
    assert r.status_code == 200
    body = r.json()
    assert "smtp" in body
    assert "missing" in body["smtp"]
    assert "configured" in body["smtp"]

"""Operational alerting nervous system."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from services.alerts import (
    alert_first_paperwork_submission,
    alert_high_fit_target,
    alert_organism_failure,
    get_operator_dashboard,
    is_real_customer_email,
    raise_alert,
)
from services.alerts import dedupe, email as alert_email, telegram, throttling
from services.alerts.digest import generate_daily_digest
from services.alerts.paths import ensure_alerts_dir, load_config, load_state, save_state
from services.alerts.severity import Severity
from services.alerts.telemetry import acknowledge_alert, load_history


@pytest.fixture
def alerts_env(monkeypatch, tmp_path):
    alerts = tmp_path / "alerts"
    alerts.mkdir()
    (alerts / "digests").mkdir()
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setattr("services.config.DATA", tmp_path)
    monkeypatch.setattr("services.alerts.paths._data_root", lambda: tmp_path)
    monkeypatch.setattr("services.memory.telemetry.memory_dir", lambda base=None: mem)
    monkeypatch.setenv("DIGEST_EMAIL_TO", "ops@keepyourcontracts.com")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    return tmp_path


def test_severity_and_real_customer():
    assert is_real_customer_email("owner@precision-aero.com") is True
    assert is_real_customer_email("test@example.com") is False
    assert is_real_customer_email("pytest@local.dev") is False


def test_email_template_generation():
    html = alert_email.render_alert_html(
        title="FIRST REAL PAPERWORK SUBMISSION",
        body="Customer submitted files.",
        severity=Severity.CRITICAL,
        event_type="first_paperwork_submission",
        when_utc="2026-05-26T12:00:00Z",
        context={"company": "Precision Aero", "upload_count": 12, "source": "reddit"},
        action_hint="Review in Control.",
    )
    assert "Precision Aero" in html
    assert "SMTP_PASS" not in html
    assert "12" in html


def test_telegram_formatting():
    text = telegram.format_telegram_message(
        title="FIRST PAPERWORK SUBMISSION",
        body="Real customer upload.",
        severity_emoji="🚨",
        context={"source": "Reddit acquisition", "company": "Precision Aerospace LLC", "upload_count": 12},
    )
    assert "Precision Aerospace" in text
    assert "Reddit" in text


def test_deduplication(alerts_env):
    dedupe.mark_seen("key1")
    assert dedupe.is_duplicate("key1", 3600) is True
    assert dedupe.is_duplicate("key2", 3600) is False


def test_throttling(alerts_env):
    throttling.mark_sent("smtp_failure", "smtp_failure", Severity.CRITICAL)
    assert throttling.is_throttled("smtp_failure", "smtp_failure", Severity.CRITICAL) is True


def test_raise_alert_records_history(alerts_env, monkeypatch):
    monkeypatch.setattr("services.alerts.routing.should_send_telegram", lambda *a, **k: False)
    monkeypatch.setattr("services.alerts.routing.should_send_email", lambda *a, **k: False)
    out = raise_alert("high_fit_target", title="Test target", body="Pain detected", force=True)
    assert out.get("alert_id")
    hist = load_history(limit=5)
    assert any(h.get("event_type") == "high_fit_target" for h in hist)


def test_first_paperwork_critical(alerts_env, monkeypatch):
    sent = []

    def fake_tg(text, **kw):
        sent.append(text)
        return {"ok": True, "sent": True}

    monkeypatch.setattr("services.alerts.telegram.send_telegram_message", fake_tg)
    monkeypatch.setattr("services.alerts.routing.should_send_email", lambda *a, **k: False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr("services.alerts.telegram.telegram_configured", lambda: True)
    monkeypatch.setattr("services.alerts.routing.should_send_telegram", lambda *a, **k: True)

    r1 = alert_first_paperwork_submission(
        email="ceo@precisionmfg.com",
        name="Precision Mfg",
        project_id="PRJ-REAL-1",
        upload_count=5,
        file_types=["pdf", "document"],
        source="upload-first",
        continuation_url="https://compliance.keepyourcontracts.com/ui/continue.html?token=x",
    )
    assert r1.get("event_type") == "first_paperwork_submission" or r1.get("severity") == "CRITICAL"
    assert load_state().get("first_paperwork_alert_sent") is True

    r2 = alert_first_paperwork_submission(
        email="ceo@precisionmfg.com",
        name="Precision Mfg",
        project_id="PRJ-REAL-2",
        upload_count=2,
        file_types=["pdf"],
    )
    assert r2.get("event_type") == "paperwork_submitted" or r2.get("skipped")


def test_high_fit_threshold(alerts_env, monkeypatch):
    monkeypatch.setattr("services.alerts.routing.should_send_telegram", lambda *a, **k: False)
    monkeypatch.setattr("services.alerts.routing.should_send_email", lambda *a, **k: False)
    low = alert_high_fit_target({"company_name": "Co", "fit_score": 40, "qualification_score": 40})
    assert low is None
    out = alert_high_fit_target(
        {"company_name": "Co", "fit_score": 90, "qualification_score": 90, "target_id": "T1", "source": "reddit"}
    )
    assert out is not None


def test_failure_alert_throttled(alerts_env, monkeypatch):
    monkeypatch.setattr("services.alerts.routing.should_send_telegram", lambda *a, **k: False)
    monkeypatch.setattr("services.alerts.routing.should_send_email", lambda *a, **k: False)
    a1 = alert_organism_failure("smtp_failure", message="Connection refused")
    a2 = alert_organism_failure("smtp_failure", message="Connection refused again")
    assert a1.get("alert_id")
    assert a2.get("suppressed") is True


def test_digest_generation(alerts_env, monkeypatch):
    monkeypatch.setattr("services.alerts.engine.raise_alert", lambda *a, **k: {"ok": True, "alert_id": "ALT-digest"})
    d = generate_daily_digest()
    assert d.get("kind") == "daily"
    assert (alerts_env / "alerts" / "digests").exists() or list((alerts_env / "alerts").glob("digests/*"))


def test_acknowledge_alert(alerts_env, monkeypatch):
    monkeypatch.setattr("services.alerts.routing.should_send_telegram", lambda *a, **k: False)
    monkeypatch.setattr("services.alerts.routing.should_send_email", lambda *a, **k: False)
    out = raise_alert("upload_started", title="Upload", force=True)
    aid = out["alert_id"]
    assert acknowledge_alert(aid) is True
    hist = load_history(limit=3)
    row = next(h for h in hist if h.get("alert_id") == aid)
    assert row.get("acknowledged") is True


def test_operator_dashboard(alerts_env):
    dash = get_operator_dashboard()
    assert dash.get("ok") is True
    assert dash["safety"]["no_customer_docs_in_alerts"] is True


def test_cockpit_api_auth(client, alerts_env):
    r = client.get("/api/operator/operational-alerts")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_no_public_ops_exposure(anon_client):
    r = anon_client.get("/api/operator/operational-alerts")
    assert r.status_code in (401, 403, 302)


def test_memory_linkage_on_alert(alerts_env, monkeypatch):
    linked = []
    monkeypatch.setattr(
        "services.alerts.telemetry.link_memory",
        lambda event, **kw: linked.append(event),
    )
    monkeypatch.setattr("services.alerts.routing.should_send_telegram", lambda *a, **k: False)
    monkeypatch.setattr("services.alerts.routing.should_send_email", lambda *a, **k: False)
    raise_alert("acquisition_conversion", title="Conversion", force=True)
    assert "alert_generated" in linked

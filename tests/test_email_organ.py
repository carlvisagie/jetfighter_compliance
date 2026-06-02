"""Email organ architecture tests.

Verifies the full adapter-boundary contract:
  - Resend success path
  - Resend failure → SMTP success (fallback_used=True)
  - All providers fail → manual copyable fallback (organism never blocks)
  - Payment link always generated, even on total provider failure
  - Outreach invite always generated, even on total provider failure
  - Delivery record written for every attempt
  - No business logic inside provider adapters
  - Lead/intake IDs tracked in delivery record
  - send_operator_alert compatibility with alerts/engine
"""
from __future__ import annotations

import ast
import json
import pathlib
from typing import Any, Dict

import pytest


# ---------------------------------------------------------------------------
# Adapter stubs
# ---------------------------------------------------------------------------

def _stub_resend_ok(monkeypatch):
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.is_configured",
        lambda key: True,
    )
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.send",
        lambda to, subject, html, *, from_addr, api_key: {
            "sent": True, "provider": "resend", "provider_id": "fake-resend-id",
        },
    )


def _stub_resend_fail(monkeypatch):
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.is_configured",
        lambda key: True,
    )
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.send",
        lambda to, subject, html, *, from_addr, api_key: {
            "sent": False, "provider": "resend",
            "error": "ConnectionError", "detail": "network down",
        },
    )


def _stub_resend_absent(monkeypatch):
    monkeypatch.setattr(
        "services.communications.adapters.resend_adapter.is_configured",
        lambda key: False,
    )


def _stub_smtp_ok(monkeypatch):
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.is_configured",
        lambda host, user, password, enabled: True,
    )
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.send",
        lambda to, subject, html, *, host, port, user, password, from_addr: {
            "sent": True, "provider": "smtp",
        },
    )


def _stub_smtp_fail(monkeypatch):
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.is_configured",
        lambda host, user, password, enabled: True,
    )
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.send",
        lambda to, subject, html, *, host, port, user, password, from_addr: {
            "sent": False, "provider": "smtp",
            "error": "ConnectionError", "detail": "smtp down",
        },
    )


def _stub_smtp_absent(monkeypatch):
    monkeypatch.setattr(
        "services.communications.adapters.smtp_adapter.is_configured",
        lambda host, user, password, enabled: False,
    )


# ---------------------------------------------------------------------------
# Fixture: isolated delivery log
# ---------------------------------------------------------------------------

@pytest.fixture
def email_env(tmp_path, monkeypatch):
    log_dir = tmp_path / "comms"
    log_dir.mkdir()
    monkeypatch.setattr(
        "services.communications.delivery_record._log_dir",
        lambda: log_dir,
    )
    return tmp_path


def _log_rows(email_env) -> list:
    log = email_env / "comms" / "email_delivery.jsonl"
    if not log.is_file():
        return []
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# 1. Resend success
# ---------------------------------------------------------------------------

def test_resend_success(email_env, monkeypatch):
    _stub_resend_ok(monkeypatch)
    _stub_smtp_absent(monkeypatch)

    from services.communications.email_service import send_raw
    result = send_raw("customer@example.com", "Hello", "<p>hi</p>", intent="test")

    assert result["sent"] is True
    assert result["provider_succeeded"] == "resend"
    assert result["fallback_used"] is False
    assert result["manual_fallback_generated"] is False
    assert "resend" in result["provider_attempted"]
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# 2. Resend failure → SMTP success
# ---------------------------------------------------------------------------

def test_resend_failure_smtp_success(email_env, monkeypatch):
    _stub_resend_fail(monkeypatch)
    _stub_smtp_ok(monkeypatch)

    from services.communications.email_service import send_raw
    result = send_raw("customer@example.com", "Hello", "<p>hi</p>", intent="test")

    assert result["sent"] is True
    assert result["provider_succeeded"] == "smtp"
    assert result["fallback_used"] is True
    assert result["manual_fallback_generated"] is False
    assert "resend" in result["provider_attempted"]
    assert "smtp" in result["provider_attempted"]


# ---------------------------------------------------------------------------
# 3. Both fail → manual fallback (organism never blocks)
# ---------------------------------------------------------------------------

def test_all_providers_fail_manual_fallback(email_env, monkeypatch):
    _stub_resend_fail(monkeypatch)
    _stub_smtp_fail(monkeypatch)

    from services.communications.email_service import send_raw
    result = send_raw("customer@example.com", "Hello", "<p>Copy this</p>", intent="test")

    assert result["sent"] is False
    assert result["manual_fallback_generated"] is True
    assert result["ok"] is True  # organism continues
    assert result.get("manual_copy_text") or result.get("manual_copy_html")
    assert result.get("operator_instruction")


# ---------------------------------------------------------------------------
# 4. Payment link still generated on total provider failure
# ---------------------------------------------------------------------------

def test_payment_link_generated_on_provider_failure(email_env, monkeypatch):
    _stub_resend_fail(monkeypatch)
    _stub_smtp_fail(monkeypatch)

    monkeypatch.setattr(
        "services.intake.payment_products.get_payment_product",
        lambda pid: {
            "id": pid,
            "title": "CMMC L1 Bundle",
            "price_display": "$4,997",
            "paypal_url": "https://paypal.com/pay/cmmc-l1-test",
        },
    )

    from services.communications.email_service import send_payment_link
    result = send_payment_link(
        to_email="cust@acme.com",
        customer_name="John Doe",
        company="Acme",
        product_id="cmmc_l1",
        intake_id="FB-abc123",
    )

    assert result["manual_fallback_generated"] is True
    assert result.get("paypal_url") == "https://paypal.com/pay/cmmc-l1-test"
    assert result.get("product_id") == "cmmc_l1"
    # PayPal URL must be in the copyable fallback text so operator can forward it
    copy = (result.get("manual_copy_text") or "") + (result.get("manual_copy_html") or "")
    assert "paypal.com" in copy


# ---------------------------------------------------------------------------
# 5. Outreach invite still generated on total provider failure
# ---------------------------------------------------------------------------

def test_outreach_invite_generated_on_provider_failure(email_env, monkeypatch):
    _stub_resend_fail(monkeypatch)
    _stub_smtp_fail(monkeypatch)

    from services.communications.email_service import send_outreach_invite
    result = send_outreach_invite(
        to_email="lead@acme.com",
        company_name="Acme Corp",
        contact_name="Jane Smith",
        invite_url="https://compliance.keepyourcontracts.com/?ref=LD-001",
        upload_url="https://compliance.keepyourcontracts.com/ui/intake?ref=LD-001",
        lead_id="LD-001",
    )

    assert result["manual_fallback_generated"] is True
    assert result.get("draft")  # template was built
    assert result["intent"] == "outreach_invite"
    assert result["lead_id"] == "LD-001"
    assert "LD-001" in (result.get("manual_copy_text") or result.get("manual_copy_html") or "")


# ---------------------------------------------------------------------------
# 6. Delivery record written for every attempt (success)
# ---------------------------------------------------------------------------

def test_delivery_record_written_on_success(email_env, monkeypatch):
    _stub_resend_ok(monkeypatch)
    _stub_smtp_absent(monkeypatch)

    from services.communications.email_service import send_raw
    send_raw("a@b.com", "Subject", "<p>body</p>", intent="test_record_success")

    rows = _log_rows(email_env)
    assert rows, "delivery log is empty"
    row = rows[-1]
    assert row["intent"] == "test_record_success"
    assert row["to"] == "a@b.com"
    assert row["sent"] is True
    assert row["message_id"].startswith("MSG-")
    assert len(row["message_hash"]) == 32
    assert "timestamp_utc" in row
    assert "provider_attempted" in row


# ---------------------------------------------------------------------------
# 7. Delivery record written on failure too
# ---------------------------------------------------------------------------

def test_delivery_record_written_on_failure(email_env, monkeypatch):
    _stub_resend_fail(monkeypatch)
    _stub_smtp_fail(monkeypatch)

    from services.communications.email_service import send_raw
    send_raw("x@y.com", "Fail", "<p>x</p>", intent="test_record_failure")

    rows = _log_rows(email_env)
    assert rows
    row = rows[-1]
    assert row["sent"] is False
    assert row["manual_fallback_generated"] is True
    assert row["intent"] == "test_record_failure"


# ---------------------------------------------------------------------------
# 8. No business logic inside resend adapter
# ---------------------------------------------------------------------------

def test_resend_adapter_has_no_business_logic():
    src = pathlib.Path("services/communications/adapters/resend_adapter.py").read_text()
    tree = ast.parse(src)
    forbidden = ("intake", "acquisition", "alerts", "email_utils", "email_service",
                 "payment", "lead", "config")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = (getattr(node, "module", "") or "").lower()
            for alias in getattr(node, "names", []):
                name = (getattr(alias, "name", "") or "").lower()
                for bad in forbidden:
                    assert bad not in mod, f"resend_adapter imports from '{mod}' (forbidden: {bad})"
                    assert bad not in name, f"resend_adapter imports '{name}' (forbidden: {bad})"


# ---------------------------------------------------------------------------
# 9. No business logic inside smtp adapter
# ---------------------------------------------------------------------------

def test_smtp_adapter_has_no_business_logic():
    src = pathlib.Path("services/communications/adapters/smtp_adapter.py").read_text()
    tree = ast.parse(src)
    forbidden = ("intake", "acquisition", "alerts", "email_utils", "email_service",
                 "payment", "lead", "config")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = (getattr(node, "module", "") or "").lower()
            for alias in getattr(node, "names", []):
                name = (getattr(alias, "name", "") or "").lower()
                for bad in forbidden:
                    assert bad not in mod, f"smtp_adapter imports from '{mod}' (forbidden: {bad})"
                    assert bad not in name, f"smtp_adapter imports '{name}' (forbidden: {bad})"


# ---------------------------------------------------------------------------
# 10. Lead and intake IDs tracked in delivery record
# ---------------------------------------------------------------------------

def test_delivery_record_tracks_lead_id(email_env, monkeypatch):
    _stub_resend_ok(monkeypatch)
    _stub_smtp_absent(monkeypatch)

    from services.communications.email_service import send_outreach_invite
    send_outreach_invite(
        to_email="lead@test.com",
        invite_url="https://example.com",
        lead_id="LD-TRACK001",
    )

    rows = _log_rows(email_env)
    row = rows[-1]
    assert row["lead_id"] == "LD-TRACK001"
    assert row["intent"] == "outreach_invite"


def test_delivery_record_tracks_intake_id(email_env, monkeypatch):
    _stub_resend_ok(monkeypatch)
    _stub_smtp_absent(monkeypatch)
    monkeypatch.setattr(
        "services.intake.payment_products.get_payment_product",
        lambda pid: {"id": pid, "title": "T", "price_display": "$1", "paypal_url": "https://p.com"},
    )

    from services.communications.email_service import send_payment_link
    send_payment_link(
        to_email="c@t.com",
        product_id="cmmc_l1",
        intake_id="FB-TRACK999",
    )

    rows = _log_rows(email_env)
    row = rows[-1]
    assert row["intake_id"] == "FB-TRACK999"
    assert row["intent"] == "payment_link"


# ---------------------------------------------------------------------------
# 11. send_operator_alert compatibility
# ---------------------------------------------------------------------------

def test_send_operator_alert_sent(email_env, monkeypatch):
    _stub_resend_ok(monkeypatch)
    _stub_smtp_absent(monkeypatch)

    from services.communications.email_service import send_operator_alert
    result = send_operator_alert(
        to_email="ops@keepyourcontracts.com",
        subject="Alert: new intake",
        html_body="<p>An intake arrived.</p>",
    )
    assert result["sent"] is True
    assert result["intent"] == "operator_alert"


def test_send_operator_alert_manual_fallback_on_failure(email_env, monkeypatch):
    _stub_resend_fail(monkeypatch)
    _stub_smtp_fail(monkeypatch)

    from services.communications.email_service import send_operator_alert
    result = send_operator_alert(
        to_email="ops@keepyourcontracts.com",
        subject="Critical: payment failed",
        html_body="<p>Something went wrong.</p>",
    )
    assert result["sent"] is False
    assert result["manual_fallback_generated"] is True
    assert result["ok"] is True  # alert still available as copy
    assert result.get("manual_copy_text") or result.get("manual_copy_html")


# ---------------------------------------------------------------------------
# 12. No providers configured → graceful skip (not an error)
# ---------------------------------------------------------------------------

def test_no_providers_graceful_skip(email_env, monkeypatch):
    """When no providers are configured at all → skipped, not a failure, no manual fallback."""
    _stub_resend_absent(monkeypatch)
    _stub_smtp_absent(monkeypatch)

    from services.communications.email_service import send_raw
    result = send_raw("a@b.com", "Subj", "<p>hi</p>")

    assert result.get("skipped") is True
    assert result.get("sent") is False
    assert result.get("manual_fallback_generated") is False
    assert result.get("reason") == "no_email_provider_configured"

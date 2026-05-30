"""
Stripe ban guardrail — fails if active Stripe code is reintroduced.

PayPal is the payment path. See docs/STRIPE_PURGE_AUDIT.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PRODUCTION_SCAN_ROOTS = (
    ROOT / "server.py",
    ROOT / "services",
    ROOT / "ui",
    ROOT / "render.yaml",
    ROOT / "requirements.txt",
)

# Allowed only in this guardrail test and the purge audit doc.
ALLOWLIST_FILES = {
    ROOT / "tests" / "test_stripe_ban_guardrail.py",
    ROOT / "docs" / "STRIPE_PURGE_AUDIT.md",
}

FORBIDDEN_PATTERNS = [
    (re.compile(r"/webhooks/stripe", re.I), "Stripe webhook route"),
    (re.compile(r"stripe_hook", re.I), "stripe_hook module reference"),
    (re.compile(r"verify_stripe_signature", re.I), "Stripe signature verifier"),
    (re.compile(r"parse_checkout_completed", re.I), "Stripe checkout parser"),
    (re.compile(r"STRIPE_WEBHOOK_SECRET", re.I), "STRIPE_WEBHOOK_SECRET env"),
    (re.compile(r"stripe_webhook_secret", re.I), "stripe_webhook_secret setting"),
    (re.compile(r"Stripe-Signature", re.I), "Stripe-Signature header"),
    (re.compile(r"buy\.stripe\.com", re.I), "Stripe Payment Link URL"),
    (re.compile(r"checkout\.session", re.I), "Stripe checkout.session event"),
    (re.compile(r"payment_intent", re.I), "Stripe payment_intent"),
    (re.compile(r"\bstripe-python\b", re.I), "stripe-python package"),
    (re.compile(r"\bstripe\.js\b", re.I), "stripe.js"),
    (re.compile(r"pk_live_[0-9a-zA-Z]+", re.I), "Stripe live publishable key"),
    (re.compile(r"sk_live_[0-9a-zA-Z]+", re.I), "Stripe live secret key"),
    (re.compile(r"pk_test_[0-9a-zA-Z]+", re.I), "Stripe test publishable key"),
    (re.compile(r"sk_test_[0-9a-zA-Z]+", re.I), "Stripe test secret key"),
]


def _iter_scan_files():
    for root in PRODUCTION_SCAN_ROOTS:
        if root.is_file():
            yield root
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path in ALLOWLIST_FILES:
                continue
            if "__pycache__" in path.parts:
                continue
            if path.suffix.lower() in {".py", ".html", ".js", ".css", ".yaml", ".yml", ".txt", ".json"}:
                yield path


def test_no_active_stripe_in_production_paths():
    violations: list[str] = []
    for path in _iter_scan_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rx, label in FORBIDDEN_PATTERNS:
            if rx.search(text):
                violations.append(f"{path.relative_to(ROOT)}: {label}")
    assert not violations, "Stripe ban violated:\n" + "\n".join(sorted(set(violations)))


def test_stripe_webhook_route_returns_404():
    from fastapi.testclient import TestClient

    from server import app

    client = TestClient(app)
    r = client.post("/webhooks/stripe", json={})
    assert r.status_code == 404, r.text


def test_stripe_hook_module_removed():
    assert not (ROOT / "services" / "stripe_hook.py").is_file()


def test_stripe_webhook_test_removed():
    assert not (ROOT / "tests" / "test_stripe_webhook.py").is_file()

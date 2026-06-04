"""
Stripe ban guardrail — fails if active Stripe code is reintroduced.

PayPal is the payment path. See docs/STRIPE_FINAL_STATUS.md.
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

# Allowed only in this guardrail test and the final status doc.
ALLOWLIST_FILES = {
    ROOT / "tests" / "test_stripe_ban_guardrail.py",
    ROOT / "docs" / "STRIPE_FINAL_STATUS.md",
}

QUARANTINE_EXCLUDE_PARTS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "node_modules",
        "data",
        "bin",
    }
)

_TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".html",
        ".js",
        ".css",
        ".yaml",
        ".yml",
        ".txt",
        ".json",
        ".jsonl",
        ".md",
        ".ps1",
        ".sh",
        ".toml",
        ".ini",
        ".cfg",
        ".xml",
    }
)


def _under_archive(path: Path) -> bool:
    parts = path.resolve().parts
    archive_parts = (ROOT / "archive" / "legacy" / "stripe").resolve().parts
    if len(parts) >= len(archive_parts) and parts[: len(archive_parts)] == archive_parts:
        return True
    return False


def _quarantine_excluded(path: Path) -> bool:
    if _under_archive(path):
        return True
    return any(part in QUARANTINE_EXCLUDE_PARTS for part in path.parts)

QUARANTINE_ALLOWLIST = ALLOWLIST_FILES | {
    ROOT / "tests" / "test_organism_integration.py",
    ROOT / "tests" / "test_kyc_guardrails.py",
    ROOT / ".github" / "workflows" / "kyc_guardrails.yml",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "LAUNCH_PATH.md",
    ROOT / "docs" / "KYC_CONSTITUTION.md",
    ROOT / "docs" / "README.md",
    # Deployment readiness brief documents the removal of Stripe — it
    # references the name to declare its banned status, same as STRIPE_FINAL_STATUS.md.
    ROOT / "docs" / "KYC_DEPLOYMENT_READINESS_BRIEF_v2.md",
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


def _repo_wide_stripe_hits() -> list[str]:
    """Return paths outside archive with stripe-like content (excluding allowlist)."""
    hits: list[str] = []
    rx = re.compile(r"stripe", re.I)
    allow = {p.resolve() for p in QUARANTINE_ALLOWLIST}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if _quarantine_excluded(path):
            continue
        if path.resolve() in allow:
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if rx.search(text):
            hits.append(str(path.relative_to(ROOT)))
    return sorted(set(hits))


def test_no_stripe_outside_archive_except_allowlist():
    hits = _repo_wide_stripe_hits()
    assert not hits, "Stripe references outside archive/legacy/stripe:\n" + "\n".join(hits)

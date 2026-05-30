"""
KYC agent protection guardrails — static + contract checks for CI.

Fails on conditions that future agents must not introduce.
Run: pytest tests/test_kyc_guardrails.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "ui"
SERVICES_ROOT = ROOT / "services"

CANONICAL_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "docs" / "KYC_CONSTITUTION.md",
    ROOT / "docs" / "CENTRAL_MEMORY.md",
    ROOT / "docs" / "KYC_ORGANISM_INTEGRATION_AUDIT.md",
    ROOT / "docs" / "LAUNCH_PATH.md",
]

PUBLIC_HTML_FILES = [
    "shop.html",
    "inquiry.html",
    "intake.html",
    "upload.html",
    "continue.html",
    "index.html",
    "vendor_quote.html",
]

FORBIDDEN_PUBLIC_HREFS = (
    "/ui/control.html",
    "/ui/memory.html",
    "/ui/command.html",
    "/ui/webhook_test.html",
)

BACKUP_UI_GLOBS = ("*.bak", "*.backup*.html", "*~")

# Production service code — not tests/scripts
PRODUCTION_CODE_ROOTS = (
    SERVICES_ROOT,
    ROOT / "server.py",
)

FORBIDDEN_PRODUCTION_PATTERNS = [
    (re.compile(r"MOCK_PRODUCTION\s*=\s*True", re.I), "MOCK_PRODUCTION flag"),
    (re.compile(r"USE_FAKE_DISCOVERY\s*=\s*True", re.I), "USE_FAKE_DISCOVERY flag"),
    (re.compile(r"fake_production\s*=\s*True", re.I), "fake_production flag"),
    (re.compile(r"seed_mock_leads\s*\(", re.I), "seed_mock_leads() in production code"),
]


def test_canonical_agent_docs_exist():
    missing = [p for p in CANONICAL_DOCS if not p.is_file()]
    assert not missing, f"Missing canonical docs: {missing}"


def test_agents_md_references_constitution():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "KYC IRON LAW" in text
    assert "KYC_CONSTITUTION.md" in text
    assert "central memory" in text.lower()


def test_constitution_contains_iron_law():
    text = (ROOT / "docs" / "KYC_CONSTITUTION.md").read_text(encoding="utf-8")
    assert "IRON LAW" in text
    assert "sacred" in text.lower() or "Sacred" in text
    assert "change gate" in text.lower() or "Change gate" in text


def test_no_ui_backup_artifacts_in_repo():
    found = []
    for pattern in BACKUP_UI_GLOBS:
        found.extend(UI_ROOT.rglob(pattern))
    assert not found, f"Remove backup UI files: {found}"


@pytest.mark.parametrize("name", PUBLIC_HTML_FILES)
def test_public_html_files_do_not_link_ops_pages(name: str):
    path = UI_ROOT / name
    if not path.is_file():
        pytest.skip(f"{name} not present")
    html = path.read_text(encoding="utf-8", errors="replace")
    for href in FORBIDDEN_PUBLIC_HREFS:
        assert href not in html, f"{href} linked or embedded in ui/{name}"


def test_internal_control_and_memory_have_noindex():
    for name in ("control.html", "memory.html", "login.html"):
        path = UI_ROOT / name
        assert path.is_file(), name
        lower = path.read_text(encoding="utf-8", errors="replace").lower()
        assert "noindex" in lower, f"{name} missing noindex"
        assert "nofollow" in lower, f"{name} missing nofollow"


def test_discovery_rejects_mock_domains():
    from services.acquisition.discovery import validate_row
    from services.acquisition.intelligence_paths import is_mock_domain

    assert is_mock_domain("contact@example.com")
    assert is_mock_domain("https://example.com")
    row, err = validate_row(
        {"company_name": "Acme", "website": "https://example.com", "segment": "cmmc_l1"},
        1,
    )
    assert row is None
    assert err and "mock" in err.lower()


def test_no_fake_production_flags_in_services():
    violations = []
    for root in PRODUCTION_CODE_ROOTS:
        if root.is_file():
            files = [root]
        else:
            files = list(root.rglob("*.py"))
        for py in files:
            if "__pycache__" in str(py):
                continue
            text = py.read_text(encoding="utf-8", errors="replace")
            for rx, label in FORBIDDEN_PRODUCTION_PATTERNS:
                if rx.search(text):
                    violations.append(f"{py}: {label}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("name", PUBLIC_HTML_FILES)
def test_customer_pages_upload_first_no_steps(name: str):
    path = UI_ROOT / name
    if not path.is_file():
        pytest.skip(f"{name} not present")
    lower = path.read_text(encoding="utf-8", errors="replace").lower()
    assert "step 1" not in lower and "step 2" not in lower, f"steps on {name}"
    if name in ("shop.html", "inquiry.html", "upload.html", "index.html"):
        assert "give us exactly what you have" in lower, name


def test_github_guardrails_workflow_exists():
    wf = ROOT / ".github" / "workflows" / "kyc_guardrails.yml"
    assert wf.is_file(), "Missing .github/workflows/kyc_guardrails.yml"
    content = wf.read_text(encoding="utf-8")
    assert "test_public_ui_exposure" in content
    assert "test_kyc_guardrails" in content
    assert "test_stripe_ban_guardrail" in content
    assert "pytest tests/" in content

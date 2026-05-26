"""Upload-first customer experience guardrails."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "ui"

CUSTOMER_PAGES = [
    "shop.html",
    "inquiry.html",
    "intake.html",
    "upload.html",
    "continue.html",
    "index.html",
    "vendor_quote.html",
]

FORBIDDEN_STEP_RE = re.compile(r"Step\s+[123]", re.I)
FORBIDDEN_PHRASES = [
    "structured readiness support",
    "begin structured readiness",
    "start compliance intake",
    "compliance intake",
    "launch onboarding workflow",
    "enterprise compliance workflow platform",
    "ask a question",
    "mode=question",
]

REQUIRED_PHRASES = [
    "give us exactly what you have",
    "you do not need perfect",
    "upload my paperwork",
]

UPLOAD_CTA_RE = re.compile(r"upload\s+(my\s+)?paperwork|upload\s+what\s+i\s+have", re.I)


@pytest.mark.parametrize("name", CUSTOMER_PAGES)
def test_no_step_123_on_customer_pages(name: str):
    html = (UI / name).read_text(encoding="utf-8", errors="replace")
    assert not FORBIDDEN_STEP_RE.search(html), f"Step 1/2/3 found on {name}"


@pytest.mark.parametrize("name", CUSTOMER_PAGES)
def test_no_friction_decreasing_phrases(name: str):
    lower = (UI / name).read_text(encoding="utf-8", errors="replace").lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lower, f"{phrase!r} on {name}"


@pytest.mark.parametrize("name", ["shop.html", "inquiry.html", "upload.html", "index.html"])
def test_upload_first_core_copy(name: str):
    lower = (UI / name).read_text(encoding="utf-8", errors="replace").lower()
    for phrase in REQUIRED_PHRASES:
        assert phrase in lower, f"Missing {phrase!r} on {name}"


@pytest.mark.parametrize("name", ["shop.html", "inquiry.html", "upload.html"])
def test_upload_cta_present(name: str):
    html = (UI / name).read_text(encoding="utf-8", errors="replace")
    assert UPLOAD_CTA_RE.search(html), f"No upload CTA on {name}"
    assert "kyc-upload-cta-primary" in html or "kyc-upload-cta-primary" in html


def test_inquiry_has_pre_contact_session_flow():
    html = (UI / "inquiry.html").read_text(encoding="utf-8", errors="replace")
    assert "customer-session-flow.js" in html
    assert "phaseMinInfo" in html
    assert "Create my secure workspace" in html
    assert "copyMagicLink" in html or "customer-session-flow" in html
    assert "KYCSessionFlow" in html


def test_qr_visible_on_upload_and_continue():
    upload = (UI / "upload.html").read_text(encoding="utf-8", errors="replace")
    cont = (UI / "continue.html").read_text(encoding="utf-8", errors="replace")
    assert "kyc-qr-block--prominent" in upload
    assert "qrImg" in upload or "qr.svg" in upload
    assert "customer-friction" in cont
    assert "initContinuePage" in cont


def test_intake_has_collapsed_advanced_only():
    html = (UI / "intake.html").read_text(encoding="utf-8", errors="replace")
    assert "<details" in html
    assert "ext_cmmc" in html
    assert "kyc-upload-cta-primary" in html


SECONDARY_HELP_CTA = "not sure what to upload"


@pytest.mark.parametrize("name", ["shop.html", "inquiry.html"])
def test_no_ask_question_cta(name: str):
    lower = (UI / name).read_text(encoding="utf-8", errors="replace").lower()
    assert "ask a question" not in lower
    assert "mode=question" not in lower


@pytest.mark.parametrize("name", ["shop.html", "inquiry.html"])
def test_secondary_help_cta_and_panel(name: str):
    html = (UI / name).read_text(encoding="utf-8", errors="replace").lower()
    assert SECONDARY_HELP_CTA in html
    assert "kyc-upload-help-panel" in html
    assert "upload whatever you already have" in html or "whatever you already have" in html


def test_primary_upload_cta_dominant_on_shop():
    html = (UI / "shop.html").read_text(encoding="utf-8", errors="replace")
    assert html.index("kyc-upload-cta-primary") < html.index("kyc-help-cta")
    assert "kyc-upload-help-details" in html
    assert "support queue" not in html.lower()
    assert "live chat" not in html.lower()


def test_help_panel_funnels_to_upload_not_ops():
    for name in ["shop.html", "inquiry.html"]:
        html = (UI / name).read_text(encoding="utf-8", errors="replace")
        assert "/ui/control.html" not in html
        assert "upload my paperwork" in html.lower()


def test_shop_upload_first_not_process_grid():
    from fastapi.testclient import TestClient
    from server import app

    r = TestClient(app).get("/ui/shop.html")
    assert r.status_code == 200
    text = r.text.lower()
    assert "how it works" not in text
    assert "readiness outcomes" not in text
    assert "service catalog" not in text

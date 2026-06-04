"""Founding Beta organism validation mode."""
from __future__ import annotations

import os

import pytest

from services.acquisition.acquisition_probability import (
    DEFAULT_MIN_PREY_SCORE,
    compute_adaptive_prey_threshold,
    passes_prey_gate,
    score_acquisition_probability,
)
from services.acquisition.connectors.reddit.author_intent import classify_author_intent
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.intelligence.soft_burden import score_soft_burden
from services.intake.messaging import BETA_HEADLINE, intake_messaging_blocks
from services.intake.mode import is_intake_mode
from services.intake.telemetry import emit_intake_event


@pytest.fixture
def beta_on(monkeypatch):
    monkeypatch.setenv("KYC_FOUNDING_BETA_MODE", "true")


def test_founding_beta_mode_default_on():
    assert is_intake_mode() is True


def test_intake_messaging_blocks():
    blocks = intake_messaging_blocks()
    assert BETA_HEADLINE in blocks["headline"]
    assert "upload-first" in blocks["intro"].lower()
    assert "partial" in blocks["upload_prompt"].lower()


def test_quiet_operational_burden_scores_soft():
    title = "Trying to understand what applies to us"
    body = "Prime contractor requested documentation. Small business — not sure whether we need CMMC level 2. Where do we start?"
    soft = score_soft_burden(title, body)
    assert soft["soft_burden_score"] >= 35
    assert soft.get("has_quiet_operational_need")


def test_quiet_prospect_can_queue_under_beta(beta_on):
    title = "Customer asked for security questionnaire"
    body = "Small business subcontractor — partial documentation. Do we actually need this? Where do we start?"
    cls = classify_post(title, body)
    intent = classify_author_intent(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] >= 40
    qual = {
        "prey_score": out["prey_score"],
        "acquisition_probability": out,
    }
    if intent["author_intent"] in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED"):
        assert passes_prey_gate(qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE)
    elif intent["author_intent"] == "UNKNOWN" and out["soft_burden_score"] >= 40:
        assert passes_prey_gate(qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE)


def test_consultant_still_rejected(beta_on):
    title = "CMMC AMA"
    body = "As a consultant I advise clients. Book a call for our webinar."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["queue_eligible"] is False
    assert not passes_prey_gate(
        {"prey_score": out["prey_score"], "acquisition_probability": out},
        cls,
        min_prey_score=DEFAULT_MIN_PREY_SCORE,
    )


def test_adaptive_threshold_targets_nonzero_queue(beta_on):
    candidates = [
        {"prey_score": 51, "deployable_intent": True, "low_predator": True, "has_operational_need": True},
        {"prey_score": 49, "deployable_intent": True, "low_predator": True, "has_operational_need": True},
        {"prey_score": 48, "deployable_intent": True, "low_predator": True, "has_operational_need": True},
    ]
    th = compute_adaptive_prey_threshold(DEFAULT_MIN_PREY_SCORE, candidates)
    assert th <= DEFAULT_MIN_PREY_SCORE
    would = sum(1 for c in candidates if c["prey_score"] >= th and c["deployable_intent"])
    assert would >= 1


def test_beta_telemetry_emits(beta_on):
    from services.memory.telemetry import load_telemetry

    emit_intake_event("beta_upload_started", metadata={"test": True})
    # emit_intake_event writes subsystem="intake" (post-beta rebrand);
    # the event_type retains the historical name for log continuity.
    rows = load_telemetry(limit=30, subsystem="intake")
    assert any(r.get("event_type") == "beta_upload_started" for r in rows)


def test_acquisition_dashboard_includes_founding_beta():
    from services.acquisition.orchestration import get_operator_dashboard

    dash = get_operator_dashboard()
    assert "founding_beta" in dash
    assert dash["founding_beta"].get("active") is True


def test_control_html_intake_strip(client):
    """Operator cockpit must render the intake strip in control.html.
    Post-rebrand: class is 'intake-strip' (was founding-beta-strip)."""
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    assert 'class="intake-strip"' in r.text
    assert "fb-paperwork-banner" in r.text

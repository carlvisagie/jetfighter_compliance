"""Founding beta acquisition discovery — queue, fallback, USASpending paperwork."""
from __future__ import annotations

import pytest

from services.acquisition.acquisition_probability import DEFAULT_MIN_PREY_SCORE, score_acquisition_probability
from services.acquisition.connectors.reddit.autonomy import decide_engagement
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post
from services.acquisition.founding_beta_mode import passes_founding_beta_prey_gate
from services.founding_beta.paperwork_prediction import predict_federal_supplier_paperwork
from services.founding_beta.reddit_discovery import (
    CycleDiagnostics,
    classify_queue_block,
    passes_founding_beta_fallback_gate,
)


IDEAL_TITLE = "VERY BASIC SMALL BUSINESS QUESTION - Which CMMC level?"
IDEAL_BODY = (
    "We provide office furniture to military bases. Prime contractor sent a questionnaire. "
    "Costs are beyond what we can afford. Can anyone provide simple insight on what level we need?"
)


def _qualify(title: str, body: str):
    post = {"title": title, "selftext": body, "post_id": "t1", "subreddit": "smallbusiness"}
    cls = classify_post(title, body)
    qual = qualify_post(post, cls)
    plan = decide_engagement(
        {"title": title, "selftext": body, "post_id": "t1", "subreddit": "smallbusiness", "num_comments": 2},
        cls,
        qual,
    )
    return post, cls, qual, plan


def test_ideal_cmmc_small_business_queues():
    _, cls, qual, plan = _qualify(IDEAL_TITLE, IDEAL_BODY)
    assert qual.get("prey_score", 0) >= DEFAULT_MIN_PREY_SCORE
    assert passes_founding_beta_prey_gate(qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE)
    assert plan.get("show_operator_queue") is True


def test_quiet_operational_burden_queues():
    _, cls, qual, plan = _qualify(
        "Level 2 question",
        "Which level applies to us? We store drawings. Prime contractor asked for documentation.",
    )
    assert passes_founding_beta_prey_gate(qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE)
    assert plan.get("show_operator_queue") is True


def test_customer_security_questionnaire_queues():
    _, cls, qual, plan = _qualify(
        "Security questionnaire",
        "Customer sent a security questionnaire. Partial policies in a spreadsheet. What do we need?",
    )
    assert qual.get("prey_score", 0) >= 42
    assert plan.get("show_operator_queue") is True


def test_vendor_onboarding_security_queues():
    _, cls, qual, plan = _qualify(
        "Vendor onboarding",
        "Vendor onboarding security requirements — MFA and evidence request from customer.",
    )
    assert qual.get("prey_score", 0) >= 42
    assert plan.get("show_operator_queue") is True


def test_consultant_ama_blocked():
    _, cls, qual, plan = _qualify(
        "CMMC AMA",
        "As a consultant I advise clients. Book a call for our webinar and pro tip guide.",
    )
    out = score_acquisition_probability("CMMC AMA", "As a consultant...", classification=cls)
    assert out["queue_eligible"] is False
    block = classify_queue_block(
        post={"post_id": "x"},
        cls=cls,
        qual=qual,
        plan=plan,
        effective_prey=50,
        min_fit_score=40,
        queued_this_cycle=0,
        target_queue_max=15,
    )
    assert block in ("predator_block", "predator_penalty", "prey_gate", "low_prey", "autonomy_defer")


def test_topic_only_skipped_or_low_tier():
    _, cls, qual, _ = _qualify(
        "CMMC news",
        "New rule announced for CMMC effective date. Just announced deadline extended.",
    )
    prob = qual.get("acquisition_probability") or {}
    assert int(prob.get("prey_tier", 4)) >= 4 or not qual.get("queue_eligible")


def test_fallback_pass_medium_operational():
    _, cls, qual, _ = _qualify(
        "SPRS help",
        "Prime contractor asked for SPRS score. What documentation is needed for vendor onboarding?",
    )
    assert passes_founding_beta_fallback_gate(qual, cls) or passes_founding_beta_prey_gate(
        qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE
    )


def test_empty_queue_diagnostics_counts():
    diag = CycleDiagnostics()
    post = {"post_id": "p1", "title": "t"}
    qual = {"prey_score": 48, "acquisition_probability": {"predator_class": "none", "predator_penalty": 10}}
    cls = {"author_intent": "UNKNOWN"}
    diag.record_block("prey_gate", post=post, qual=qual, cls=cls)
    out = diag.to_dict(effective_threshold=50, queued=0, discovered=3)
    assert out["zero_result_cycle"] is True
    assert out["near_miss_count"] >= 1
    assert "empty_queue_summary" in out


def test_usaspending_includes_likely_paperwork_prediction():
    pred = predict_federal_supplier_paperwork(
        "Acme Defense Machining LLC",
        notes="aerospace supplier government subcontractor",
        segment="manufacturing",
    )
    assert pred.get("likely_paperwork_prediction")
    assert pred.get("likely_outreach_angle")
    assert pred.get("why_might_upload_paperwork")
    assert "questionnaire" in pred.get("likely_paperwork_prediction", "").lower()

"""Soft burden intelligence — quiet operational confusion."""
from __future__ import annotations

import pytest

from services.acquisition.acquisition_probability import (
    DEFAULT_MIN_PREY_SCORE,
    MIN_PREY_FLOOR,
    compute_adaptive_prey_threshold,
    passes_prey_gate,
    score_acquisition_probability,
)
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post
from services.acquisition.intelligence.soft_burden import score_soft_burden

IDEAL_TITLE = "VERY BASIC SMALL BUSINESS QUESTION - Which CMMC level?"
IDEAL_BODY = (
    "We provide office furniture to military bases. Costs are beyond what we can afford. "
    "More confused than ever. Can anyone provide simple insight on what level we need?"
)


def test_which_cmmc_level_high_soft_burden():
    soft = score_soft_burden("Which CMMC level?", "Small business trying to understand.")
    assert soft["soft_burden_score"] >= 40


def test_ideal_post_must_queue():
    cls = classify_post(IDEAL_TITLE, IDEAL_BODY)
    out = score_acquisition_probability(IDEAL_TITLE, IDEAL_BODY, classification=cls)
    assert out["soft_burden_score"] >= 40
    assert out["queue_eligible"] is True
    assert out["prey_score"] >= DEFAULT_MIN_PREY_SCORE
    post = {"title": IDEAL_TITLE, "selftext": IDEAL_BODY, "subreddit": "smallbusiness"}
    qual = qualify_post(post, cls)
    assert passes_prey_gate(qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE)


def test_trying_to_understand_queues():
    title = "Trying to understand what applies to us"
    body = "We are a small subcontractor. Not sure whether CMMC Level 1 or 2 applies."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["soft_burden_score"] >= 45
    assert out["has_operational_need"] is True
    assert out["queue_eligible"] is True


def test_cui_operational_context_queues():
    title = "CUI question"
    body = "We receive CUI but do not distribute it. What level do we need for our contract?"
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["soft_burden_score"] >= 40
    assert out["queue_eligible"] is True


def test_thoughts_on_cmmc_low_prey():
    title = "Thoughts on CMMC Level 2?"
    body = "Discussion: what do you think about scoping for defense contractors in general?"
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] < DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is False


def test_consultant_ama_blocked():
    title = "CMMC AMA"
    body = "As a consultant I advise clients. Book a call. Here's my guide."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["queue_eligible"] is False
    assert out["predator_class"] in ("consultant", "ama", "educator", "promoter", "authority")


def test_quiet_confusion_without_panic():
    body = "Trying to understand CMMC. We don't know if this applies to us. What actually counts?"
    soft = score_soft_burden("CMMC question", body)
    assert soft["has_quiet_operational_need"] is True
    assert "Quiet confusion" in soft["soft_burden_badges"] or soft["soft_burden_score"] >= 45


def test_starvation_adaptive_relaxation():
    candidates = [
        {
            "prey_score": 50,
            "soft_burden_score": 55,
            "deployable_intent": True,
            "low_predator": True,
            "has_operational_need": True,
        },
    ]
    t = compute_adaptive_prey_threshold(58, candidates)
    assert t <= 58
    assert t >= MIN_PREY_FLOOR


def test_soft_burden_badges_present_for_ideal():
    soft = score_soft_burden(IDEAL_TITLE, IDEAL_BODY)
    assert len(soft["soft_burden_badges"]) >= 2

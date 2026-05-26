"""Acquisition probability — prey vs predator scoring."""
from __future__ import annotations

import pytest

from services.acquisition.acquisition_probability import (
    DEFAULT_MIN_PREY_SCORE,
    score_acquisition_probability,
)
from services.acquisition.connectors.reddit.author_intent import classify_author_intent
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post


@pytest.mark.parametrize(
    "title,body",
    [
        (
            "Where do I start with CMMC?",
            "Small subcontractor — prime sent a questionnaire and we're overwhelmed.",
        ),
        (
            "Can't afford CMMC",
            "We got asked for CMMC. I was tasked with this and don't know what documents we need.",
        ),
    ],
)
def test_high_prey_overwhelmed_contractor(title, body):
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] >= DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is True
    assert out["predator_penalty"] < 40


@pytest.mark.parametrize(
    "title,body,predator_kind",
    [
        ("CMMC AMA — ask me anything", "I'm a consultant and C3PAO. Book a call.", "ama"),
        ("How CMMC works", "Here's how this works. You should start with SSP. Pro tip.", "educator"),
        ("We offer CMMC services", "DM me for help. My company helps defense contractors.", "promoter"),
        ("New DFARS rule change", "Deadline announced. Effective date updated for all contractors.", "news_explainer"),
    ],
)
def test_low_prey_predators(title, body, predator_kind):
    cls = classify_post(title, body)
    intent = classify_author_intent(title, body)
    cls["author_intent"] = intent["author_intent"]
    cls["advice_giver_score"] = intent["advice_giver_score"]
    cls["advice_seeker_score"] = intent["advice_seeker_score"]
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] < DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is False


def test_topical_discussion_without_operational_need_scores_low():
    title = "Thoughts on CMMC Level 2 requirements?"
    body = "Discussion: what do you think about the new scoping guidance for defense contractors?"
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] < DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is False


def test_prey_beats_topical_fit_in_qualification():
    post = {
        "title": "Where do I start with CMMC?",
        "selftext": "Small business subcontractor. Prime contractor sent questionnaire. We're overwhelmed.",
        "subreddit": "smallbusiness",
    }
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    assert qual["prey_score"] >= DEFAULT_MIN_PREY_SCORE
    assert qual["queue_eligible"] is True

    predator_post = {
        "title": "CMMC AMA",
        "selftext": "As a consultant I advise clients. Here's my guide. Book a call.",
        "subreddit": "cmmc",
    }
    pcls = classify_post(predator_post["title"], predator_post["selftext"])
    pqual = qualify_post(predator_post, pcls)
    assert pqual["prey_score"] < qual["prey_score"]
    assert pqual["queue_eligible"] is False


def test_helpless_seeker_higher_than_consultant():
    seek = score_acquisition_probability(
        "I was tasked with CMMC",
        "What documents do I need? We can't afford this.",
        classification=classify_post("I was tasked with CMMC", "What documents do I need? We can't afford this."),
    )
    consult = score_acquisition_probability(
        "CMMC overview",
        "As a consultant, let me explain. You should do X. Pro tip.",
        classification=classify_post("CMMC overview", "As a consultant, let me explain."),
    )
    assert seek["prey_score"] > consult["prey_score"]

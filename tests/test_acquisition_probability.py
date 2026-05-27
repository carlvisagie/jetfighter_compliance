"""Acquisition probability — prey vs predator scoring (balanced sensitivity)."""
from __future__ import annotations

import pytest

from services.acquisition.acquisition_probability import (
    DEFAULT_MIN_PREY_SCORE,
    MIN_PREY_FLOOR,
    TARGET_QUEUE_MAX,
    TARGET_QUEUE_MIN,
    classify_prey_tier,
    compute_adaptive_prey_threshold,
    passes_prey_gate,
    score_acquisition_probability,
)
from services.acquisition.connectors.reddit.author_intent import classify_author_intent
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post

IDEAL_PREY_TITLE = "VERY BASIC SMALL BUSINESS QUESTION - Which CMMC level?"
IDEAL_PREY_BODY = (
    "We provide office furniture to military bases. Costs are beyond what we can afford. "
    "More confused than ever. Can anyone provide simple insight on what level we need?"
)


def test_ideal_small_business_cmmc_level_post_queued():
    cls = classify_post(IDEAL_PREY_TITLE, IDEAL_PREY_BODY)
    out = score_acquisition_probability(IDEAL_PREY_TITLE, IDEAL_PREY_BODY, classification=cls)
    assert out["prey_score"] >= DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is True
    assert out["has_operational_need"] is True
    assert out["financial_stress_score"] >= 35 or "Financial stress" in out.get("prey_reasons", [])
    post = {"title": IDEAL_PREY_TITLE, "selftext": IDEAL_PREY_BODY, "subreddit": "smallbusiness"}
    qual = qualify_post(post, cls)
    assert passes_prey_gate(qual, cls, min_prey_score=DEFAULT_MIN_PREY_SCORE)


def test_more_confused_than_ever_boosts_prey():
    cls = classify_post("CMMC help", "We are more confused than ever about what applies to us.")
    out = score_acquisition_probability("CMMC help", "We are more confused than ever about what applies to us.", classification=cls)
    assert out["confusion_density_score"] >= 35
    assert out["prey_score"] >= MIN_PREY_FLOOR


def test_financial_panic_boosts_prey():
    body = (
        "Small business — we cannot afford this. Costs are beyond what we can afford. "
        "We got quoted $80k. Where do we start?"
    )
    cls = classify_post("CMMC too expensive — help", body)
    out = score_acquisition_probability("CMMC too expensive — help", body, classification=cls)
    assert out["financial_stress_score"] >= 45
    assert out["prey_score"] >= MIN_PREY_FLOOR


def test_cannot_afford_boosts_prey():
    cls = classify_post("Help", "Small business — we can't afford CMMC compliance.")
    out = score_acquisition_probability("Help", "Small business — we can't afford CMMC compliance.", classification=cls)
    assert out["financial_stress_score"] >= 40


def test_topical_discussion_stays_low():
    title = "Thoughts on CMMC Level 2 requirements?"
    body = "Discussion: what do you think about the new scoping guidance for defense contractors?"
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] < DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is False
    assert out["topical_only_risk"] is True


@pytest.mark.parametrize(
    "title,body",
    [
        ("CMMC AMA — ask me anything", "I'm a consultant and C3PAO. Book a call."),
        ("How CMMC works", "Here's how this works. You should start with SSP. Pro tip."),
        ("We offer CMMC services", "DM me for help. My company helps defense contractors."),
    ],
)
def test_predators_rejected(title, body):
    cls = classify_post(title, body)
    intent = classify_author_intent(title, body)
    cls["author_intent"] = intent["author_intent"]
    cls["advice_giver_score"] = intent["advice_giver_score"]
    cls["advice_seeker_score"] = intent["advice_seeker_score"]
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["queue_eligible"] is False
    assert not passes_prey_gate({"prey_score": out["prey_score"], "acquisition_probability": out}, cls, min_prey_score=MIN_PREY_FLOOR)


def test_adaptive_relaxation_on_near_miss():
    candidates = [
        {"prey_score": 50, "deployable_intent": True, "low_predator": True, "has_operational_need": True},
        {"prey_score": 49, "deployable_intent": True, "low_predator": True, "has_operational_need": True},
    ]
    threshold = compute_adaptive_prey_threshold(58, candidates, learning_state={"min_prey_threshold": 58})
    assert threshold <= 58
    assert threshold >= MIN_PREY_FLOOR


def test_prey_starvation_prevention_best_candidate():
    candidates = [
        {"prey_score": 51, "deployable_intent": True, "low_predator": True, "has_operational_need": True},
    ]
    threshold = compute_adaptive_prey_threshold(58, candidates)
    assert threshold <= 51


def test_operational_burden_beats_topical_relevance():
    burden = score_acquisition_probability(
        IDEAL_PREY_TITLE,
        IDEAL_PREY_BODY,
        classification=classify_post(IDEAL_PREY_TITLE, IDEAL_PREY_BODY),
    )
    topic = score_acquisition_probability(
        "Thoughts on CMMC Level 2?",
        "Discussion about requirements in general for the industry.",
        classification=classify_post("Thoughts on CMMC Level 2?", "Discussion about requirements."),
    )
    assert burden["prey_score"] > topic["prey_score"] + 25


def test_prey_beats_topical_fit_in_qualification():
    post = {
        "title": "Where do I start with CMMC?",
        "selftext": "Small business subcontractor. Prime contractor sent questionnaire. We're overwhelmed.",
        "subreddit": "smallbusiness",
    }
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    assert qual["prey_score"] >= DEFAULT_MIN_PREY_SCORE

    predator_post = {
        "title": "CMMC AMA",
        "selftext": "As a consultant I advise clients. Here's my guide. Book a call.",
        "subreddit": "cmmc",
    }
    pcls = classify_post(predator_post["title"], predator_post["selftext"])
    pqual = qualify_post(predator_post, pcls)
    assert pqual["prey_score"] < qual["prey_score"]


def test_queue_targets_updated():
    assert TARGET_QUEUE_MIN == 8
    assert TARGET_QUEUE_MAX == 20


def test_quiet_operational_post_tier_one_or_two():
    title = "Which level applies to us?"
    body = "Prime contractor asked for SPRS score and security questionnaire. We store drawings with CUI."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_tier"] in (1, 2)
    assert out["operational_entanglement_score"] >= 35
    assert out["queue_eligible"] is True


def test_emotional_only_post_lower_tier_than_operational():
    emotional = score_acquisition_probability(
        "Help",
        "I'm overwhelmed and lost and panicking.",
        classification=classify_post("Help", "I'm overwhelmed and lost and panicking."),
    )
    operational = score_acquisition_probability(
        "Customer asked for MFA",
        "Small business subcontractor — vendor onboarding security questionnaire. What documentation is needed?",
        classification=classify_post(
            "Customer asked for MFA",
            "Small business subcontractor — vendor onboarding security questionnaire. What documentation is needed?",
        ),
    )
    assert operational["prey_score"] > emotional["prey_score"]
    assert operational["prey_tier"] <= emotional["prey_tier"]


def test_prey_tier_blocks_consultants():
    tier = classify_prey_tier(
        70,
        predator_class="consultant",
        predator_penalty=55,
        queue_eligible=False,
        topical_only=False,
        dimension_scores={},
        soft_score=50,
        has_operational_need=True,
    )
    assert tier == 5

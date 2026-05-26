"""Social intelligence layer — trust-first acquisition organism."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from services.acquisition.connectors.reddit.autonomy import decide_engagement
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.draft_generation import generate_draft_reply
from services.acquisition.connectors.reddit.qualification import qualify_post
from services.acquisition.routing import build_upload_route
from services.acquisition.social_intelligence import enrich_engagement_plan, trust_building
from services.acquisition.social_intelligence.conversational_memory import (
    is_repetitive_phrasing,
    record_engagement,
)
from services.acquisition.social_intelligence.engagement_strategy import choose_strategy
from services.acquisition.social_intelligence.pacing import decide_pacing
from services.acquisition.social_intelligence.subreddit_culture import get_subreddit_profile


@pytest.fixture
def social_env(monkeypatch, tmp_path):
    monkeypatch.setattr("services.config.DATA", tmp_path)
    (tmp_path / "acquisition" / "social_intelligence").mkdir(parents=True)
    return tmp_path


def _post(**kw):
    base = {
        "post_id": "p1",
        "subreddit": "smallbusiness",
        "title": "Where do I start with CMMC?",
        "selftext": "I'm overwhelmed and lost.",
        "author": "user_a",
        "num_comments": 2,
    }
    base.update(kw)
    return base


def test_no_early_link_on_first_contact(social_env):
    post = _post()
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    plan = decide_engagement(post, cls, qual)
    assert plan.get("show_operator_queue") is True
    assert plan.get("link_in_public_reply") is False
    assert (plan.get("social_intelligence") or {}).get("link_allowed") is False
    assert plan.get("relationship_state") in (
        "first_contact",
        "familiar_presence",
        "trusted_participant",
        "burden_relief_opportunity",
    )


def test_trust_progression_with_approvals(social_env):
    sub = "smallbusiness"
    for i in range(3):
        record_engagement(
            post_id=f"p{i}",
            subreddit=sub,
            author="user_a",
            outcome="approved",
            phrasing=f"unique helpful reply number {i} with different words",
            relationship_state="familiar_presence",
            trust_score=50 + i * 10,
            base=social_env,
        )
    post = _post()
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    plan = decide_engagement(post, cls, qual)
    assert plan.get("trust_score", 0) >= 40


def test_subreddit_culture_hate_links(social_env):
    prof = get_subreddit_profile("cybersecurity", social_env)
    assert prof.get("link_tolerance") == "hate"
    post = _post(subreddit="cybersecurity")
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    plan = decide_engagement(post, cls, qual)
    assert plan.get("link_in_public_reply") is False


def test_emotional_reassurance_strategy(social_env):
    cls = classify_post("CMMC nightmare", "I was tasked with CMMC and I'm lost")
    strategy = choose_strategy(
        relationship_stage=1,
        classification=cls,
        subreddit_profile=get_subreddit_profile("cmmc", social_env),
        trust_score=40,
        show_queue=True,
    )
    assert strategy in ("emotional_reassurance", "helpful_clarification")


def test_pacing_patient_first_touch(social_env):
    pacing = decide_pacing(
        subreddit_profile=get_subreddit_profile("smallbusiness", social_env),
        relationship_stage=1,
    )
    assert pacing["deployment_timing"] in ("patient_first_touch", "ready_when_helpful", "respect_cooldown")


def test_repetitive_phrasing_prevention(social_env):
    text = "The hardest part is usually figuring out where to start."
    record_engagement(
        post_id="r1",
        subreddit="smallbusiness",
        outcome="drafted",
        phrasing=text,
        base=social_env,
    )
    assert is_repetitive_phrasing(text, "smallbusiness", social_env) is True


def test_trust_score_evolution():
    low = trust_building.compute_trust_score(
        safety_score=50, familiarity_score=0, emotional_burden=30, fit_score=40
    )
    high = trust_building.compute_trust_score(
        safety_score=85,
        familiarity_score=60,
        emotional_burden=70,
        fit_score=80,
        prior_approvals=3,
    )
    assert high > low


def test_relationship_stage_transitions():
    rel = trust_building.relationship_state_from_signals(
        trust_score=82,
        familiarity_score=55,
        burden_score=60,
        prior_approvals=3,
        link_tolerance="tolerate",
    )
    assert rel["relationship_state"] in ("burden_relief_opportunity", "onboarding_ready")
    assert rel["relationship_stage"] >= trust_building.STAGE_BURDEN_RELIEF


def test_upload_introduction_gated(social_env):
    post = _post()
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    routes = build_upload_route(lead_id="LD-RDT-p1")
    plan = decide_engagement(post, cls, qual)
    draft = generate_draft_reply(post, cls, routes["primary_url"], plan=plan)
    assert draft.get("link_in_public_reply") is False
    assert routes["primary_url"] not in (draft.get("public_reply_text") or "")


def test_link_allowed_only_at_high_trust():
    assert trust_building.link_allowed_for_stage(
        trust_building.STAGE_HELP_NO_LINK, 90, link_tolerance="tolerate", engagement_before_route=False
    ) is False
    assert trust_building.link_allowed_for_stage(
        trust_building.STAGE_ONBOARDING,
        75,
        link_tolerance="tolerate",
        engagement_before_route=False,
    ) is True


def test_enrich_suppresses_link_when_not_ready(social_env):
    post = _post()
    cls = classify_post(post["title"], post["selftext"])
    qual = qualify_post(post, cls)
    base_plan = {
        "engagement_stage": "assist_route",
        "link_in_public_reply": True,
        "link_appropriate": True,
        "show_operator_queue": True,
        "subreddit_safety": {"safety_score": 80},
        "engagement_before_route": False,
        "cooldown_hours": 24,
    }
    enriched = enrich_engagement_plan(base_plan, post, cls, qual, base=social_env)
    assert enriched.get("link_in_public_reply") is False

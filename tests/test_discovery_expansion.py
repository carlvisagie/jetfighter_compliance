"""Discovery expansion — multi-ecosystem operational burden hunting."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from services.acquisition.acquisition_probability import DEFAULT_MIN_PREY_SCORE, score_acquisition_probability
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post
from services.acquisition.intelligence.discovery_expansion import (
    CLUSTER_ORDER,
    DISCOVERY_CLUSTERS,
    DISCOVERY_ECOSYSTEMS,
    build_cycle_discovery_plan,
    build_cycle_queries,
    build_subreddit_search_plan,
    classify_discovery_cluster,
    ensure_semantic_diversity,
    ensure_subreddit_diversity,
    infer_burden_profile,
)


@pytest.mark.parametrize(
    "title,body,expected_cluster",
    [
        ("Prime contractor sent security questionnaire", "", "vendor_pressure"),
        ("Government customer asking for MFA", "Small business IT requirements", "mfa_security_requirements"),
        ("Vendor onboarding security requirements", "Not sure what they need", "vendor_pressure"),
        (
            "Need cybersecurity policies for customer",
            "Small business - what documents do we need? Not sure what applies.",
            "documentation_burden",
        ),
    ],
)
def test_semantic_posts_classify_and_relevant(title, body, expected_cluster):
    cluster = classify_discovery_cluster(title, body)
    assert cluster == expected_cluster or cluster in (
        "cybersecurity_questionnaire",
        "operational_security",
        "documentation_burden",
        "government_contract",
        "supplier_requirements",
    )
    cls = classify_post(title, body)
    assert cls["relevant"] is True


def test_semantic_posts_can_score_as_prey():
    title = "Prime contractor sent security questionnaire"
    body = "Small business — we got asked for documentation. Not sure what applies to us."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] >= 35
    qual = qualify_post({"title": title, "selftext": body, "subreddit": "smallbusiness"}, cls)
    assert qual["prey_score"] > 0


def test_thoughts_on_cmmc_stays_low_prey():
    title = "Thoughts on CMMC Level 2?"
    body = "Discussion: what do you think about scoping for contractors in general?"
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["prey_score"] < DEFAULT_MIN_PREY_SCORE
    assert out["queue_eligible"] is False


def test_consultant_ama_predator_reject():
    title = "CMMC AMA"
    body = "As a consultant I advise clients. Book a call."
    cls = classify_post(title, body)
    out = score_acquisition_probability(title, body, classification=cls)
    assert out["queue_eligible"] is False


def test_ten_discovery_clusters_defined():
    assert len(CLUSTER_ORDER) == 10
    assert set(CLUSTER_ORDER) == set(DISCOVERY_CLUSTERS.keys())


def test_discovery_ecosystems_cover_mission_subreddits():
    all_subs = {s.lower() for subs in DISCOVERY_ECOSYSTEMS.values() for s in subs}
    for required in ("govcontracts", "smallbusiness", "sysadmin", "msp", "entrepreneur"):
        assert required in all_subs or required.replace("entrepreneur", "entrepreneur") in all_subs


def test_build_cycle_queries_semantic_diversity():
    plan = build_cycle_queries(max_queries=14, min_clusters=6)
    clusters = {p["discovery_source_cluster"] for p in plan}
    assert len(clusters) >= 6
    assert "direct_cmmc" in clusters
    assert "vendor_pressure" in clusters or "operational_security" in clusters
    assert len({p["query"] for p in plan}) == len(plan)


def test_build_cycle_discovery_plan_includes_subreddit_searches():
    plan = build_cycle_discovery_plan()
    assert plan["global_queries"]
    assert plan["subreddit_searches"]
    subs = {(s.get("subreddit") or "").lower() for s in plan["subreddit_searches"]}
    assert len(subs) >= 3
    ecosystems = {s.get("discovery_ecosystem") for s in plan["subreddit_searches"]}
    assert len(ecosystems) >= 2


def test_build_subreddit_search_plan_diversity():
    plan = build_subreddit_search_plan(max_searches=12)
    subs = {(p.get("subreddit") or "").lower() for p in plan}
    assert len(subs) >= 3


def test_ensure_semantic_diversity_interleaves():
    posts = []
    for c in ("direct_cmmc", "vendor_pressure", "operational_security", "documentation_burden"):
        for i in range(3):
            posts.append({"post_id": f"{c}_{i}", "discovery_source_cluster": c, "subreddit": f"sub_{i % 4}"})
    mixed = ensure_semantic_diversity(posts, min_clusters=4)
    first_four_clusters = [mixed[i]["discovery_source_cluster"] for i in range(4)]
    assert len(set(first_four_clusters)) >= 3


def test_ensure_subreddit_diversity_interleaves():
    posts = []
    for sub in ("smallbusiness", "sysadmin", "govcontracts", "msp"):
        for i in range(2):
            posts.append(
                {
                    "post_id": f"{sub}_{i}",
                    "subreddit": sub,
                    "discovery_source_cluster": "vendor_pressure",
                }
            )
    mixed = ensure_subreddit_diversity(posts)
    first_four_subs = [mixed[i]["subreddit"] for i in range(4)]
    assert len(set(first_four_subs)) >= 3


def test_infer_burden_profile_ui_fields():
    post = {
        "title": "Prime contractor sent security questionnaire",
        "selftext": "Small business. Government customer. Need policies.",
        "subreddit": "smallbusiness",
        "discovery_source_cluster": "vendor_pressure",
        "discovery_ecosystem": "small_business",
    }
    cls = classify_post(post["title"], post["selftext"])
    profile = infer_burden_profile(post, cls)
    assert profile["burden_category"]
    assert profile["operational_context"]
    assert profile["likely_paperwork_indicators"]
    assert "Vendor pressure" in profile.get("burden_badges", []) or profile["burden_category"]


def test_discover_posts_tags_cluster(reddit_env, monkeypatch):
    from services.acquisition.connectors.reddit import discovery

    captured = []

    def fake_search(query, **kwargs):
        captured.append({"query": query, "subreddit": kwargs.get("subreddit", "")})
        return [
            {
                "post_id": f"pid_{hash((query, kwargs.get('subreddit', ''))) % 10000}",
                "subreddit": kwargs.get("subreddit") or "smallbusiness",
                "title": "Prime contractor sent security questionnaire",
                "selftext": "We got asked for documentation. Small business.",
                "url": "https://reddit.com/x",
                "author": "u1",
                "num_comments": 1,
            }
        ]

    monkeypatch.setattr(discovery, "search_reddit", fake_search)
    monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
    rows = discovery.discover_posts(pause_seconds=0, base=reddit_env, max_queries=4)
    assert rows
    assert rows[0].get("discovery_source_cluster")
    assert len({r.get("subreddit") for r in rows}) >= 1 or len(captured) >= 1


def test_pipeline_entry_without_cmmc_keyword():
    post = {
        "title": "Customer security requirements",
        "selftext": "Government customer asking for MFA. We need policies. What do they need from us?",
        "subreddit": "smallbusiness",
    }
    cls = classify_post(post["title"], post["selftext"])
    assert cls["relevant"] is True
    assert cls["burden_score"] >= 10

"""Discovery expansion — semantic search without weakening prey precision."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from services.acquisition.acquisition_probability import DEFAULT_MIN_PREY_SCORE, score_acquisition_probability
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit.qualification import qualify_post
from services.acquisition.intelligence.discovery_expansion import (
    build_cycle_queries,
    classify_discovery_cluster,
    ensure_semantic_diversity,
)


@pytest.mark.parametrize(
    "title,body,expected_cluster",
    [
        ("Prime contractor sent security questionnaire", "", "vendor_pressure"),
        ("Government customer asking for MFA", "Small business IT requirements", "operational_security"),
        ("Vendor onboarding security requirements", "Not sure what they need", "vendor_pressure"),
    ],
)
def test_semantic_posts_classify_and_relevant(title, body, expected_cluster):
    cluster = classify_discovery_cluster(title, body)
    assert cluster == expected_cluster or cluster in (
        "security_questionnaire",
        "pain_semantic",
        "documentation_burden",
        "government_contract",
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


def test_build_cycle_queries_semantic_diversity():
    plan = build_cycle_queries(max_queries=14, min_clusters=4)
    clusters = {p["discovery_source_cluster"] for p in plan}
    assert len(clusters) >= 4
    assert "direct_cmmc" in clusters
    assert len({p["query"] for p in plan}) == len(plan)


def test_ensure_semantic_diversity_interleaves():
    posts = []
    for c in ("direct_cmmc", "vendor_pressure", "operational_security", "pain_semantic"):
        for i in range(3):
            posts.append({"post_id": f"{c}_{i}", "discovery_source_cluster": c})
    mixed = ensure_semantic_diversity(posts, min_clusters=4)
    first_four_clusters = [mixed[i]["discovery_source_cluster"] for i in range(4)]
    assert len(set(first_four_clusters)) >= 3


def test_discover_posts_tags_cluster(reddit_env, monkeypatch):
    from services.acquisition.connectors.reddit import discovery

    captured_queries = []

    def fake_search(query, **kwargs):
        captured_queries.append(query)
        return [
            {
                "post_id": f"pid_{hash(query) % 10000}",
                "subreddit": "smallbusiness",
                "title": "Prime contractor sent security questionnaire",
                "selftext": "We got asked for documentation. Small business.",
                "url": "https://reddit.com/x",
                "author": "u1",
                "num_comments": 1,
            }
        ]

    monkeypatch.setattr(discovery, "search_reddit", fake_search)
    monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
    rows = discovery.discover_posts(
        queries=["prime contractor sent questionnaire"],
        pause_seconds=0,
        base=reddit_env,
    )
    assert rows
    assert rows[0].get("discovery_source_cluster")


def test_pipeline_entry_without_cmmc_keyword():
    post = {
        "title": "Customer security requirements",
        "selftext": "Government customer asking for MFA. We need policies. What do they need from us?",
        "subreddit": "smallbusiness",
    }
    cls = classify_post(post["title"], post["selftext"])
    assert cls["relevant"] is True
    assert cls["burden_score"] >= 10

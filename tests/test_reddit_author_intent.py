"""Reddit author intent — advice-seekers vs advice-givers."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from services.acquisition.connectors.reddit.author_intent import classify_author_intent
from services.acquisition.connectors.reddit.classifier import classify_post
from services.acquisition.connectors.reddit import run_reddit_acquisition_cycle


@pytest.mark.parametrize(
    "title,body,expected",
    [
        ("Where do I start with CMMC?", "", "SEEKING_HELP"),
        ("Can someone explain DFARS?", "We are a small supplier.", "SEEKING_HELP"),
        ("CMMC nightmare", "I was tasked with CMMC and I'm lost", "VENTING_OR_OVERWHELMED"),
        ("Here is how CMMC works", "The answer is you need SSP first.", "GIVING_ADVICE"),
        ("CMMC tips", "As a consultant, I recommend you start with scoping.", "GIVING_ADVICE"),
        ("We offer CMMC help", "Book a call with our team.", "PROMOTING_SERVICE"),
        ("New CMMC rule change", "Deadline announced for defense contractors.", "DISCUSSING_NEWS"),
    ],
)
def test_author_intent_classification(title, body, expected):
    out = classify_author_intent(title, body)
    assert out["author_intent"] == expected, out


def test_advice_seekers_score_above_givers_for_help_posts():
    seek = classify_author_intent("Where do I start with CMMC?", "I'm confused and need help")
    give = classify_author_intent("How CMMC works", "You should do X. In my experience as a consultant...")
    assert seek["advice_seeker_score"] > seek["advice_giver_score"]
    assert give["advice_giver_score"] > give["advice_seeker_score"]


def test_deployable_only_for_seeking_and_venting():
    assert classify_author_intent("Help with CMMC", "where do I start?")["deployable_engagement"] is True
    assert classify_author_intent("Overwhelmed", "we're overwhelmed by paperwork")["deployable_engagement"] is True
    assert classify_author_intent("Guide", "Here's how this works for everyone")["deployable_engagement"] is False


def test_classify_post_merges_intent():
    cls = classify_post("Where do I start with NIST 800-171?", "My boss asked me")
    assert cls["author_intent"] == "SEEKING_HELP"
    assert "advice_seeker_score" in cls


def test_cycle_skips_advice_giver(reddit_env, monkeypatch):
    def fake_listing(post_id="giver1", title="CMMC guide", selftext="You should start here. As a consultant I advise clients."):
        return {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": post_id,
                            "subreddit": "cmmc",
                            "title": title,
                            "selftext": selftext,
                            "permalink": "/r/cmmc/comments/giver1/x/",
                            "author": "expert",
                            "created_utc": 1710000000,
                            "num_comments": 10,
                        },
                    }
                ]
            }
        }

    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", side_effect=lambda url: fake_listing()):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        monkeypatch.setattr(
            "services.acquisition.connectors.reddit.discovery.load_discovered_post_ids",
            lambda base=None: set(),
        )
        out = run_reddit_acquisition_cycle(
            queries=["CMMC"],
            max_posts=3,
            min_fit_score=20,
            pause_seconds=0,
            base=reddit_env,
        )
    assert out["queued_for_operator"] == 0
    assert out["organism_auto_skipped"] >= 1


def test_cycle_queues_advice_seeker(reddit_env, monkeypatch):
    def fake_listing():
        return {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "seeker1",
                            "subreddit": "smallbusiness",
                            "title": "Where do I start with CMMC?",
                            "selftext": "Can someone explain? I was tasked with this and I'm lost.",
                            "permalink": "/r/smallbusiness/comments/seeker1/x/",
                            "author": "u1",
                            "created_utc": 1710000000,
                            "num_comments": 2,
                        },
                    }
                ]
            }
        }

    with patch("services.acquisition.connectors.reddit.discovery._fetch_json", side_effect=lambda url: fake_listing()):
        monkeypatch.setattr("services.acquisition.connectors.reddit.discovery.time.sleep", lambda _: None)
        monkeypatch.setattr(
            "services.acquisition.connectors.reddit.discovery.load_discovered_post_ids",
            lambda base=None: set(),
        )
        out = run_reddit_acquisition_cycle(
            queries=["CMMC"],
            max_posts=3,
            min_fit_score=20,
            pause_seconds=0,
            base=reddit_env,
        )
    assert out["queued_for_operator"] >= 1

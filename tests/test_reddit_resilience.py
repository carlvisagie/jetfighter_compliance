"""Reddit acquisition production resilience — malformed posts, cluster isolation, telemetry."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import services.acquisition.connectors.reddit.discovery as reddit_discovery
from services.acquisition.connectors.reddit.discovery import _parse_listing
from services.acquisition.connectors.reddit.resilience import (
    ERROR_RATE_LIMITED,
    normalize_post,
    sanitize_telemetry_metadata,
)


def test_normalize_post_missing_fields():
    p = normalize_post({})
    assert p["post_id"] == ""
    assert p["subreddit"] == ""
    assert p["discovery_source_cluster"] == "operational_security"


def test_parse_listing_skips_malformed_children():
    data = {
        "data": {
            "children": [
                {"kind": "t3", "data": {"id": "abc123", "title": "help", "subreddit": "smallbusiness"}},
                {"kind": "t3", "data": None},
                "not-a-dict",
                {"kind": "t1", "data": {"id": "cmt"}},
            ]
        }
    }
    rows = _parse_listing(data)
    assert len(rows) == 1
    assert rows[0]["post_id"] == "abc123"


def test_sanitize_telemetry_strips_deep_plan():
    meta = sanitize_telemetry_metadata({"plan": {"engagement_stage": "observe", "nested": {"x": 1}}})
    assert "plan" in meta


def test_discover_posts_continues_after_cluster_failure(reddit_env, monkeypatch):
    calls = {"n": 0}

    def flaky_fetch(url, timeout=25):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("simulated")
        fake = {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "okpost1",
                            "title": "vendor questionnaire help",
                            "subreddit": "smallbusiness",
                            "selftext": "customer sent security form",
                        },
                    }
                ]
            }
        }
        return fake, None

    monkeypatch.setattr(reddit_discovery, "load_discovered_post_ids", lambda base=None: set())
    monkeypatch.setattr(reddit_discovery.time, "sleep", lambda _: None)
    with patch.object(reddit_discovery, "_fetch_json", side_effect=flaky_fetch):
        rows = reddit_discovery.discover_posts(
            queries=["security questionnaire", "CMMC help"],
            pause_seconds=0,
            base=reddit_env,
        )
    assert len(rows) >= 1
    diag = getattr(reddit_discovery.discover_posts, "last_diagnostics", {})
    assert diag.get("cluster_errors")


def test_rate_limit_recorded(reddit_env, monkeypatch):
    monkeypatch.setattr(reddit_discovery, "load_discovered_post_ids", lambda base=None: set())
    monkeypatch.setattr(reddit_discovery.time, "sleep", lambda _: None)
    with patch.object(
        reddit_discovery,
        "_fetch_json",
        return_value=(None, ERROR_RATE_LIMITED),
    ):
        rows = reddit_discovery.discover_posts(queries=["test query"], pause_seconds=0, base=reddit_env)
    assert rows == []
    assert reddit_discovery.discover_posts.last_diagnostics.get("rate_limited") is True

"""Subreddit culture profiles — links, tone, moderation learning."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .paths import SUBREDDIT_PROFILES_JSON, ensure_social_intel_dir
from services.defensive_wiring import safe_write_text, safe_write_json

DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "smallbusiness": {
        "link_tolerance": "cautious",
        "prefers_concise": True,
        "prefers_long_form": False,
        "moderation_strictness": "medium",
        "trust_via_helpfulness": True,
    },
    "cybersecurity": {
        "link_tolerance": "hate",
        "prefers_concise": False,
        "prefers_long_form": True,
        "moderation_strictness": "high",
        "trust_via_helpfulness": True,
    },
    "cmmc": {
        "link_tolerance": "cautious",
        "prefers_concise": False,
        "prefers_long_form": True,
        "moderation_strictness": "medium",
        "trust_via_helpfulness": True,
    },
    "nist800171": {
        "link_tolerance": "cautious",
        "prefers_concise": False,
        "prefers_long_form": True,
        "moderation_strictness": "medium",
        "trust_via_helpfulness": True,
    },
    "govcontracts": {
        "link_tolerance": "tolerate",
        "prefers_concise": True,
        "prefers_long_form": False,
        "moderation_strictness": "low",
        "trust_via_helpfulness": True,
    },
    "defensecontracting": {
        "link_tolerance": "tolerate",
        "prefers_concise": True,
        "prefers_long_form": False,
        "moderation_strictness": "low",
        "trust_via_helpfulness": True,
    },
    "manufacturing": {
        "link_tolerance": "cautious",
        "prefers_concise": True,
        "prefers_long_form": False,
        "moderation_strictness": "medium",
        "trust_via_helpfulness": True,
    },
    "entrepreneur": {
        "link_tolerance": "cautious",
        "prefers_concise": True,
        "prefers_long_form": False,
        "moderation_strictness": "medium",
        "trust_via_helpfulness": True,
    },
    "_default": {
        "link_tolerance": "cautious",
        "prefers_concise": True,
        "prefers_long_form": False,
        "moderation_strictness": "medium",
        "trust_via_helpfulness": True,
        "removals": 0,
        "ignores": 0,
        "positive_engagements": 0,
    },
}


def load_profiles(base: Optional[Any] = None) -> Dict[str, Dict[str, Any]]:
    path = ensure_social_intel_dir(base) / SUBREDDIT_PROFILES_JSON
    merged = {k: dict(v) for k, v in DEFAULT_PROFILES.items()}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for sub, prof in data.items():
                    if isinstance(prof, dict):
                        base_prof = merged.get(sub, dict(merged["_default"]))
                        base_prof.update(prof)
                        merged[sub] = base_prof
        except json.JSONDecodeError:
            pass
    return merged


def save_profiles(profiles: Dict[str, Dict[str, Any]], base: Optional[Any] = None) -> None:
    path = ensure_social_intel_dir(base) / SUBREDDIT_PROFILES_JSON
    out = {k: v for k, v in profiles.items() if not k.startswith("_")}
    safe_write_json(

        path,

        out,

        component="subreddit_culture",

        context="culture state"

    )


def get_subreddit_profile(subreddit: str, base: Optional[Any] = None) -> Dict[str, Any]:
    sub = (subreddit or "").lower().strip()
    profiles = load_profiles(base)
    prof = dict(profiles.get(sub, profiles.get("_default", DEFAULT_PROFILES["_default"])))
    prof["subreddit"] = sub
    return prof


def record_subreddit_outcome(
    subreddit: str,
    outcome: str,
    *,
    base: Optional[Any] = None,
) -> Dict[str, Any]:
    """Learn from moderation, ignores, positive engagement."""
    sub = (subreddit or "").lower().strip()
    profiles = load_profiles(base)
    prof = get_subreddit_profile(sub, base)
    if outcome in ("moderation_removed", "operator_denied"):
        prof["removals"] = int(prof.get("removals", 0)) + (1 if outcome == "moderation_removed" else 0)
        prof["ignores"] = int(prof.get("ignores", 0)) + 1
        if prof["ignores"] >= 3 and prof.get("link_tolerance") != "hate":
            prof["link_tolerance"] = "cautious"
        if prof["removals"] >= 2:
            prof["link_tolerance"] = "hate"
    elif outcome in ("operator_approved", "uploads_completed", "positive_reply"):
        prof["positive_engagements"] = int(prof.get("positive_engagements", 0)) + 1
        if prof["positive_engagements"] >= 3 and prof.get("link_tolerance") == "hate":
            prof["link_tolerance"] = "cautious"
    profiles[sub] = prof
    save_profiles(profiles, base)
    return prof

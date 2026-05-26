"""Data paths for social intelligence layer."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

SUBREDDIT_PROFILES_JSON = "subreddit_behavior_profiles.json"
CONVERSATION_MEMORY_JSONL = "conversation_memory.jsonl"
SOCIAL_TELEMETRY_JSONL = "social_telemetry.jsonl"


def _data_root() -> Path:
    from ...config import DATA

    return DATA


def social_intel_dir(base: Optional[Path] = None) -> Path:
    if base is None:
        return _data_root() / "acquisition" / "social_intelligence"
    p = Path(base)
    if p.name == "social_intelligence":
        return p
    return p / "acquisition" / "social_intelligence"


def ensure_social_intel_dir(base: Optional[Path] = None) -> Path:
    d = social_intel_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    return d

"""Data paths for Reddit acquisition connector."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

DISCOVERED_POSTS_JSONL = "discovered_posts.jsonl"
DRAFT_REPLIES_JSONL = "draft_replies.jsonl"
APPROVED_REPLIES_JSONL = "approved_replies.jsonl"
IGNORED_POSTS_JSONL = "ignored_posts.jsonl"
REDDIT_TELEMETRY_JSONL = "telemetry.jsonl"


def _data_root() -> Path:
    from ....config import DATA

    return DATA


def reddit_dir(base: Optional[Path] = None) -> Path:
    if base is None:
        return _data_root() / "acquisition" / "reddit"
    p = Path(base)
    return p if p.name == "reddit" else p / "acquisition" / "reddit"


def ensure_reddit_dir(base: Optional[Path] = None) -> Path:
    d = reddit_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    return d

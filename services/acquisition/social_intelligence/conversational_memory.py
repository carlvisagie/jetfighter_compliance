"""Conversational memory — prior touches, repetition prevention."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from ..models import utc_now
from .paths import CONVERSATION_MEMORY_JSONL, ensure_social_intel_dir


def _memory_path(base: Optional[Any] = None):
    return ensure_social_intel_dir(base) / CONVERSATION_MEMORY_JSONL


def load_memory_rows(base: Optional[Any] = None, limit: int = 500) -> List[Dict[str, Any]]:
    path = _memory_path(base)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def prior_engagements(
    *,
    author: str = "",
    subreddit: str = "",
    post_id: str = "",
    base: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    author = (author or "").lower()
    sub = (subreddit or "").lower()
    rows = load_memory_rows(base)
    out = []
    for r in rows:
        if post_id and r.get("post_id") == post_id:
            out.append(r)
        elif author and r.get("author", "").lower() == author:
            out.append(r)
        elif sub and r.get("subreddit", "").lower() == sub and not author:
            out.append(r)
    return out


def count_prior_touches(
    *,
    author: str = "",
    subreddit: str = "",
    base: Optional[Any] = None,
) -> Dict[str, int]:
    rows = prior_engagements(author=author, subreddit=subreddit, base=base)
    return {
        "total": len(rows),
        "approved": sum(1 for r in rows if r.get("outcome") == "approved"),
        "denied": sum(1 for r in rows if r.get("outcome") == "denied"),
        "removed": sum(1 for r in rows if r.get("outcome") == "moderation_removed"),
    }


def phrasing_fingerprint(text: str) -> str:
    normalized = " ".join((text or "").lower().split())[:500]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def is_repetitive_phrasing(text: str, subreddit: str = "", base: Optional[Any] = None) -> bool:
    fp = phrasing_fingerprint(text)
    sub = (subreddit or "").lower()
    for r in load_memory_rows(base, limit=200):
        if r.get("phrasing_fp") == fp and (not sub or r.get("subreddit", "").lower() == sub):
            return True
    return False


def record_engagement(
    *,
    post_id: str,
    subreddit: str,
    author: str = "",
    outcome: str = "drafted",
    phrasing: str = "",
    relationship_state: str = "",
    trust_score: int = 0,
    strategy: str = "",
    base: Optional[Any] = None,
) -> Dict[str, Any]:
    rec = {
        "post_id": post_id,
        "subreddit": (subreddit or "").lower(),
        "author": author,
        "outcome": outcome,
        "phrasing_fp": phrasing_fingerprint(phrasing) if phrasing else "",
        "relationship_state": relationship_state,
        "trust_score": trust_score,
        "strategy": strategy,
        "when_utc": utc_now(),
    }
    path = _memory_path(base)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def over_engagement_risk(author: str, subreddit: str, base: Optional[Any] = None) -> bool:
    """Avoid unnatural cadence — same author too often."""
    touches = count_prior_touches(author=author, subreddit=subreddit, base=base)
    return touches["total"] >= 3 and touches["approved"] == 0

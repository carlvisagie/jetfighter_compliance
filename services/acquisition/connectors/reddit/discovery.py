"""Discover public Reddit discussions — read-only JSON endpoints, respectful rate limits."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from ...models import utc_now
from .paths import DISCOVERED_POSTS_JSONL, ensure_reddit_dir

logger = logging.getLogger(__name__)

CONNECTOR_ID = "reddit_live"
USER_AGENT = "KeepYourContracts:AcquisitionResearch/1.0 (lawful public burden detection; +https://compliance.keepyourcontracts.com)"

# Public search queries aligned to compliance burden (mission list)
DEFAULT_SEARCH_QUERIES = [
    "CMMC confusion",
    "DFARS confusion",
    "NIST 800-171 help",
    "security questionnaire overwhelmed",
    "compliance documentation stress",
    "where do I start compliance",
    "what paperwork CMMC",
    "small business compliance defense",
    "prime contractor requirements",
    "vendor security assessment",
    "customer security questionnaire",
    "audit anxiety compliance",
]

# Subreddits where burden discussions commonly appear
DEFAULT_SUBREDDITS = [
    "smallbusiness",
    "cybersecurity",
    "CMMC",
    "NIST800171",
    "govcontracts",
    "defensecontracting",
]

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
REDDIT_SUBREDDIT_SEARCH_URL = "https://www.reddit.com/r/{subreddit}/search.json"

MIN_SECONDS_BETWEEN_REQUESTS = 2.0


def _fetch_json(url: str, timeout: int = 25) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning("Reddit fetch failed %s: %s", url[:80], e)
        return None


def _parse_listing(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    children = (data.get("data") or {}).get("children") or []
    for child in children:
        if child.get("kind") != "t3":
            continue
        d = child.get("data") or {}
        post_id = d.get("id") or ""
        if not post_id:
            continue
        permalink = d.get("permalink") or ""
        if permalink and not permalink.startswith("http"):
            permalink = "https://www.reddit.com" + permalink
        posts.append(
            {
                "post_id": post_id,
                "subreddit": (d.get("subreddit") or "").strip(),
                "title": (d.get("title") or "").strip(),
                "selftext": (d.get("selftext") or "").strip()[:4000],
                "url": permalink or (d.get("url") or ""),
                "author": (d.get("author") or "[deleted]"),
                "created_utc": d.get("created_utc"),
                "num_comments": d.get("num_comments", 0),
                "source": "reddit_public_json",
            }
        )
    return posts


def search_reddit(
    query: str,
    *,
    subreddit: str = "",
    limit: int = 15,
    sort: str = "new",
) -> List[Dict[str, Any]]:
    """Single public search — respects rate limits via caller pacing."""
    q = urllib.parse.quote(query)
    if subreddit:
        url = (
            REDDIT_SUBREDDIT_SEARCH_URL.format(subreddit=urllib.parse.quote(subreddit))
            + f"?q={q}&restrict_sr=1&sort={sort}&limit={min(limit, 25)}"
        )
    else:
        url = f"{REDDIT_SEARCH_URL}?q={q}&sort={sort}&limit={min(limit, 25)}"
    data = _fetch_json(url)
    if not data:
        return []
    return _parse_listing(data)


def load_discovered_post_ids(base: Optional[Any] = None) -> set:
    path = ensure_reddit_dir(base) / DISCOVERED_POSTS_JSONL
    ids: set = set()
    if not path.is_file():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            pid = row.get("post_id")
            if pid:
                ids.add(pid)
        except json.JSONDecodeError:
            continue
    return ids


def append_discovered_post(record: Dict[str, Any], base: Optional[Any] = None) -> None:
    path = ensure_reddit_dir(base) / DISCOVERED_POSTS_JSONL
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def discover_posts(
    *,
    queries: Optional[List[str]] = None,
    subreddits: Optional[List[str]] = None,
    limit_per_query: int = 10,
    pause_seconds: float = MIN_SECONDS_BETWEEN_REQUESTS,
    base: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Run bounded public discovery. Caller processes/classifies results.
    """
    queries = queries or list(DEFAULT_SEARCH_QUERIES)
    subreddits = subreddits or []
    seen_ids = load_discovered_post_ids(base)
    seen_ids_run: set = set()
    out: List[Dict[str, Any]] = []

    def _collect(batch: List[Dict[str, Any]], query: str, sub: str = "") -> None:
        for post in batch:
            pid = post.get("post_id")
            if not pid or pid in seen_ids or pid in seen_ids_run:
                continue
            seen_ids_run.add(pid)
            post["search_query"] = query
            post["search_subreddit"] = sub
            post["discovered_utc"] = utc_now()
            out.append(post)

    for q in queries[:12]:
        batch = search_reddit(q, limit=limit_per_query)
        _collect(batch, q)
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    for sub in (subreddits or DEFAULT_SUBREDDITS)[:6]:
        for q in ["CMMC", "compliance paperwork", "security questionnaire"][:2]:
            batch = search_reddit(q, subreddit=sub, limit=8)
            _collect(batch, q, sub)
            if pause_seconds > 0:
                time.sleep(pause_seconds)

    return out

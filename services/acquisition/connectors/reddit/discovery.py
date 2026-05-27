"""Discover public Reddit discussions — multi-ecosystem operational burden hunting."""

from __future__ import annotations



import json

import logging

import os

import time

import urllib.error

import urllib.parse

import urllib.request

from typing import Any, Dict, List, Optional, Tuple



from ...intelligence.discovery_expansion import (

    all_ecosystem_subreddits,

    all_expanded_queries,

    apply_post_cluster_metadata,

    build_cycle_discovery_plan,

    classify_discovery_ecosystem,

    ensure_subreddit_diversity,

)

from ...models import utc_now

from .paths import DISCOVERED_POSTS_JSONL, ensure_reddit_dir

from .resilience import ERROR_RATE_LIMITED, ERROR_TIME_BUDGET, log_phase_failure, normalize_post



logger = logging.getLogger(__name__)



CONNECTOR_ID = "reddit_live"

USER_AGENT = "KeepYourContracts:AcquisitionResearch/1.0 (lawful public burden detection; +https://compliance.keepyourcontracts.com)"



DEFAULT_SEARCH_QUERIES = list(all_expanded_queries())

DEFAULT_SUBREDDITS = list(all_ecosystem_subreddits())



REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"

REDDIT_SUBREDDIT_SEARCH_URL = "https://www.reddit.com/r/{subreddit}/search.json"



MIN_SECONDS_BETWEEN_REQUESTS = 2.0



DEFAULT_DISCOVERY_BUDGET_SEC = float(os.getenv("ACQUISITION_DISCOVERY_BUDGET_SEC", "50"))





def _fetch_json(url: str, timeout: int = 25) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:

    """Returns (data, error_code). error_code set on rate limit or hard fetch failure."""

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:

        with urllib.request.urlopen(req, timeout=timeout) as resp:

            if resp.status == 429:

                return None, ERROR_RATE_LIMITED

            if resp.status != 200:

                return None, None

            return json.loads(resp.read().decode("utf-8", errors="replace")), None

    except urllib.error.HTTPError as e:

        if e.code == 429:

            logger.warning("Reddit rate limited %s", url[:80])

            return None, ERROR_RATE_LIMITED

        logger.warning("Reddit HTTP %s %s: %s", e.code, url[:80], e)

        return None, None

    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:

        logger.warning("Reddit fetch failed %s: %s", url[:80], e)

        return None, None





def _parse_listing(data: Dict[str, Any]) -> List[Dict[str, Any]]:

    posts: List[Dict[str, Any]] = []

    try:

        children = (data.get("data") or {}).get("children") or []

    except (AttributeError, TypeError):

        return posts

    for child in children:

        try:

            if not isinstance(child, dict) or child.get("kind") != "t3":

                continue

            d = child.get("data") or {}

            if not isinstance(d, dict):

                continue

            post_id = str(d.get("id") or "").strip()

            if not post_id:

                continue

            permalink = str(d.get("permalink") or "")

            if permalink and not permalink.startswith("http"):

                permalink = "https://www.reddit.com" + permalink

            raw = {

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

            posts.append(normalize_post(raw))

        except Exception as e:

            log_phase_failure("reddit_parse", e)

            continue

    return posts





def search_reddit(

    query: str,

    *,

    subreddit: str = "",

    limit: int = 15,

    sort: str = "new",

) -> Tuple[List[Dict[str, Any]], Optional[str]]:

    """Search Reddit; returns (posts, error_code)."""

    q = urllib.parse.quote(str(query or ""))

    if subreddit:

        url = (

            REDDIT_SUBREDDIT_SEARCH_URL.format(subreddit=urllib.parse.quote(str(subreddit)))

            + f"?q={q}&restrict_sr=1&sort={sort}&limit={min(limit, 25)}"

        )

    else:

        url = f"{REDDIT_SEARCH_URL}?q={q}&sort={sort}&limit={min(limit, 25)}"

    data, err = _fetch_json(url)

    if err:

        return [], err

    if not data:

        return [], None

    return _parse_listing(data), None





def load_discovered_post_ids(base: Optional[Any] = None) -> set:

    path = ensure_reddit_dir(base) / DISCOVERED_POSTS_JSONL

    ids: set = set()

    if not path.is_file():

        return ids

    for line in path.read_text(encoding="utf-8").splitlines():

        if line.strip():

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

    limit_per_query: int = 6,

    pause_seconds: float = MIN_SECONDS_BETWEEN_REQUESTS,

    learning_state: Optional[Dict[str, Any]] = None,

    max_queries: Optional[int] = None,

    founding_beta_broad: bool = False,

    time_budget_sec: Optional[float] = None,

    base: Optional[Any] = None,

) -> List[Dict[str, Any]]:

    """

    Multi-ecosystem discovery: global + subreddit searches, cluster/subreddit diversity.

    Prey filters apply downstream — this widens hunting territory only.

    """

    diagnostics: Dict[str, Any] = {

        "cluster_errors": [],

        "clusters_attempted": 0,

        "clusters_succeeded": 0,

        "rate_limited": False,

        "time_budget_hit": False,

    }



    if queries:

        plan = {

            "global_queries": [{"query": q, "discovery_source_cluster": "custom"} for q in queries],

            "subreddit_searches": [],

        }

        if subreddits:

            for sub in subreddits[:8]:

                plan["subreddit_searches"].append(

                    {

                        "subreddit": sub,

                        "query": "security questionnaire",

                        "discovery_source_cluster": "cybersecurity_questionnaire",

                        "discovery_ecosystem": "custom",

                    }

                )

    else:

        try:

            if founding_beta_broad:

                from ...intelligence.discovery_expansion import build_founding_beta_discovery_plan



                plan = build_founding_beta_discovery_plan(learning_state=learning_state)

                limit_per_query = max(limit_per_query, 10)

            else:

                plan = build_cycle_discovery_plan(learning_state=learning_state)

        except Exception as e:

            code, detail = log_phase_failure("discovery", e)

            diagnostics["cluster_errors"].append(

                {"cluster": "plan_build", "error_code": code, "detail": detail}

            )

            plan = {"global_queries": [], "subreddit_searches": []}

        if max_queries:

            plan["global_queries"] = (plan.get("global_queries") or [])[:max_queries]



    budget = time_budget_sec if time_budget_sec is not None else DEFAULT_DISCOVERY_BUDGET_SEC

    started = time.monotonic()



    seen_ids = load_discovered_post_ids(base)

    seen_run: set = set()

    out: List[Dict[str, Any]] = []



    def _collect(

        batch: List[Dict[str, Any]],

        query: str,

        cluster: str,

        sub: str = "",

        ecosystem: str = "",

    ) -> None:

        for post in batch:

            try:

                post = normalize_post(post)

                pid = post.get("post_id")

                if not pid or pid in seen_ids or pid in seen_run:

                    continue

                seen_run.add(pid)

                post["search_query"] = query

                post["search_subreddit"] = sub

                post["discovery_source_cluster"] = cluster or "operational_security"

                if not post.get("discovery_ecosystem"):

                    post["discovery_ecosystem"] = ecosystem or classify_discovery_ecosystem(

                        post.get("subreddit", "")

                    )

                post["discovered_utc"] = utc_now()

                try:

                    apply_post_cluster_metadata(post)

                except Exception as e:

                    log_phase_failure("discovery", e, post_id=pid)

                out.append(post)

            except Exception as e:

                log_phase_failure("reddit_parse", e)



    def _run_search(item: Dict[str, Any], *, subreddit: str = "") -> None:

        nonlocal diagnostics

        if time.monotonic() - started > budget:

            diagnostics["time_budget_hit"] = True

            diagnostics["cluster_errors"].append(

                {

                    "cluster": item.get("discovery_source_cluster", "unknown"),

                    "subreddit": subreddit or item.get("subreddit", ""),

                    "query": item.get("query", ""),

                    "error_code": ERROR_TIME_BUDGET,

                    "detail": f"Discovery stopped after {budget:.0f}s budget",

                }

            )

            return

        cluster = str(item.get("discovery_source_cluster") or "operational_security")

        query = str(item.get("query") or "")

        diagnostics["clusters_attempted"] += 1

        try:

            raw = search_reddit(
                query,
                subreddit=subreddit,
                limit=limit_per_query,
            )
            if isinstance(raw, tuple):
                batch, err = raw
            else:
                batch, err = raw or [], None

            if err == ERROR_RATE_LIMITED:

                diagnostics["rate_limited"] = True

                diagnostics["cluster_errors"].append(

                    {

                        "cluster": cluster,

                        "subreddit": subreddit,

                        "query": query,

                        "error_code": ERROR_RATE_LIMITED,

                        "detail": "Reddit returned HTTP 429",

                    }

                )

                return

            eco = str(item.get("discovery_ecosystem") or "")

            _collect(batch, query, cluster, subreddit, eco)

            diagnostics["clusters_succeeded"] += 1

        except Exception as e:

            code, detail = log_phase_failure("discovery", e, cluster=cluster, query=query)

            diagnostics["cluster_errors"].append(

                {

                    "cluster": cluster,

                    "subreddit": subreddit,

                    "query": query,

                    "error_code": code,

                    "detail": detail,

                }

            )

        if pause_seconds > 0:

            time.sleep(pause_seconds)



    for item in plan.get("global_queries", []):

        if diagnostics.get("time_budget_hit"):

            break

        _run_search(item)



    for item in plan.get("subreddit_searches", []):

        if diagnostics.get("time_budget_hit"):

            break

        sub = str(item.get("subreddit") or "")

        _run_search(item, subreddit=sub)



    try:

        diversified = ensure_subreddit_diversity(out)

    except Exception as e:

        log_phase_failure("discovery", e)

        diversified = out



    discover_posts.last_diagnostics = diagnostics  # type: ignore[attr-defined]

    return diversified



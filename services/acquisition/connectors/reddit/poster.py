"""Reddit autonomous posting via OAuth2 — comments/replies only, no self-posts.

Uses Reddit OAuth2 password grant (script app type) — requires:
  REDDIT_CLIENT_ID    — from reddit.com/prefs/apps (script app)
  REDDIT_CLIENT_SECRET
  REDDIT_USERNAME     — the account to post from
  REDDIT_PASSWORD

Rate limiting and safety gates are enforced here, not upstream.
The autonomy module decides whether to post — this module does the actual HTTP call.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_TOKEN_CACHE: Dict[str, Any] = {}

REDDIT_USER_AGENT = (
    "KeepYourContracts:ComplianceOutreach/1.0 "
    "(autonomous compliance helper bot; +https://compliance.keepyourcontracts.com)"
)

# Hard rate limits — never exceed these regardless of organism decision
MAX_COMMENTS_PER_HOUR = 3
MAX_COMMENTS_PER_DAY = 12
MAX_COMMENTS_PER_SUBREDDIT_PER_DAY = 2


def _reddit_credentials() -> Optional[Dict[str, str]]:
    client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
    username = os.getenv("REDDIT_USERNAME", "").strip()
    password = os.getenv("REDDIT_PASSWORD", "").strip()
    if not (client_id and client_secret and username and password):
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password,
    }


def reddit_configured() -> bool:
    return _reddit_credentials() is not None


def _get_access_token(creds: Dict[str, str]) -> Optional[str]:
    """Fetch/cache OAuth2 bearer token via password grant."""
    now = time.time()
    cached = _TOKEN_CACHE.get("token")
    expires = _TOKEN_CACHE.get("expires_at", 0)
    if cached and now < expires - 60:
        return cached

    auth_str = f"{creds['client_id']}:{creds['client_secret']}"
    auth_b64 = __import__("base64").b64encode(auth_str.encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "username": creds["username"],
        "password": creds["password"],
    }).encode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=data,
        headers={
            "Authorization": f"Basic {auth_b64}",
            "User-Agent": REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        token = body.get("access_token")
        expires_in = int(body.get("expires_in") or 3600)
        if token:
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["expires_at"] = now + expires_in
            return token
        logger.error("Reddit auth failed: %s", body.get("error"))
        return None
    except Exception as exc:
        logger.error("Reddit OAuth2 token request failed: %s", exc)
        return None


def _post_comment(token: str, parent_fullname: str, text: str) -> Dict[str, Any]:
    """POST /api/comment — reply to a Reddit thread or comment."""
    data = urllib.parse.urlencode({
        "api_type": "json",
        "thing_id": parent_fullname,
        "text": text,
    }).encode()
    req = urllib.request.Request(
        "https://oauth.reddit.com/api/comment",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        errors = (body.get("json") or {}).get("errors") or []
        if errors:
            return {"ok": False, "errors": errors, "body": body}
        data_out = ((body.get("json") or {}).get("data") or {})
        things = data_out.get("things") or []
        comment_id = (things[0].get("data") or {}).get("id") if things else None
        return {"ok": True, "comment_id": comment_id, "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "http_status": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _load_daily_counts(base_path: Optional[str] = None) -> Dict[str, Any]:
    """Load today's posting counts from disk."""
    from .paths import ensure_reddit_dir
    from pathlib import Path
    p = ensure_reddit_dir(Path(base_path) if base_path else None) / "posting_counts.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if data.get("date") == today:
                return data
        except Exception:
            pass
    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "total": 0, "by_hour": {}, "by_subreddit": {}}


def _save_daily_counts(counts: Dict[str, Any], base_path: Optional[str] = None) -> None:
    from .paths import ensure_reddit_dir
    from pathlib import Path
    p = ensure_reddit_dir(Path(base_path) if base_path else None) / "posting_counts.json"
    p.write_text(json.dumps(counts, ensure_ascii=False), encoding="utf-8")


def _within_rate_limits(subreddit: str, base_path: Optional[str] = None) -> Dict[str, Any]:
    """Check hard rate limits before posting."""
    counts = _load_daily_counts(base_path)
    hour = str(datetime.now(timezone.utc).hour)
    total_today = int(counts.get("total") or 0)
    this_hour = int((counts.get("by_hour") or {}).get(hour) or 0)
    this_sub = int((counts.get("by_subreddit") or {}).get(subreddit.lower()) or 0)

    if total_today >= MAX_COMMENTS_PER_DAY:
        return {"ok": False, "reason": f"daily_limit_reached ({total_today}/{MAX_COMMENTS_PER_DAY})"}
    if this_hour >= MAX_COMMENTS_PER_HOUR:
        return {"ok": False, "reason": f"hourly_limit_reached ({this_hour}/{MAX_COMMENTS_PER_HOUR})"}
    if this_sub >= MAX_COMMENTS_PER_SUBREDDIT_PER_DAY:
        return {"ok": False, "reason": f"subreddit_limit_reached ({this_sub}/{MAX_COMMENTS_PER_SUBREDDIT_PER_DAY} for r/{subreddit})"}
    return {"ok": True, "total_today": total_today, "this_hour": this_hour, "this_sub": this_sub}


def _record_post(subreddit: str, base_path: Optional[str] = None) -> None:
    counts = _load_daily_counts(base_path)
    hour = str(datetime.now(timezone.utc).hour)
    counts["total"] = int(counts.get("total") or 0) + 1
    by_hour = dict(counts.get("by_hour") or {})
    by_hour[hour] = int(by_hour.get(hour) or 0) + 1
    counts["by_hour"] = by_hour
    by_sub = dict(counts.get("by_subreddit") or {})
    sub = subreddit.lower()
    by_sub[sub] = int(by_sub.get(sub) or 0) + 1
    counts["by_subreddit"] = by_sub
    _save_daily_counts(counts, base_path)


def post_reddit_comment(
    *,
    post_id: str,
    subreddit: str,
    comment_text: str,
    thread_fullname: str = "",
    base_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Post a comment on Reddit autonomously.

    Enforces rate limits, requires credentials, returns structured result.
    thread_fullname is the Reddit t3_ fullname of the post to reply to.
    """
    creds = _reddit_credentials()
    if not creds:
        return {
            "ok": False,
            "skipped": True,
            "reason": "reddit_not_configured",
            "detail": (
                "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD "
                "in Render environment to enable autonomous Reddit posting."
            ),
        }

    rate = _within_rate_limits(subreddit, base_path)
    if not rate["ok"]:
        logger.info("Reddit rate limit — skipping post on r/%s: %s", subreddit, rate["reason"])
        return {"ok": False, "skipped": True, "reason": "rate_limited", "detail": rate["reason"]}

    token = _get_access_token(creds)
    if not token:
        return {"ok": False, "skipped": False, "reason": "auth_failed"}

    # Build the fullname if not provided
    parent = thread_fullname or f"t3_{post_id}"
    result = _post_comment(token, parent, comment_text)

    if result.get("ok"):
        _record_post(subreddit, base_path)
        logger.info(
            "Reddit comment posted on r/%s post=%s comment=%s",
            subreddit, post_id, result.get("comment_id"),
        )
    else:
        logger.warning(
            "Reddit comment failed on r/%s post=%s: %s",
            subreddit, post_id, result.get("error") or result.get("errors"),
        )

    return result

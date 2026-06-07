"""Production resilience helpers for Reddit acquisition — logging, defaults, telemetry safety."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

ERROR_DISCOVERY_CLUSTER = "discovery_cluster_failed"
ERROR_RATE_LIMITED = "rate_limited"
ERROR_QUALIFICATION = "qualification_pipeline_error"
ERROR_PREY_SCORING = "prey_scoring_error"
ERROR_DOMAIN_QUALIFICATION = "domain_qualification_error"
ERROR_SOFT_BURDEN = "soft_burden_analysis_error"
ERROR_FOUNDING_PILOT = "founding_pilot_discovery_error"
ERROR_REDDIT_PARSE = "reddit_parse_error"
ERROR_TELEMETRY = "telemetry_serialization_error"
ERROR_TIME_BUDGET = "discovery_time_budget"
ERROR_UNKNOWN = "acquisition_runtime_error"


def normalize_post(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce malformed Reddit listing rows into a safe post dict."""
    post_id = str(raw.get("post_id") or raw.get("id") or "").strip()
    subreddit = str(raw.get("subreddit") or raw.get("search_subreddit") or "").strip()
    title = str(raw.get("title") or "")
    selftext = str(raw.get("selftext") or raw.get("body") or "")[:4000]
    url = str(raw.get("url") or "")
    return {
        "post_id": post_id,
        "subreddit": subreddit,
        "title": title,
        "selftext": selftext,
        "url": url,
        "author": str(raw.get("author") or "[deleted]"),
        "created_utc": raw.get("created_utc"),
        "num_comments": int(raw.get("num_comments") or 0),
        "source": str(raw.get("source") or "reddit_public_json"),
        "search_query": str(raw.get("search_query") or raw.get("discovery_query") or ""),
        "search_subreddit": str(raw.get("search_subreddit") or subreddit),
        "discovery_source_cluster": str(
            raw.get("discovery_source_cluster") or raw.get("discovery_cluster") or "operational_security"
        ),
        "discovery_ecosystem": str(raw.get("discovery_ecosystem") or ""),
        "discovered_utc": raw.get("discovered_utc") or "",
    }


def sanitize_telemetry_metadata(meta: Optional[Dict[str, Any]], *, max_depth: int = 4) -> Dict[str, Any]:
    """JSON-safe metadata — strips non-serializable / oversized nested objects."""

    def _walk(obj: Any, depth: int) -> Any:
        if depth <= 0:
            return str(obj)[:200] if obj is not None else None
        if obj is None or isinstance(obj, (bool, int, float, str)):
            s = obj if not isinstance(obj, str) else obj[:2000]
            return s
        if isinstance(obj, (list, tuple)):
            return [_walk(x, depth - 1) for x in obj[:30]]
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in list(obj.items())[:40]:
                key = str(k)[:80]
                if key in ("plan", "organism_plan", "classification", "qualification", "draft_reply"):
                    out[key] = {
                        sk: _walk(sv, depth - 1)
                        for sk, sv in list(v.items())[:12]
                        if isinstance(v, dict)
                    } if isinstance(v, dict) else str(v)[:120]
                else:
                    out[key] = _walk(v, depth - 1)
            return out
        return str(obj)[:300]

    cleaned = _walk(dict(meta or {}), max_depth)
    try:
        json.dumps(cleaned)
        return cleaned
    except (TypeError, ValueError):
        return {"sanitized": True, "preview": str(meta)[:500]}


def classify_exception(exc: BaseException, *, phase: str = "") -> Tuple[str, str]:
    """Map exception to operator-facing error_code and short detail."""
    msg = str(exc) or exc.__class__.__name__
    low = msg.lower()
    if "429" in low or "rate limit" in low or "too many requests" in low:
        return ERROR_RATE_LIMITED, "Reddit rate limited this request; retry in a few minutes."
    if phase == "discovery":
        return ERROR_DISCOVERY_CLUSTER, msg[:240]
    if phase == "qualification":
        return ERROR_QUALIFICATION, msg[:240]
    if phase == "prey_scoring":
        return ERROR_PREY_SCORING, msg[:240]
    if phase == "soft_burden":
        return ERROR_SOFT_BURDEN, msg[:240]
    if phase == "founding_pilot":
        return ERROR_FOUNDING_PILOT, msg[:240]
    if phase == "reddit_parse":
        return ERROR_REDDIT_PARSE, msg[:240]
    if phase == "telemetry":
        return ERROR_TELEMETRY, msg[:240]
    return ERROR_UNKNOWN, msg[:240]


def log_phase_failure(phase: str, exc: BaseException, **context: Any) -> Tuple[str, str]:
    code, detail = classify_exception(exc, phase=phase)
    logger.exception(
        "Reddit acquisition %s failed [%s]: %s",
        phase,
        code,
        detail,
        extra={"context": {k: str(v)[:120] for k, v in context.items()}},
    )
    return code, detail

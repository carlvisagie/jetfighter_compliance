"""
Reddit acquisition intelligence connector.

Read-only public discovery. Operator-approved drafts only. No auto-post.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...models import utc_now
from ...routing import build_upload_route
from . import classifier, draft_generation, discovery, qualification, telemetry
from .paths import (
    APPROVED_REPLIES_JSONL,
    DRAFT_REPLIES_JSONL,
    IGNORED_POSTS_JSONL,
    ensure_reddit_dir,
)

CONNECTOR_ID = discovery.CONNECTOR_ID
DEFAULT_SEARCH_QUERIES = discovery.DEFAULT_SEARCH_QUERIES
DEFAULT_SUBREDDITS = discovery.DEFAULT_SUBREDDITS


def _append_jsonl(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> None:
    path = ensure_reddit_dir(base) / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_jsonl(filename: str, base: Optional[Path] = None, limit: int = 300) -> List[Dict[str, Any]]:
    path = ensure_reddit_dir(base) / filename
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


def run_reddit_acquisition_cycle(
    *,
    queries: Optional[List[str]] = None,
    subreddits: Optional[List[str]] = None,
    limit_per_query: int = 10,
    max_posts: int = 40,
    min_fit_score: int = 50,
    campaign_id: str = "reddit-upload-first",
    message_variant: str = "A",
    pause_seconds: float = discovery.MIN_SECONDS_BETWEEN_REQUESTS,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Discover → classify → qualify → draft → route → organism targets.
    Never auto-posts to Reddit.
    """
    from ...orchestration import ingest_discovery_candidate, load_recent_target_keys

    telemetry.emit("reddit_discovery_started", metadata={"connector": CONNECTOR_ID}, base=base)
    stats: Dict[str, Any] = {
        "ok": True,
        "connector": CONNECTOR_ID,
        "discovered": 0,
        "drafts_created": 0,
        "targets_created": 0,
        "ignored_low_fit": 0,
        "duplicates": 0,
        "when_utc": utc_now(),
    }

    posts = discovery.discover_posts(
        queries=queries,
        subreddits=subreddits,
        limit_per_query=limit_per_query,
        pause_seconds=pause_seconds,
        base=base,
    )[:max_posts]

    seen_targets = load_recent_target_keys(base)

    for post in posts:
        stats["discovered"] += 1
        cls = classifier.classify_post(post.get("title", ""), post.get("selftext", ""))
        qual = qualification.qualify_post(post, cls)

        if not cls.get("relevant") or qual["fit_score"] < min_fit_score:
            stats["ignored_low_fit"] += 1
            _append_jsonl(
                IGNORED_POSTS_JSONL,
                {
                    "post_id": post["post_id"],
                    "reason": "low_fit",
                    "fit_score": qual["fit_score"],
                    "when_utc": utc_now(),
                },
                base,
            )
            telemetry.emit("reddit_post_ignored", post_id=post["post_id"], subreddit=post.get("subreddit", ""), base=base)
            continue

        lead_id = f"LD-RDT-{post['post_id'][:8]}"
        routes = build_upload_route(
            lead_id=lead_id,
            segment="compliance-heavy",
            campaign_id=campaign_id,
            message_variant=message_variant,
            destination="inquiry",
        )
        draft = draft_generation.generate_draft_reply(post, cls, routes["primary_url"], variant=message_variant)

        opportunity_id = f"RDT-{uuid.uuid4().hex[:10]}"
        record = {
            "opportunity_id": opportunity_id,
            "post_id": post["post_id"],
            "subreddit": post.get("subreddit", ""),
            "title": post.get("title", ""),
            "url": post.get("url", ""),
            "classification": cls,
            "qualification": qual,
            "fit_score": qual["fit_score"],
            "burden_score": cls.get("burden_score", 0),
            "pain_signal": ", ".join((cls.get("pain_themes") or [])[:5]),
            "emotional_burden_score": cls.get("emotional_burden_score", 0),
            "draft_reply": draft,
            "route_url": routes["primary_url"],
            "lead_id": lead_id,
            "status": "pending_operator_review",
            "auto_post": False,
            "discovered_utc": utc_now(),
        }
        discovery.append_discovered_post(record, base)
        _append_jsonl(DRAFT_REPLIES_JSONL, record, base)
        stats["drafts_created"] += 1

        telemetry.emit("reddit_post_discovered", post_id=post["post_id"], subreddit=post.get("subreddit", ""), metadata=record, base=base)
        telemetry.emit("reddit_draft_generated", post_id=post["post_id"], metadata={"auto_post": False}, base=base)

        company_key = f"reddit:{post['post_id']}"
        if company_key in seen_targets:
            stats["duplicates"] += 1
            continue
        seen_targets.add(company_key)

        row = {
            "company_name": f"Reddit opportunity r/{post.get('subreddit', 'unknown')}",
            "segment": "compliance-heavy",
            "source": "reddit_public_json",
            "source_url": post.get("url", ""),
            "notes": f"{post.get('title', '')}\n\n{post.get('selftext', '')[:1500]}",
            "industry": "unknown",
        }
        try:
            out = ingest_discovery_candidate(
                row,
                campaign_id=campaign_id,
                message_variant=message_variant,
                min_fit_score=0,
                base=base,
            )
            if not out.get("skipped"):
                stats["targets_created"] += 1
        except Exception:
            pass

    try:
        from ... import learning

        learning.run_learning_cycle(base)
    except Exception:
        pass

    telemetry.emit("reddit_discovery_completed", metadata=stats, base=base)
    stats["message"] = (
        f"Reddit: {stats['drafts_created']} drafts for review, "
        f"{stats['targets_created']} organism targets (no auto-post)."
    )
    return stats


def approve_draft(
    post_id: str,
    *,
    operator_note: str = "",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Move draft to approved queue — operator must post manually on Reddit."""
    drafts = _load_jsonl(DRAFT_REPLIES_JSONL, base, limit=500)
    match = next((d for d in drafts if d.get("post_id") == post_id), None)
    if not match:
        return {"ok": False, "detail": "draft not found"}
    rec = dict(match)
    rec["status"] = "approved_for_manual_post"
    rec["approved_utc"] = utc_now()
    rec["operator_note"] = operator_note
    rec["auto_post"] = False
    _append_jsonl(APPROVED_REPLIES_JSONL, rec, base)
    telemetry.emit("reddit_reply_approved", post_id=post_id, metadata={"manual_post_only": True}, base=base)
    try:
        from ... import learning

        learning.record_winner(reason="reddit_draft_approved", metadata={"post_id": post_id}, base=base)
    except Exception:
        pass
    return {"ok": True, "approved": rec, "notice": "Post this reply manually on Reddit — system does not auto-post."}


def ignore_post(post_id: str, reason: str = "operator_ignored", base: Optional[Path] = None) -> Dict[str, Any]:
    _append_jsonl(
        IGNORED_POSTS_JSONL,
        {"post_id": post_id, "reason": reason, "when_utc": utc_now()},
        base,
    )
    telemetry.emit("reddit_post_ignored", post_id=post_id, metadata={"reason": reason}, base=base)
    try:
        from ... import learning

        learning.record_failure(reason=f"reddit_ignored:{reason}", metadata={"post_id": post_id}, base=base)
    except Exception:
        pass
    return {"ok": True}


def get_operator_dashboard(base: Optional[Path] = None) -> Dict[str, Any]:
    """Reddit Acquisition Intelligence panel."""
    drafts = _load_jsonl(DRAFT_REPLIES_JSONL, base, limit=100)
    pending = [d for d in drafts if d.get("status") == "pending_operator_review"]
    pending.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
    approved = _load_jsonl(APPROVED_REPLIES_JSONL, base, limit=50)
    ignored = _load_jsonl(IGNORED_POSTS_JSONL, base, limit=50)
    events = telemetry.load_events(limit=100, base=base)

    sub_counts: Dict[str, int] = {}
    pain_counts: Dict[str, int] = {}
    for d in drafts:
        sub = d.get("subreddit") or "unknown"
        sub_counts[sub] = sub_counts.get(sub, 0) + 1
        for p in (d.get("pain_signal") or "").split(","):
            p = p.strip()
            if p:
                pain_counts[p] = pain_counts.get(p, 0) + 1

    from ...orchestration import get_operator_dashboard as acq_dash

    acq = acq_dash(base)
    conv = acq.get("upload_conversion", {})

    return {
        "ok": True,
        "connector": CONNECTOR_ID,
        "doctrine": {
            "message": "Give us exactly what you have. We'll take it from here.",
            "auto_post": False,
            "success_metric": "real_paperwork_submitted",
        },
        "subreddit_targets": DEFAULT_SUBREDDITS,
        "search_queries": DEFAULT_SEARCH_QUERIES[:8],
        "pending_opportunities": pending[:20],
        "approved_for_manual_post": approved[-10:],
        "ignored_count": len(ignored),
        "telemetry_recent": events[-20:],
        "best_subreddits": sorted(sub_counts.items(), key=lambda x: -x[1])[:8],
        "top_pain_signals": sorted(pain_counts.items(), key=lambda x: -x[1])[:10],
        "upload_conversion": conv,
        "safety": {
            "auto_post": False,
            "operator_approval_required": True,
            "no_vote_manipulation": True,
            "no_impersonation": True,
        },
    }


__all__ = [
    "CONNECTOR_ID",
    "DEFAULT_SEARCH_QUERIES",
    "DEFAULT_SUBREDDITS",
    "run_reddit_acquisition_cycle",
    "approve_draft",
    "ignore_post",
    "get_operator_dashboard",
    "discover_posts",
]

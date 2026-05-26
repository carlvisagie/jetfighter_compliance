"""
Reddit acquisition intelligence connector.

Organism-autonomous engagement decisions. Operator: approve or deny only. No auto-post.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...models import utc_now
from ...routing import build_upload_route
from . import autonomy, classifier, draft_generation, discovery, learning, qualification, telemetry
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


def _update_draft_status(post_id: str, status: str, base: Optional[Path] = None, **extra: Any) -> None:
    path = ensure_reddit_dir(base) / DRAFT_REPLIES_JSONL
    if not path.is_file():
        return
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)
            continue
        if row.get("post_id") == post_id:
            row["status"] = status
            row.update(extra)
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def run_reddit_acquisition_cycle(
    *,
    queries: Optional[List[str]] = None,
    subreddits: Optional[List[str]] = None,
    limit_per_query: int = 10,
    max_posts: int = 40,
    min_fit_score: Optional[int] = None,
    campaign_id: str = "reddit-upload-first",
    message_variant: str = "A",
    pause_seconds: float = discovery.MIN_SECONDS_BETWEEN_REQUESTS,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Discover → classify → organism plan → draft → operator queue (approve/deny only)."""
    from ...orchestration import ingest_discovery_candidate, load_recent_target_keys

    state = learning.load_learning_state(base)
    if min_fit_score is None:
        min_fit_score = int(state.get("min_fit_threshold", 50))

    telemetry.emit("reddit_discovery_started", metadata={"connector": CONNECTOR_ID}, base=base)
    stats: Dict[str, Any] = {
        "ok": True,
        "connector": CONNECTOR_ID,
        "discovered": 0,
        "queued_for_operator": 0,
        "organism_auto_skipped": 0,
        "drafts_created": 0,
        "targets_created": 0,
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
        plan = autonomy.decide_engagement(post, cls, qual, state=state)

        if not cls.get("relevant") or qual["fit_score"] < min_fit_score:
            stats["organism_auto_skipped"] += 1
            learning.record_outcome(
                "organism_deferred",
                post_id=post.get("post_id", ""),
                subreddit=post.get("subreddit", ""),
                metadata={"reason": "low_fit"},
                base=base,
            )
            continue

        if not plan.get("show_operator_queue"):
            stats["organism_auto_skipped"] += 1
            _append_jsonl(
                IGNORED_POSTS_JSONL,
                {
                    "post_id": post["post_id"],
                    "reason": plan.get("engagement_stage"),
                    "organism_rationale": plan.get("rationale"),
                    "when_utc": utc_now(),
                },
                base,
            )
            continue

        lead_id = f"LD-RDT-{post['post_id'][:8]}"
        variant = plan.get("wording_variant") or message_variant
        routes = build_upload_route(
            lead_id=lead_id,
            segment="compliance-heavy",
            campaign_id=campaign_id,
            message_variant=variant,
            destination="inquiry",
        )
        draft = draft_generation.generate_draft_reply(
            post, cls, routes["primary_url"], variant=variant, plan=plan
        )

        opportunity_id = f"RDT-{uuid.uuid4().hex[:10]}"
        record = {
            "opportunity_id": opportunity_id,
            "post_id": post["post_id"],
            "subreddit": post.get("subreddit", ""),
            "title": post.get("title", ""),
            "url": post.get("url", ""),
            "classification": cls,
            "qualification": qual,
            "organism_plan": plan,
            "fit_score": qual["fit_score"],
            "burden_score": cls.get("burden_score", 0),
            "pain_signal": ", ".join((cls.get("pain_themes") or [])[:5]),
            "emotional_burden_score": cls.get("emotional_burden_score", 0),
            "draft_reply": draft,
            "route_url": routes["primary_url"],
            "lead_id": lead_id,
            "status": "awaiting_operator_decision",
            "auto_post": False,
            "operator_actions": ["approve", "deny"],
            "discovered_utc": utc_now(),
        }
        discovery.append_discovered_post(record, base)
        _append_jsonl(DRAFT_REPLIES_JSONL, record, base)
        stats["drafts_created"] += 1
        stats["queued_for_operator"] += 1

        telemetry.emit(
            "reddit_post_discovered",
            post_id=post["post_id"],
            subreddit=post.get("subreddit", ""),
            metadata={"plan": plan, "auto_post": False},
            base=base,
        )
        telemetry.emit("reddit_draft_generated", post_id=post["post_id"], metadata={"auto_post": False}, base=base)

        company_key = f"reddit:{post['post_id']}"
        if company_key not in seen_targets:
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
                    message_variant=variant,
                    min_fit_score=0,
                    base=base,
                )
                if not out.get("skipped"):
                    stats["targets_created"] += 1
            except Exception:
                pass

    learning.run_daily_reddit_learning(base)
    telemetry.emit("reddit_discovery_completed", metadata=stats, base=base)
    stats["message"] = (
        f"Reddit: {stats['queued_for_operator']} awaiting approve/deny, "
        f"{stats['organism_auto_skipped']} handled by organism."
    )
    return stats


def approve_draft(
    post_id: str,
    *,
    operator_note: str = "",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Operator APPROVE — paste organism draft on Reddit manually."""
    drafts = _load_jsonl(DRAFT_REPLIES_JSONL, base, limit=500)
    match = next((d for d in drafts if d.get("post_id") == post_id), None)
    if not match:
        return {"ok": False, "detail": "opportunity not found"}
    rec = dict(match)
    draft = rec.get("draft_reply") or {}
    paste_text = draft.get("public_reply_text") or draft.get("body", "")
    rec["status"] = "approved_for_manual_post"
    rec["approved_utc"] = utc_now()
    rec["auto_post"] = False
    _append_jsonl(APPROVED_REPLIES_JSONL, rec, base)
    _update_draft_status(post_id, "approved", base, approved_utc=utc_now())
    learning.record_outcome(
        "operator_approved",
        post_id=post_id,
        subreddit=rec.get("subreddit", ""),
        metadata={"variant": draft.get("variant"), "stage": (rec.get("organism_plan") or {}).get("engagement_stage")},
        base=base,
    )
    if draft.get("variant"):
        learning.record_outcome(
            "wording_win",
            post_id=post_id,
            metadata={"variant": draft.get("variant")},
            base=base,
        )
    telemetry.emit("reddit_reply_approved", post_id=post_id, metadata={"manual_post_only": True}, base=base)
    return {
        "ok": True,
        "approved": rec,
        "paste_on_reddit": paste_text,
        "route_for_reference": draft.get("operator_route_copy") or rec.get("route_url", ""),
        "notice": "Copy the text below and post on Reddit yourself. The organism does not auto-post.",
    }


def deny_draft(post_id: str, reason: str = "operator_denied", base: Optional[Path] = None) -> Dict[str, Any]:
    """Operator DENY — organism learns and will adjust."""
    drafts = _load_jsonl(DRAFT_REPLIES_JSONL, base, limit=500)
    match = next((d for d in drafts if d.get("post_id") == post_id), None)
    sub = match.get("subreddit", "") if match else ""
    _append_jsonl(
        IGNORED_POSTS_JSONL,
        {"post_id": post_id, "reason": reason, "when_utc": utc_now()},
        base,
    )
    _update_draft_status(post_id, "denied", base)
    learning.record_outcome("operator_denied", post_id=post_id, subreddit=sub, metadata={"reason": reason}, base=base)
    telemetry.emit("reddit_post_ignored", post_id=post_id, metadata={"reason": reason}, base=base)
    return {"ok": True, "denied": True}


def ignore_post(post_id: str, reason: str = "operator_denied", base: Optional[Path] = None) -> Dict[str, Any]:
    return deny_draft(post_id, reason=reason, base=base)


def get_operator_dashboard(base: Optional[Path] = None) -> Dict[str, Any]:
    """Lightweight approve/deny queue — organism handles everything else."""
    drafts = _load_jsonl(DRAFT_REPLIES_JSONL, base, limit=200)
    pending = [
        d
        for d in drafts
        if d.get("status") in ("awaiting_operator_decision", "pending_operator_review")
    ]
    pending.sort(key=lambda x: (x.get("organism_plan") or {}).get("organism_confidence", 0), reverse=True)

    state = learning.load_learning_state(base)
    from ...orchestration import get_operator_dashboard as acq_dash

    acq = acq_dash(base)

    return {
        "ok": True,
        "connector": CONNECTOR_ID,
        "operator_role": "strategic_approval_only",
        "operator_actions": ["approve", "deny"],
        "doctrine": {
            "message": "Give us exactly what you have. We'll take it from here.",
            "auto_post": False,
            "success_metric": "real_paperwork_submitted",
            "organism_handles": [
                "engagement_stage",
                "link_appropriateness",
                "subreddit_safety",
                "pacing",
                "wording",
                "timing",
                "cooldowns",
                "follow_up_cadence",
            ],
        },
        "pending_opportunities": [
            {
                "post_id": o.get("post_id"),
                "subreddit": o.get("subreddit"),
                "title": o.get("title"),
                "url": o.get("url"),
                "burden_score": o.get("burden_score"),
                "fit_score": o.get("fit_score"),
                "organism_rationale": (o.get("organism_plan") or {}).get("rationale", ""),
                "engagement_stage": (o.get("organism_plan") or {}).get("engagement_stage", ""),
                "organism_confidence": (o.get("organism_plan") or {}).get("organism_confidence", 0),
                "paste_text": (o.get("draft_reply") or {}).get("public_reply_text")
                or (o.get("draft_reply") or {}).get("body", ""),
                "link_in_reply": (o.get("draft_reply") or {}).get("link_in_public_reply", False),
            }
            for o in pending[:15]
        ],
        "learning": {
            "last_daily_learning_utc": state.get("last_daily_learning_utc"),
            "min_fit_threshold": state.get("min_fit_threshold"),
            "wording_winners": state.get("wording_winners"),
            "outcome_totals": state.get("outcome_totals"),
        },
        "upload_conversion": acq.get("upload_conversion", {}),
        "ignored_count": len(_load_jsonl(IGNORED_POSTS_JSONL, base, limit=100)),
        "safety": {
            "auto_post": False,
            "operator_approval_required": True,
            "platform_trust_first": True,
        },
    }


__all__ = [
    "CONNECTOR_ID",
    "DEFAULT_SEARCH_QUERIES",
    "DEFAULT_SUBREDDITS",
    "run_reddit_acquisition_cycle",
    "approve_draft",
    "deny_draft",
    "ignore_post",
    "get_operator_dashboard",
    "discover_posts",
]

discover_posts = discovery.discover_posts

"""Operator-review draft replies — never auto-posted."""
from __future__ import annotations

from typing import Any, Dict

FORBIDDEN_PHRASES = (
    "guaranteed certification",
    "you will pass",
    "act now",
    "limited time",
    "dm me for",
    "check out our amazing",
    "as a customer",
    "i used this service",
)

OPENERS = [
    "The hardest part is usually figuring out where to start — not having perfect paperwork.",
    "You do not need perfect documentation to begin.",
    "Most companies start with partial paperwork and organize from there.",
]

CLOSERS = [
    "If it helps, you can upload what you already have (policies, screenshots, spreadsheets, questionnaires) and sort out the rest from there.",
    "Give us exactly what you have — messy and partial is fine — and let someone competent take the organizing from there.",
]


def generate_draft_reply(
    post: Dict[str, Any],
    classification: Dict[str, Any],
    route_url: str,
    *,
    variant: str = "A",
) -> Dict[str, Any]:
    """Human-toned draft for operator review only."""
    title = (post.get("title") or "")[:200]
    themes = classification.get("pain_themes") or []
    opener_idx = hash(post.get("post_id", "")) % len(OPENERS)
    opener = OPENERS[opener_idx]
    closer = CLOSERS[0] if variant.upper() == "A" else CLOSERS[1]

    empathy = ""
    if "overwhelm" in (classification.get("emotional_tags") or []):
        empathy = "That overwhelmed feeling is really common with compliance paperwork. "
    elif "confusion" in (classification.get("emotional_tags") or []):
        empathy = "CMMC/DFARS/NIST language can feel like a wall of requirements. "
    elif themes:
        empathy = "A lot of small suppliers hit the same paperwork bottleneck. "

    body = (
        f"{empathy}{opener} "
        f"{closer} "
        f"(Upload-first link for your review — not posted automatically: {route_url})"
    ).strip()

    for bad in FORBIDDEN_PHRASES:
        if bad in body.lower():
            body = f"{OPENERS[0]} {CLOSERS[0]}"

    return {
        "variant": variant.upper(),
        "headline": "Give us exactly what you have. We'll take it from here.",
        "body": body,
        "tone": "calm_helpful_non_pushy",
        "doctrine": "upload_first_burden_removal",
        "auto_post": False,
        "requires_operator_approval": True,
        "context_post_title": title,
        "forbidden_auto_post": True,
    }

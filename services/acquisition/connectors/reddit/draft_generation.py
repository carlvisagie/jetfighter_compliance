"""Operator-review draft replies — organism wording; never auto-posted."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ...social_intelligence import emotional_resonance, etiquette

FORBIDDEN_PHRASES = (
    "guaranteed certification",
    "you will pass",
    "act now",
    "limited time",
    "dm me for",
    "check out our amazing",
    "as a customer",
    "i used this service",
    "click here",
    "sign up now",
)

OPENERS = [
    "The hardest part is usually figuring out where to start — not having perfect paperwork.",
    "You do not need perfect documentation to begin.",
    "Most companies start with partial paperwork and organize from there.",
]

CLOSERS_SOFT = [
    "If you want, you can gather whatever you already have — policies, screenshots, spreadsheets — and sort it out from there. No need for perfect folders first.",
    "A lot of people just start with messy partial files and organize later. That is completely normal.",
]

CLOSERS_ROUTE = [
    "If it helps, you can upload what you already have and let someone competent take the organizing from there.",
    "Give us exactly what you have — messy and partial is fine — and take it from there.",
]


def generate_draft_reply(
    post: Dict[str, Any],
    classification: Dict[str, Any],
    route_url: str,
    *,
    variant: str = "A",
    plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Human-toned draft — public paste text vs operator-only route copy."""
    plan = plan or {}
    title = (post.get("title") or "")[:200]
    themes = classification.get("pain_themes") or []
    variant = (plan.get("wording_variant") or variant or "A").upper()
    opener_idx = hash(post.get("post_id", "")) % len(OPENERS)
    opener = OPENERS[opener_idx]

    strategy = plan.get("engagement_strategy") or (plan.get("social_intelligence") or {}).get(
        "engagement_strategy", "helpful_clarification"
    )
    guidance = emotional_resonance.build_reply_guidance(classification, strategy)
    empathy = guidance.get("empathy_prefix", "")
    if not empathy:
        if "overwhelm" in (classification.get("emotional_tags") or []):
            empathy = "That overwhelmed feeling is really common with compliance paperwork. "
        elif "confusion" in (classification.get("emotional_tags") or []):
            empathy = "CMMC/DFARS/NIST language can feel like a wall of requirements. "
        elif themes:
            empathy = "A lot of small suppliers hit the same paperwork bottleneck. "

    include_link = bool(plan.get("link_in_public_reply"))
    stage = plan.get("engagement_stage", "assist_soft")

    social = plan.get("social_intelligence") or {}
    if strategy == "practical_checklist":
        checklist = (
            "A practical starting point: list what the customer or prime already asked for, "
            "gather whatever policies/screenshots you have (even messy), and note gaps — "
            "you do not need a perfect SSP on day one."
        )
        public_body = f"{empathy}{checklist}".strip()
    elif stage == "empathize_only" or not include_link:
        closer = CLOSERS_SOFT[0 if variant == "A" else 1]
        public_body = f"{empathy}{opener} {closer}".strip()
    else:
        closer = CLOSERS_ROUTE[0 if variant == "A" else 1]
        public_body = f"{empathy}{opener} {closer}".strip()
        if include_link and route_url and social.get("link_allowed", include_link):
            public_body += f"\n\n{route_url}"

    fallback = f"{OPENERS[0]} {CLOSERS_SOFT[0]}"
    for bad in FORBIDDEN_PHRASES:
        if bad in public_body.lower():
            public_body = fallback
    if conversational_memory_repetitive(public_body, post.get("subreddit", "")):
        public_body = fallback
    public_body = etiquette.sanitize_reply(public_body, fallback)

    try:
        from services.intake.mode import is_intake_mode as is_founding_pilot_mode
        from services.intake.messaging import PILOT_HEADLINE, PILOT_REASSURANCE

        if is_founding_pilot_mode():
            pilot_note = (
                f"{PILOT_HEADLINE} — we are validating an upload-first workflow. "
                "Upload whatever you already have (questionnaires, policies, screenshots, spreadsheets). "
                f"{PILOT_REASSURANCE} This is a pilot validation run, not a sales pitch."
            )
            if include_link and route_url:
                public_body = f"{public_body}\n\n{pilot_note}\n{route_url}"
            else:
                public_body = f"{public_body}\n\n{pilot_note}"
    except Exception:
        pass

    return {
        "variant": variant,
        "headline": "Founding Pilot — Free Compliance Burden Review",
        "body": public_body,
        "public_reply_text": public_body,
        "operator_route_copy": route_url if route_url else "",
        "tone": "calm_helpful_non_pushy",
        "doctrine": "upload_first_burden_removal",
        "auto_post": False,
        "requires_operator_approval": True,
        "context_post_title": title,
        "forbidden_auto_post": True,
        "link_in_public_reply": include_link and bool((plan.get("social_intelligence") or {}).get("link_allowed", include_link)),
        "social_tone": guidance.get("tone", "helpful_peer"),
        "engagement_strategy": strategy,
    }


def conversational_memory_repetitive(text: str, subreddit: str) -> bool:
    try:
        from ...social_intelligence.conversational_memory import is_repetitive_phrasing

        return is_repetitive_phrasing(text, subreddit)
    except Exception:
        return False

"""Emotional resonance — calm, practical, non-corporate tone."""
from __future__ import annotations

from typing import Any, Dict, List


def detect_emotional_state(classification: Dict[str, Any]) -> str:
    tags = classification.get("emotional_tags") or []
    intent = classification.get("author_intent", "")
    if intent == "VENTING_OR_OVERWHELMED" or "overwhelm" in tags:
        return "overwhelm"
    if "fear" in tags or "audit_anxiety" in (classification.get("pain_themes") or []):
        return "fear"
    if "confusion" in tags:
        return "confusion"
    if "procrastination" in tags:
        return "uncertainty"
    return "neutral"


def resonance_for_state(emotional_state: str, strategy: str) -> Dict[str, Any]:
    templates = {
        "overwhelm": {
            "prefix": "That overwhelmed feeling is really common — you're not behind because you're careless. ",
            "tone": "reassuring_practical",
            "avoid": ["corporate", "urgency", "sales"],
        },
        "fear": {
            "prefix": "The audit anxiety piece is real — most teams feel it before they have a clear map. ",
            "tone": "calm_clear",
            "avoid": ["guarantees", "fear_amplification"],
        },
        "confusion": {
            "prefix": "The CMMC/DFARS/NIST overlap confuses almost everyone at first — that's normal. ",
            "tone": "clarifying",
            "avoid": ["jargon_dump", "condescension"],
        },
        "uncertainty": {
            "prefix": "Not knowing where to start is usually the hardest part, not the paperwork itself. ",
            "tone": "encouraging",
            "avoid": ["pressure", "deadlines"],
        },
        "neutral": {
            "prefix": "",
            "tone": "helpful_peer",
            "avoid": ["marketing"],
        },
    }
    base = dict(templates.get(emotional_state, templates["neutral"]))
    if strategy in ("emotional_reassurance", "helpful_clarification"):
        base["emphasis"] = "empathy_first"
    elif strategy == "practical_checklist":
        base["emphasis"] = "actionable_steps"
    return base


def build_reply_guidance(classification: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    state = detect_emotional_state(classification)
    resonance = resonance_for_state(state, strategy)
    return {
        "emotional_state": state,
        "resonance": resonance,
        "tone": resonance.get("tone", "helpful_peer"),
        "empathy_prefix": resonance.get("prefix", ""),
    }

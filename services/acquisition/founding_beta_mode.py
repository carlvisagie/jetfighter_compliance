"""Founding beta hooks for acquisition probability (avoids circular imports)."""
from __future__ import annotations

from typing import Any, Dict


def _beta() -> bool:
    try:
        from services.founding_beta.mode import is_founding_beta_mode

        return is_founding_beta_mode()
    except Exception:
        return True


def deployable_intent(
    intent: str,
    *,
    soft_score: int,
    has_personal_need: bool,
    predator_raw: int,
) -> bool:
    if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED"):
        return True
    if soft_score >= 42 and has_personal_need and predator_raw < 12:
        return True
    if _beta() and intent == "UNKNOWN" and soft_score >= 35 and has_personal_need and predator_raw < 10:
        return True
    return False


def intent_passes_prey_gate(intent: str, *, soft_score: int, prob: Dict[str, Any]) -> bool:
    if intent in ("SEEKING_HELP", "VENTING_OR_OVERWHELMED"):
        return True
    if _beta() and intent == "UNKNOWN" and soft_score >= 35 and prob.get("has_operational_need"):
        return True
    if soft_score >= 40 and prob.get("has_operational_need") and int(prob.get("operational_entanglement_score", 0)) >= 30:
        return True
    return False

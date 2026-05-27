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
    if _beta() and intent == "UNKNOWN" and soft_score >= 30 and prob.get("has_operational_need"):
        return True
    if soft_score >= 38 and prob.get("has_operational_need") and int(prob.get("operational_entanglement_score", 0)) >= 25:
        return True
    if _beta() and soft_score >= 32 and int(prob.get("paperwork_likelihood_score", 0)) >= 28:
        return True
    return False


def passes_founding_beta_prey_gate(
    qualification: Dict[str, Any],
    classification: Dict[str, Any],
    *,
    min_prey_score: int,
) -> bool:
    """Founding beta primary gate — operational burden over distress."""
    from .acquisition_probability import passes_prey_gate

    if passes_prey_gate(qualification, classification, min_prey_score=min_prey_score):
        return True
    if not _beta():
        return False
    prob = qualification.get("acquisition_probability") or {}
    prey = int(qualification.get("prey_score", 0))
    tier = int(qualification.get("prey_tier") or prob.get("prey_tier", 4))
    relaxed = max(42, min_prey_score - 6)
    return bool(
        prey >= relaxed
        and tier <= 3
        and int(prob.get("predator_penalty", 99)) < 48
        and prob.get("predator_class")
        not in ("consultant", "educator", "moderator", "promoter", "ama")
        and not prob.get("topical_only_risk")
        and (prob.get("has_operational_need") or int(prob.get("soft_burden_score", 0)) >= 32)
        and intent_passes_prey_gate(
            classification.get("author_intent", "UNKNOWN"),
            soft_score=int(prob.get("soft_burden_score", 0)),
            prob=prob,
        )
    )

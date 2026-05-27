"""Founding Beta Reddit discovery — wider operational net, fallback queue, diagnostics."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from services.acquisition.acquisition_probability import (
    BANNED_PREDATOR_CLASSES,
    TARGET_QUEUE_MIN,
)
from .mode import is_founding_beta_mode
from .telemetry import emit_beta_event

FALLBACK_MIN_PREY = 42
FALLBACK_MIN_OPERATIONAL_CONTEXT = 32
FALLBACK_MIN_PAPERWORK = 22
FALLBACK_MIN_FIT = 38


class CycleDiagnostics:
    """Per-cycle block accounting for operator empty-queue transparency."""

    def __init__(self) -> None:
        self.blocked_by_reason: Counter = Counter()
        self.predator_block_count = 0
        self.near_miss_candidates: List[Dict[str, Any]] = []
        self.operational_candidate_count = 0
        self.fallback_discovery_used = False

    def record_block(self, reason: str, *, post: Dict[str, Any], qual: Dict[str, Any], cls: Dict[str, Any]) -> None:
        self.blocked_by_reason[reason] += 1
        prob = qual.get("acquisition_probability") or {}
        pc = qual.get("predator_class") or prob.get("predator_class", "")
        if pc in BANNED_PREDATOR_CLASSES or int(prob.get("predator_penalty", 0)) >= 48:
            self.predator_block_count += 1
        if prob.get("has_operational_need") or int(prob.get("soft_burden_score", 0)) >= 35:
            self.operational_candidate_count += 1
        prey = int(qual.get("prey_score", 0))
        effective = int(prob.get("min_prey_score", 50))
        if prey >= effective - 6 and prey < effective and reason in ("low_prey", "prey_gate"):
            self.near_miss_candidates.append(
                {
                    "post_id": post.get("post_id"),
                    "title": (post.get("title") or "")[:120],
                    "prey_score": prey,
                    "prey_tier": qual.get("prey_tier"),
                    "predator_class": pc,
                    "threshold": effective,
                    "reason": reason,
                }
            )

    def to_dict(self, *, effective_threshold: int, queued: int, discovered: int) -> Dict[str, Any]:
        near = self.near_miss_candidates[:12]
        return {
            "discovered": discovered,
            "queued_for_operator": queued,
            "effective_prey_threshold": effective_threshold,
            "predator_block_count": self.predator_block_count,
            "operational_candidate_count": self.operational_candidate_count,
            "near_miss_count": len(self.near_miss_candidates),
            "near_miss_candidates": near,
            "blocked_by_reason": dict(self.blocked_by_reason),
            "fallback_discovery_used": self.fallback_discovery_used,
            "zero_result_cycle": discovered > 0 and queued == 0,
            "empty_queue_summary": _empty_queue_summary(self, effective_threshold, queued, discovered),
        }


def _empty_queue_summary(diag: CycleDiagnostics, threshold: int, queued: int, discovered: int) -> str:
    if queued > 0 or discovered == 0:
        return ""
    top = diag.blocked_by_reason.most_common(4)
    parts = [f"No candidates queued from {discovered} discovered posts."]
    if top:
        parts.append("Top blocks: " + ", ".join(f"{k}={v}" for k, v in top))
    parts.append(f"Effective prey threshold: {threshold}.")
    if diag.near_miss_candidates:
        parts.append(f"Near misses: {len(diag.near_miss_candidates)}.")
    if diag.predator_block_count:
        parts.append(f"Predator/consultant blocks: {diag.predator_block_count}.")
    return " ".join(parts)


def is_founding_beta_discovery_mode() -> bool:
    return is_founding_beta_mode()


def classify_queue_block(
    *,
    post: Dict[str, Any],
    cls: Dict[str, Any],
    qual: Dict[str, Any],
    plan: Dict[str, Any],
    effective_prey: int,
    min_fit_score: int,
    queued_this_cycle: int,
    target_queue_max: int,
) -> Optional[str]:
    """Return block reason if this post must not queue in strict mode."""
    prob = qual.get("acquisition_probability") or {}
    pc = qual.get("predator_class") or prob.get("predator_class", "")
    if pc in BANNED_PREDATOR_CLASSES:
        return "predator_block"
    if int(prob.get("predator_penalty", 0)) >= 48:
        return "predator_penalty"
    if not cls.get("relevant"):
        return "not_relevant"
    if qual.get("fit_score", 0) < min_fit_score:
        return "low_fit"
    from services.acquisition.founding_beta_mode import passes_founding_beta_prey_gate

    if not passes_founding_beta_prey_gate(qual, cls, min_prey_score=effective_prey):
        if int(qual.get("prey_score", 0)) >= effective_prey - 8:
            return "prey_gate"
        return "low_prey"
    if queued_this_cycle >= target_queue_max:
        return "queue_cap"
    if not plan.get("show_operator_queue"):
        if cls.get("author_intent") in ("GIVING_ADVICE", "PROMOTING_SERVICE"):
            return "predator_block"
        return "autonomy_defer"
    return None


def passes_founding_beta_fallback_gate(
    qual: Dict[str, Any],
    cls: Dict[str, Any],
) -> bool:
    """Medium-prey operational posts when strict pass leaves queue empty."""
    prob = qual.get("acquisition_probability") or {}
    pc = qual.get("predator_class") or prob.get("predator_class", "none")
    if pc in BANNED_PREDATOR_CLASSES:
        return False
    if int(prob.get("predator_penalty", 99)) >= 48:
        return False
    prey = int(qual.get("prey_score", 0))
    if prey < FALLBACK_MIN_PREY:
        return False
    tier = int(qual.get("prey_tier") or prob.get("prey_tier", 4))
    if tier >= 5:
        return False
    if tier == 4 and not prob.get("has_operational_need"):
        return False
    op_ctx = (
        int(prob.get("operational_entanglement_score", 0))
        + int(prob.get("operational_pressure_score", 0))
        + int(prob.get("paperwork_likelihood_score", 0))
    )
    likely_pw = int(prob.get("paperwork_likelihood_score", 0))
    if op_ctx < FALLBACK_MIN_OPERATIONAL_CONTEXT or likely_pw < FALLBACK_MIN_PAPERWORK:
        return False
    if prob.get("topical_only_risk") and not prob.get("has_operational_need"):
        return False
    intent = cls.get("author_intent", "")
    if intent in ("GIVING_ADVICE", "PROMOTING_SERVICE"):
        return False
    if intent == "DISCUSSING_NEWS" and cls.get("recommended_action") == "news_context_only":
        return False
    return bool(prob.get("has_operational_need") or int(prob.get("soft_burden_score", 0)) >= 32)


def plan_for_founding_beta_fallback(plan: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(plan)
    out["show_operator_queue"] = True
    out["engagement_stage"] = out.get("engagement_stage") or "assist_soft"
    out["rationale"] = (
        "Founding beta fallback — calm operational compliance burden (no distress required). "
        + (out.get("rationale") or "")
    )[:280]
    return out


def enrich_founding_beta_candidate_fields(
    record: Dict[str, Any],
    *,
    post: Dict[str, Any],
    qual: Dict[str, Any],
    cls: Dict[str, Any],
    plan: Dict[str, Any],
    fallback_used: bool = False,
) -> None:
    prob = qual.get("acquisition_probability") or {}
    reasons = qual.get("prey_reasons") or prob.get("prey_reasons") or []
    paperwork = record.get("likely_paperwork_indicators") or []
    record["source"] = "reddit"
    record["operational_burden_reason"] = "; ".join(reasons[:4]) or record.get("operational_context", "")
    record["likely_paperwork"] = ", ".join(paperwork[:4]) or "Questionnaires, policies, partial evidence likely"
    record["beta_fit"] = _beta_fit_label(qual, prob, fallback_used)
    record["recommended_next_action"] = (
        "Approve — paste founding beta paperwork review offer (validation run, not sales)."
        if plan.get("show_operator_queue")
        else "Skip"
    )
    record["founding_beta_framing"] = (
        "Free Founding Beta paperwork review — upload what you have; messy/partial is fine."
    )


def _beta_fit_label(qual: Dict[str, Any], prob: Dict[str, Any], fallback: bool) -> str:
    tier = int(qual.get("prey_tier") or prob.get("prey_tier", 4))
    prey = int(qual.get("prey_score", 0))
    if tier == 1 and prey >= 55:
        return "high — immediate operational burden"
    if tier <= 2:
        return "strong — likely paperwork upload"
    if tier == 3 or fallback:
        return "moderate — emerging compliance realization"
    return "low"


def emit_cycle_telemetry(stats: Dict[str, Any], diag: CycleDiagnostics) -> None:
    try:
        from services.acquisition.connectors.reddit.resilience import sanitize_telemetry_metadata

        meta = sanitize_telemetry_metadata(
            {
                **stats,
                **diag.to_dict(
                    effective_threshold=stats.get("effective_prey_threshold", 50),
                    queued=stats.get("queued_for_operator", 0),
                    discovered=stats.get("discovered", 0),
                ),
            }
        )
        if meta.get("zero_result_cycle"):
            emit_beta_event("zero_result_cycle", metadata=meta)
        if diag.fallback_discovery_used:
            emit_beta_event("fallback_discovery_used", metadata=meta)
        if diag.near_miss_candidates:
            emit_beta_event(
                "near_miss_candidate",
                metadata={
                    "count": len(diag.near_miss_candidates),
                    "samples": diag.near_miss_candidates[:5],
                },
            )
        emit_beta_event("beta_discovery_cycle_completed", metadata=meta)
    except Exception:
        import logging

        logging.getLogger(__name__).warning("emit_cycle_telemetry skipped", exc_info=True)

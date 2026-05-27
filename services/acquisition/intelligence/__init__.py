"""Acquisition intelligence modules — burden detection beyond loud distress signals."""

from .discovery_expansion import (
    build_cycle_discovery_plan,
    build_cycle_queries,
    classify_discovery_cluster,
    ensure_semantic_diversity,
    ensure_subreddit_diversity,
    infer_burden_profile,
    record_ecosystem_outcome,
)
from .operational_pressure import SIGNAL_CATEGORIES, score_operational_pressure
from .soft_burden import score_soft_burden

__all__ = [
    "score_soft_burden",
    "score_operational_pressure",
    "SIGNAL_CATEGORIES",
    "build_cycle_queries",
    "build_cycle_discovery_plan",
    "classify_discovery_cluster",
    "ensure_semantic_diversity",
    "ensure_subreddit_diversity",
    "infer_burden_profile",
    "record_ecosystem_outcome",
]

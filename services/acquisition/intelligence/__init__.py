"""Acquisition intelligence modules — burden detection beyond loud distress signals."""

from .discovery_expansion import (
    build_cycle_queries,
    classify_discovery_cluster,
    ensure_semantic_diversity,
)
from .soft_burden import score_soft_burden

__all__ = [
    "score_soft_burden",
    "build_cycle_queries",
    "classify_discovery_cluster",
    "ensure_semantic_diversity",
]

"""Organism Core — reusable self-awareness architecture.

A domain-agnostic engine for organisms (products) that need to honestly
report their own state. KYC is the first implementation. Purposeful,
Sage, Just Talk, Transformation Session, and future products plug in by
providing their own collectors, checks, recommendations, and residue
patterns.

Public surface:
    AwarenessEngine        — orchestrator (compose + run)
    SignalCollector        — base class for domain signal collection
    Check                  — base class for domain reconciliation checks
    CheckResult            — return type from a Check
    Severity / HealthState — enums
    derive_health          — pure function (checks -> health + bottleneck)
    ResidueScanner         — generic pattern scanner with location classes
    Pattern                — what to look for
    LocationRule           — how to classify a match
    RecommendationRegistry — check_name -> action text
    write_snapshot         — atomic JSON snapshot writer
"""
from __future__ import annotations

from organism_core.awareness.engine import AwarenessEngine
from organism_core.awareness.signals import SignalCollector, SignalBundle
from organism_core.health.checks import Check, CheckResult
from organism_core.health.severity import HealthState, Severity
from organism_core.health.derivation import derive_health
from organism_core.recommendations.registry import RecommendationRegistry
from organism_core.residue.patterns import LocationRule, Pattern
from organism_core.residue.scanner import ResidueScanner, ResidueReport
from organism_core.persistence.snapshot_writer import write_snapshot

__all__ = [
    "AwarenessEngine",
    "SignalCollector",
    "SignalBundle",
    "Check",
    "CheckResult",
    "HealthState",
    "Severity",
    "derive_health",
    "RecommendationRegistry",
    "ResidueScanner",
    "ResidueReport",
    "Pattern",
    "LocationRule",
    "write_snapshot",
]

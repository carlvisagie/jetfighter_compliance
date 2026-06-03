"""AwarenessEngine — the orchestrator that ties everything together.

A domain (KYC, Purposeful, Sage, etc.) constructs one AwarenessEngine
per organism, registering its collectors, checks, recommendations,
optional residue scanner, and optional snapshot path.

Calling :meth:`snapshot` runs the full pipeline:

    1. Run every SignalCollector (failures isolated)
    2. Run optional ResidueScanner
    3. Run every Check against the SignalBundle (failures isolated)
    4. Derive overall health + bottleneck
    5. Compose a final snapshot dict (timestamp, signals, checks, health,
       residue, recommendation, plus any extra metadata the domain adds)
    6. Optionally write to disk

Returns a JSON-serializable dict ready for an HTTP response.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from organism_core.awareness.signals import SignalBundle, SignalCollector
from organism_core.health.checks import Check, CheckResult
from organism_core.health.derivation import derive_health
from organism_core.health.severity import HealthState
from organism_core.persistence.snapshot_writer import write_snapshot
from organism_core.recommendations.registry import RecommendationRegistry
from organism_core.residue.scanner import ResidueScanner

logger = logging.getLogger(__name__)


@dataclass
class _GatingConfig:
    fn: Callable[[SignalBundle], Optional[Tuple[str, str]]]


class AwarenessEngine:
    """Composes collectors + checks + recommendations into a snapshot."""

    def __init__(
        self,
        *,
        organism_name: str,
        collectors: Sequence[SignalCollector],
        checks: Sequence[Check],
        recommendations: Optional[RecommendationRegistry] = None,
        residue_scanner: Optional[ResidueScanner] = None,
        residue_root: Optional[Path] = None,
        snapshot_path: Optional[Path] = None,
        gating: Optional[Callable[[SignalBundle], Optional[Tuple[str, str]]]] = None,
        green_workload_indicator: Optional[Callable[[SignalBundle], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not organism_name:
            raise ValueError("organism_name is required")
        self._organism = organism_name
        self._collectors = list(collectors)
        self._checks = list(checks)
        self._recs = recommendations or RecommendationRegistry()
        self._scanner = residue_scanner
        self._residue_root = residue_root
        self._snapshot_path = Path(snapshot_path) if snapshot_path else None
        self._gating = _GatingConfig(fn=gating) if gating else None
        self._workload = green_workload_indicator
        self._metadata = dict(metadata or {})

    def add_metadata(self, key: str, value: Any) -> "AwarenessEngine":
        self._metadata[key] = value
        return self

    def snapshot(self, *, persist: bool = True) -> Dict[str, Any]:
        """Run the full awareness pipeline and return the snapshot dict."""
        bundle = SignalBundle()
        for collector in self._collectors:
            cname = collector.name or type(collector).__name__
            bundle.add(cname, collector.safe_collect())

        residue_report = None
        if self._scanner is not None and self._residue_root is not None:
            try:
                residue_report = self._scanner.scan(self._residue_root)
                bundle.add("residue", residue_report.to_dict())
            except Exception as exc:
                logger.warning("organism_core: residue scan failed: %s", exc)
                bundle.add("residue", {"detected": False, "error": str(exc)[:200]})

        check_results: List[CheckResult] = [c.safe_evaluate(bundle) for c in self._checks]

        gating_failure: Optional[Tuple[str, str]] = None
        if self._gating is not None:
            try:
                gating_failure = self._gating.fn(bundle)
            except Exception as exc:
                logger.warning("organism_core: gating evaluator raised: %s", exc)

        verdict = derive_health(check_results, gating_failure=gating_failure)

        workload_flag: Optional[bool] = None
        if self._workload is not None:
            try:
                workload_flag = bool(self._workload(bundle))
            except Exception:
                workload_flag = None

        recommendation = self._recs.recommend(
            state=verdict.state,
            results=check_results,
            green_workload_indicator=workload_flag,
        )

        snapshot = {
            "ok": True,
            "organism": self._organism,
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "health_state": verdict.state.value,
            "current_bottleneck": verdict.bottleneck,
            "next_recommended_action": recommendation,
            "visibility_mismatches": verdict.mismatches,
            "checks": [r.to_dict() for r in check_results],
            "signals": bundle.by_collector,
            "metadata": dict(self._metadata),
        }
        if residue_report is not None:
            snapshot["residue"] = residue_report.to_dict()

        if persist and self._snapshot_path is not None:
            write_snapshot(snapshot, path=self._snapshot_path)

        return snapshot

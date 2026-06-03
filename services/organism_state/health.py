"""Legacy compatibility shim — preserves the dict-based derive_health signature."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from organism_core import HealthState, Severity
from organism_core.health.checks import CheckResult
from organism_core.health.derivation import derive_health as _core_derive

from services.organism_state.recommendations import kyc_recommendations


def derive_health(
    checks: List[Dict[str, Any]],
    *,
    intake: Dict[str, Any],
    storage: Dict[str, Any],
) -> Tuple[str, str, str, List[str]]:
    """Returns (health_state, bottleneck, next_action, mismatches).

    Same contract the old tests use. Built on top of organism_core
    derivation + KYC recommendations.
    """
    results = [
        CheckResult(
            name=c.get("name", ""),
            ok=bool(c.get("ok", True)),
            severity=Severity.coerce(c.get("severity", "info")),
            detail=str(c.get("detail", "")),
            evidence=dict(c.get("evidence") or {}),
        )
        for c in checks
    ]

    gating = None
    if storage.get("environment") == "production" and not storage.get("durable_storage_configured", False):
        gating = ("durable_storage_not_configured", "KYC_DATA missing in production")

    verdict = _core_derive(results, gating_failure=gating)
    workload = int(intake.get("queue_depth", 0)) > 0

    recs = kyc_recommendations()
    if gating is not None:
        action = "Set KYC_DATA env var in Render to point to the mounted persistent disk (e.g. /var/data)."
    else:
        action = recs.recommend(
            state=verdict.state,
            results=results,
            green_workload_indicator=workload,
            idle_when_green="Idle. Run the acquisition cycle to surface new leads.",
            active_when_green=f"Review the {int(intake.get('queue_depth') or 0)} pending intake(s) in the queue.",
        )

    return (verdict.state.value, verdict.bottleneck, action, list(verdict.mismatches))

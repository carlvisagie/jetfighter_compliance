"""Pure derivation of HealthState + bottleneck from check results.

This module has zero awareness of any domain. It only knows that:
  - any RED check => RED state, bottleneck = first RED check name
  - any AMBER check => AMBER state, bottleneck = first AMBER check name
  - otherwise GREEN, bottleneck = "none"

A caller may pass ``gating_failure`` to force RED with a specific
bottleneck (e.g. KYC uses this for missing durable storage).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from organism_core.health.checks import CheckResult
from organism_core.health.severity import HealthState, Severity


@dataclass
class HealthVerdict:
    state: HealthState
    bottleneck: str
    mismatches: List[str]

    def as_tuple(self) -> Tuple[str, str, List[str]]:
        return (self.state.value, self.bottleneck, list(self.mismatches))


def derive_health(
    results: List[CheckResult],
    *,
    gating_failure: Optional[Tuple[str, str]] = None,
) -> HealthVerdict:
    """Reduce check results to a single HealthVerdict.

    Args:
      results: ordered list of check outcomes.
      gating_failure: optional (bottleneck_name, detail) — if set, the
        verdict is forced to RED with this bottleneck regardless of
        check results. Used by domains to encode a non-negotiable
        prerequisite (e.g. missing durable storage in KYC).

    Returns:
      HealthVerdict
    """
    mismatches: List[str] = []
    first_red: Optional[CheckResult] = None
    first_amber: Optional[CheckResult] = None

    for r in results:
        sev = Severity.coerce(r.severity)
        if sev is Severity.RED:
            mismatches.append(r.name)
            if first_red is None:
                first_red = r
        elif sev is Severity.AMBER:
            mismatches.append(r.name)
            if first_amber is None:
                first_amber = r

    if gating_failure is not None:
        bottleneck, _ = gating_failure
        return HealthVerdict(HealthState.RED, bottleneck, [bottleneck] + mismatches)

    if first_red is not None:
        return HealthVerdict(HealthState.RED, first_red.name, mismatches)
    if first_amber is not None:
        return HealthVerdict(HealthState.AMBER, first_amber.name, mismatches)
    return HealthVerdict(HealthState.GREEN, "none", [])

"""RecommendationRegistry — map check_name (or fallback rules) to an action.

A recommendation can be a static string or a callable that receives the
check result and returns a string. This lets a domain customize action
text based on the actual evidence.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from organism_core.health.checks import CheckResult
from organism_core.health.severity import HealthState, Severity

ActionFn = Callable[[CheckResult], str]
ActionEntry = Union[str, ActionFn]


class RecommendationRegistry:
    """Maps check.name -> action (string or callable)."""

    def __init__(
        self,
        *,
        idle_action: str = "Idle. No work pending.",
        active_action: str = "Review the queue and process pending items.",
        fallback: str = "Investigate the failing check.",
    ) -> None:
        self._by_check: Dict[str, ActionEntry] = {}
        self._idle = idle_action
        self._active = active_action
        self._fallback = fallback

    def register(self, check_name: str, action: ActionEntry) -> "RecommendationRegistry":
        self._by_check[check_name] = action
        return self

    def register_many(self, actions: Dict[str, ActionEntry]) -> "RecommendationRegistry":
        for k, v in actions.items():
            self.register(k, v)
        return self

    def action_for_check(self, result: CheckResult) -> str:
        entry = self._by_check.get(result.name)
        if entry is None:
            return self._fallback
        if callable(entry):
            try:
                return str(entry(result))
            except Exception:
                return self._fallback
        return str(entry)

    def recommend(
        self,
        *,
        state: HealthState,
        results: List[CheckResult],
        idle_when_green: Optional[str] = None,
        active_when_green: Optional[str] = None,
        green_workload_indicator: Optional[bool] = None,
    ) -> str:
        """Pick the right recommendation for the overall state."""
        if state is HealthState.GREEN:
            idle = idle_when_green or self._idle
            active = active_when_green or self._active
            if green_workload_indicator is None:
                return active
            return active if green_workload_indicator else idle

        for r in results:
            sev = Severity.coerce(r.severity)
            if state is HealthState.RED and sev is Severity.RED:
                return self.action_for_check(r)
        for r in results:
            sev = Severity.coerce(r.severity)
            if state is HealthState.AMBER and sev is Severity.AMBER:
                return self.action_for_check(r)

        return self._fallback

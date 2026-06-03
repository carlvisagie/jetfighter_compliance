"""Check protocol — domain-specific reconciliation."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from organism_core.awareness.signals import SignalBundle
from organism_core.health.severity import Severity

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Outcome of a single Check."""

    name: str
    ok: bool
    severity: Severity = Severity.INFO
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


class Check(ABC):
    """Base class for a reconciliation check.

    A Check is a pure function from SignalBundle -> CheckResult. It
    should never raise; if it cannot evaluate, return a result with
    ``ok=True`` and ``severity=INFO`` plus a detail explaining why.
    """

    #: Unique stable name. Used as the key in RecommendationRegistry.
    name: str = ""

    @abstractmethod
    def evaluate(self, signals: SignalBundle) -> CheckResult:
        """Return a CheckResult given the signal bundle."""

    def safe_evaluate(self, signals: SignalBundle) -> CheckResult:
        try:
            result = self.evaluate(signals)
            if not isinstance(result, CheckResult):
                raise TypeError(f"{self.name}.evaluate must return CheckResult")
            return result
        except Exception as exc:
            logger.warning("organism_core: check %s raised: %s", self.name or type(self).__name__, exc)
            return CheckResult(
                name=self.name or type(self).__name__,
                ok=False,
                severity=Severity.AMBER,
                detail=f"check raised: {type(exc).__name__}: {str(exc)[:200]}",
                evidence={},
            )

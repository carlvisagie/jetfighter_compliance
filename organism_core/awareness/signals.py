"""Signal collection — the read side of awareness.

A SignalCollector reads from one source of truth (database, filesystem,
queue, HTTP API, git, etc.) and returns a dict of named values. The
core does not interpret these values — that is the job of Checks.

A SignalBundle is the merged output of all collectors, namespaced by
collector name to prevent key collisions across domains.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SignalCollector(ABC):
    """Base class for a single source-of-truth reader.

    Subclasses implement :meth:`collect`. The core wraps every call in a
    try/except so one failing collector never breaks the snapshot.
    """

    #: Unique stable name used as the namespace key in SignalBundle.
    name: str = ""

    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict of named signals."""

    def safe_collect(self) -> Dict[str, Any]:
        try:
            data = self.collect() or {}
            if not isinstance(data, dict):
                raise TypeError(f"{self.name}.collect() must return a dict")
            return data
        except Exception as exc:  # never let one collector break the rest
            logger.warning("organism_core: collector %s failed: %s", self.name or type(self).__name__, exc)
            return {"_collector_error": str(exc)[:200]}


@dataclass
class SignalBundle:
    """Namespaced container of signals from every collector."""

    by_collector: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add(self, name: str, signals: Dict[str, Any]) -> None:
        self.by_collector[name] = signals

    def get(self, collector: str, key: str, default: Any = None) -> Any:
        return self.by_collector.get(collector, {}).get(key, default)

    def section(self, collector: str) -> Dict[str, Any]:
        return self.by_collector.get(collector, {})

    def flat(self) -> Dict[str, Any]:
        """Flat view (collector.key) — useful for snapshot serialization."""
        out: Dict[str, Any] = {}
        for cname, data in self.by_collector.items():
            for k, v in data.items():
                out[f"{cname}.{k}"] = v
        return out

    def collector_names(self) -> List[str]:
        return list(self.by_collector.keys())

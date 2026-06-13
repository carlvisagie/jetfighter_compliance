"""Whole-organism observability dashboard — telemetry aggregation and recommendations."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from ..defensive_wiring import safe_write_text
from typing import Any, Dict, List, Optional

from .entity_graph import memory_dir, utc_now
from .telemetry import load_telemetry

SYSTEM_PATTERNS_FILE = "system_patterns.json"

DEFAULT_PATTERNS: Dict[str, Any] = {
    "version": 1,
    "updated_utc": "",
    "subsystem_health": {},
    "repeated_failures": [],
    "reliability_patterns": {},
    "conversion_patterns": {},
    "failure_patterns": {},
    "bottleneck_patterns": {},
    "best_paths": {},
    "recommended_improvements": [],
}


def _patterns_path(base: Optional[Path] = None) -> Path:
    return memory_dir(base) / SYSTEM_PATTERNS_FILE


def load_system_patterns(base: Optional[Path] = None) -> Dict[str, Any]:
    path = _patterns_path(base)
    if not path.exists():
        return dict(DEFAULT_PATTERNS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_PATTERNS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_PATTERNS)


def save_system_patterns(state: Dict[str, Any], base: Optional[Path] = None) -> None:
    state["updated_utc"] = utc_now()
    _patterns_path(base).write_text(json.dumps(state, indent=2), encoding="utf-8")


def refresh_system_patterns_from_telemetry(
    *,
    window: int = 500,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rows = load_telemetry(limit=window, base=base)
    state = load_system_patterns(base)

    by_sub: Dict[str, Dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0, "events": 0})
    fail_counter: Counter = Counter()
    durations: Dict[str, List[int]] = defaultdict(list)

    for r in rows:
        sub = r.get("subsystem", "unknown")
        by_sub[sub]["events"] += 1
        if r.get("success"):
            by_sub[sub]["ok"] += 1
        else:
            by_sub[sub]["fail"] += 1
            fail_counter[f"{sub}:{r.get('event_type')}"] += 1
        dm = r.get("duration_ms")
        if dm is not None:
            durations[sub].append(int(dm))

    health = {}
    for sub, counts in by_sub.items():
        total = counts["events"] or 1
        rate = counts["ok"] / total
        health[sub] = {
            "success_rate": round(rate, 3),
            "events": counts["events"],
            "failures": counts["fail"],
            "status": "healthy" if rate >= 0.9 else ("degraded" if rate >= 0.7 else "unhealthy"),
        }
        if sub in durations and durations[sub]:
            avg_ms = sum(durations[sub]) / len(durations[sub])
            if avg_ms > 5000:
                state.setdefault("bottleneck_patterns", {})[sub] = {
                    "avg_duration_ms": int(avg_ms),
                    "hint": "Investigate slow operations",
                }

    state["subsystem_health"] = health
    state["repeated_failures"] = [
        {"key": k, "count": c, "suggestion": f"Review {k} failures"}
        for k, c in fail_counter.most_common(15)
        if c >= 2
    ]
    state["failure_patterns"] = {
        k: c for k, c in fail_counter.most_common(20)
    }
    state["reliability_patterns"] = {
        sub: h["success_rate"] for sub, h in health.items()
    }

    conv_hints = []
    for r in rows:
        if r.get("subsystem") == "acquisition" and r.get("event_type") == "high_priority_lead_found":
            conv_hints.append(r.get("lead_id"))
    if conv_hints:
        state["best_paths"] = {
            "acquisition_high_priority_refs": list(dict.fromkeys(conv_hints))[-10:],
        }

    recs = []
    for rf in state["repeated_failures"][:5]:
        recs.append(rf.get("suggestion", ""))
    if health.get("email", {}).get("status") == "unhealthy":
        recs.append("Email transport reliability low — verify SMTP or disable until configured.")
    if health.get("job_queue", {}).get("failures", 0) > 3:
        recs.append("Background job failures elevated — inspect data/jobs retry queue.")
    state["recommended_improvements"] = [x for x in recs if x][:10]

    save_system_patterns(state, base)
    return state


def get_observability_dashboard(
    *,
    telemetry_limit: int = 100,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    refresh_system_patterns_from_telemetry(base=base)
    patterns = load_system_patterns(base)
    recent = load_telemetry(limit=telemetry_limit, base=base)

    invisible = [
        {"id": "organism_sqlite", "reason": "Legacy sqlite subsystem — not telemetry-wired"},
    ]
    try:
        import importlib.util

        if importlib.util.find_spec("autonomous_content_creator") is None:
            invisible.append(
                {
                    "id": "content_creator",
                    "reason": "No content creator module in repo — hooks ready via telemetry API",
                }
            )
    except Exception:
        invisible.append({"id": "content_creator", "reason": "Content creator not present"})

    subsystems_observed = len(patterns.get("subsystem_health", {}))
    verdict = "organism_observable"
    if subsystems_observed < 4:
        verdict = "not_observable"
    elif patterns.get("repeated_failures") or any(
        h.get("status") == "unhealthy" for h in patterns.get("subsystem_health", {}).values()
    ):
        verdict = "partially_observable"

    return {
        "audit_utc": utc_now(),
        "verdict": verdict,
        "recent_telemetry": recent,
        "subsystem_health": patterns.get("subsystem_health", {}),
        "repeated_failures": patterns.get("repeated_failures", []),
        "learning_patterns": {
            "reliability": patterns.get("reliability_patterns", {}),
            "failures": patterns.get("failure_patterns", {}),
            "bottlenecks": patterns.get("bottleneck_patterns", {}),
            "best_paths": patterns.get("best_paths", {}),
        },
        "recommended_improvements": patterns.get("recommended_improvements", []),
        "still_invisible": invisible,
        "telemetry_count": len(recent),
    }


def emit_content_creator_telemetry(
    event_type: str,
    *,
    success: bool = True,
    asset_id: str = "",
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    """Hook for future content creator — emits into central telemetry only."""
    from .telemetry import emit_telemetry

    emit_telemetry(
        "content_creator",
        event_type,
        severity="info" if success else "error",
        artifact_id=asset_id,
        success=success,
        message=message,
        metadata=metadata,
        base=base,
    )

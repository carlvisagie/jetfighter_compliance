"""Central learning state — signal effectiveness across vessels."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .entity_graph import memory_dir, utc_now

LEARNING_FILE = "learning_state.json"

DEFAULT_STATE = {
    "version": 1,
    "updated_utc": "",
    "signal_effectiveness": {},
    "conversion_counts": {
        "lead_to_inquiry": 0,
        "inquiry_to_intake": 0,
        "intake_to_evidence": 0,
        "lead_failed": 0,
    },
    "paperwork_patterns": {
        "high_fit": [],
        "low_fit": [],
    },
    "segment_performance": {},
}


def _path(base: Optional[Path] = None) -> Path:
    return memory_dir(base) / LEARNING_FILE


def load_learning_state(base: Optional[Path] = None) -> Dict[str, Any]:
    path = _path(base)
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_STATE)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_STATE)


def save_learning_state(state: Dict[str, Any], base: Optional[Path] = None) -> None:
    state["updated_utc"] = utc_now()
    _path(base).write_text(json.dumps(state, indent=2), encoding="utf-8")


def record_learning_signal(
    signal_key: str,
    outcome: str,
    *,
    success: bool = True,
    segment: str = "",
    paperwork_hint: str = "",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    state = load_learning_state(base)
    eff = state.setdefault("signal_effectiveness", {})
    bucket = eff.setdefault(signal_key, {"success": 0, "fail": 0, "outcomes": []})
    if success:
        bucket["success"] += 1
    else:
        bucket["fail"] += 1
    bucket["outcomes"] = (bucket.get("outcomes") or [])[-19:] + [outcome]

    counts = state.setdefault("conversion_counts", {})
    if outcome in counts:
        counts[outcome] += 1
    elif outcome == "lead_failed":
        counts["lead_failed"] = counts.get("lead_failed", 0) + 1

    if segment:
        seg = state.setdefault("segment_performance", {})
        sp = seg.setdefault(segment, {"success": 0, "fail": 0})
        if success:
            sp["success"] += 1
        else:
            sp["fail"] += 1

    if paperwork_hint:
        key = "high_fit" if success else "low_fit"
        patterns = state.setdefault("paperwork_patterns", {}).setdefault(key, [])
        if paperwork_hint not in patterns:
            patterns.append(paperwork_hint)
        state["paperwork_patterns"][key] = patterns[-30:]

    save_learning_state(state, base)
    return state


def get_learning_summary(base: Optional[Path] = None) -> Dict[str, Any]:
    return load_learning_state(base)

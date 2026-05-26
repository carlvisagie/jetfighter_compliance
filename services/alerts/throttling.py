"""Severity-aware cooldown throttling."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

from .paths import THROTTLES_JSON, ensure_alerts_dir
from .severity import Severity

# Cooldown seconds by severity
DEFAULT_COOLDOWNS: Dict[str, int] = {
    "INFO": 3600,
    "IMPORTANT": 1800,
    "HIGH": 600,
    "CRITICAL": 300,
}

# Failure-type alerts use longer cooldowns
FAILURE_COOLDOWNS: Dict[str, int] = {
    "smtp_failure": 1800,
    "scheduler_failure": 3600,
    "telemetry_failure": 1800,
    "acquisition_connector_failure": 3600,
    "memory_bridge_failure": 3600,
    "upload_failure": 900,
    "continuation_token_failure": 900,
    "qr_generation_failure": 1800,
}


def _path() -> Path:
    return ensure_alerts_dir() / THROTTLES_JSON


def _load() -> dict:
    p = _path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(data: dict) -> None:
    ensure_alerts_dir()
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def cooldown_for(event_type: str, severity: Severity) -> int:
    if event_type in FAILURE_COOLDOWNS:
        return FAILURE_COOLDOWNS[event_type]
    return DEFAULT_COOLDOWNS.get(severity.name, 1800)


def is_throttled(throttle_key: str, event_type: str, severity: Severity) -> bool:
    if not throttle_key:
        return False
    data = _load()
    entry = data.get(throttle_key) or {}
    last = float(entry.get("ts", 0))
    cd = int(entry.get("cooldown", cooldown_for(event_type, severity)))
    return (time.time() - last) < cd


def mark_sent(throttle_key: str, event_type: str, severity: Severity) -> None:
    if not throttle_key:
        return
    data = _load()
    data[throttle_key] = {
        "ts": time.time(),
        "cooldown": cooldown_for(event_type, severity),
        "event_type": event_type,
    }
    cutoff = time.time() - 7 * 86400
    data = {k: v for k, v in data.items() if float(v.get("ts", 0)) > cutoff}
    _save(data)

"""Data paths for operational alerts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _data_root() -> Path:
    from ..config import DATA

    return DATA


def alerts_root() -> Path:
    return _data_root() / "alerts"


def ensure_alerts_dir() -> Path:
    root = alerts_root()
    (root / "digests").mkdir(parents=True, exist_ok=True)
    return root


HISTORY_JSONL = "history.jsonl"
DEDUPE_JSON = "dedupe.json"
THROTTLES_JSON = "throttles.json"
FAILURES_JSONL = "failures.jsonl"
CONFIG_JSON = "config.json"
STATE_JSON = "state.json"


def config_path() -> Path:
    return ensure_alerts_dir() / CONFIG_JSON


def load_config() -> Dict[str, Any]:
    path = config_path()
    defaults: Dict[str, Any] = {
        "email_enabled": True,
        "telegram_enabled": True,
        "high_fit_threshold": 75,
        "qualification_threshold": 75,
        "abandonment_hours": 24,
        "quiet_hours_start": 22,
        "quiet_hours_end": 7,
        "digest_daily_hour_utc": 8,
        "digest_weekly_dow": 0,
        "digest_weekly_hour_utc": 9,
        "min_severity_telegram": "IMPORTANT",
        "min_severity_email": "HIGH",
        "critical_bypass_quiet_hours": True,
    }
    import os

    env_map = {
        "email_enabled": os.getenv("ALERT_EMAIL_ENABLED", "true").lower() == "true",
        "telegram_enabled": os.getenv("ALERT_TELEGRAM_ENABLED", "true").lower() == "true",
        "high_fit_threshold": int(os.getenv("ALERT_HIGH_FIT_THRESHOLD", "75")),
        "qualification_threshold": int(os.getenv("ALERT_QUALIFICATION_THRESHOLD", "75")),
        "abandonment_hours": int(os.getenv("ALERT_ABANDONMENT_HOURS", "24")),
        "quiet_hours_start": int(os.getenv("ALERT_QUIET_HOURS_START", "22")),
        "quiet_hours_end": int(os.getenv("ALERT_QUIET_HOURS_END", "7")),
        "digest_daily_hour_utc": int(os.getenv("ALERT_DIGEST_DAILY_HOUR_UTC", "8")),
        "digest_weekly_hour_utc": int(os.getenv("ALERT_DIGEST_WEEKLY_HOUR_UTC", "9")),
    }
    defaults.update(env_map)
    if path.is_file():
        try:
            file_cfg = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(file_cfg, dict):
                defaults.update(file_cfg)
        except json.JSONDecodeError:
            pass
    return defaults


def save_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    cfg = load_config()
    cfg.update({k: v for k, v in updates.items() if v is not None})
    ensure_alerts_dir()
    config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def load_state() -> Dict[str, Any]:
    path = ensure_alerts_dir() / STATE_JSON
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    path = ensure_alerts_dir() / STATE_JSON
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")

"""Deduplication windows — prevent alert storms."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .paths import DEDUPE_JSON, ensure_alerts_dir


def _path() -> Path:
    return ensure_alerts_dir() / DEDUPE_JSON


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


def is_duplicate(dedupe_key: str, window_seconds: int) -> bool:
    if not dedupe_key or window_seconds <= 0:
        return False
    data = _load()
    last = float(data.get(dedupe_key, 0))
    now = time.time()
    if now - last < window_seconds:
        return True
    return False


def mark_seen(dedupe_key: str) -> None:
    if not dedupe_key:
        return
    data = _load()
    data[dedupe_key] = time.time()
    # prune old entries (>7 days)
    cutoff = time.time() - 7 * 86400
    data = {k: v for k, v in data.items() if float(v) > cutoff}
    _save(data)


def clear_key(dedupe_key: str) -> None:
    data = _load()
    data.pop(dedupe_key, None)
    _save(data)

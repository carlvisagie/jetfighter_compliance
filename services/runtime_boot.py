"""Production boot control — safe mode, deferred schedulers, startup logging."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from .production import is_production

logger = logging.getLogger(__name__)

_BOOT_LOG: list[Dict[str, Any]] = []


def is_safe_mode() -> bool:
    return os.getenv("KYC_SAFE_MODE", "").strip().lower() in ("1", "true", "yes", "on")


def defer_scheduler_seconds() -> float:
    """Give Render health checks time to pass before background work."""
    if is_safe_mode():
        return 0.0
    raw = os.getenv("KYC_DEFER_SCHEDULER_SEC", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    if is_production():
        return 8.0
    return 0.0


def heavy_schedulers_enabled() -> bool:
    """Acquisition, compliance intel, reddit cron — off in safe mode."""
    return not is_safe_mode()


def log_boot(component: str, status: str, detail: str = "") -> None:
    entry = {"component": component, "status": status, "detail": detail}
    _BOOT_LOG.append(entry)
    msg = f"[boot] {component}: {status}"
    if detail:
        msg += f" ({detail})"
    logger.info(msg)


def boot_log_snapshot() -> Dict[str, Any]:
    return {
        "safe_mode": is_safe_mode(),
        "defer_scheduler_sec": defer_scheduler_seconds(),
        "heavy_schedulers": heavy_schedulers_enabled(),
        "entries": list(_BOOT_LOG),
    }


def safe_mode_blocked_detail(feature: str) -> str:
    return f"KYC_SAFE_MODE is enabled — {feature} is disabled until safe mode is turned off."

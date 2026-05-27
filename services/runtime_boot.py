"""Production boot control — safe mode, scheduler kill-switch, startup env audit."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

from .production import is_production

logger = logging.getLogger(__name__)

_BOOT_LOG: list[Dict[str, Any]] = []
_ENV_SNAPSHOT: Dict[str, str] = {}


def _env_raw(name: str) -> str | None:
    return os.getenv(name)


def is_safe_mode() -> bool:
    """
    Safe/minimal boot. Production defaults to safe when KYC_SAFE_MODE is unset
    (Render Dashboard often lacks vars that exist only in render.yaml).
  Explicit opt-out: KYC_SAFE_MODE=false
    """
    raw = _env_raw("KYC_SAFE_MODE")
    norm = str(raw if raw is not None else "").strip().lower()
    if norm in ("0", "false", "no", "off"):
        return False
    if norm in ("1", "true", "yes", "on"):
        return True
    if is_production():
        return True
    return False


def schedulers_enabled() -> bool:
    """Stabilization: schedulers OFF unless explicitly KYC_SCHEDULERS_ENABLED=true."""
    return str(_env_raw("KYC_SCHEDULERS_ENABLED") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def defer_scheduler_seconds() -> float:
    return 0.0


def heavy_schedulers_enabled() -> bool:
    return schedulers_enabled() and not is_safe_mode()


def audit_boot_env() -> Dict[str, str]:
    """Log critical env vars at boot (stdout + logger + boot log)."""
    global _ENV_SNAPSHOT
    keys = (
        "KYC_SAFE_MODE",
        "KYC_REQUIRE_SAFE_MODE",
        "KYC_SCHEDULERS_ENABLED",
        "ENVIRONMENT",
        "RENDER_EXTERNAL_URL",
    )
    snapshot: Dict[str, str] = {}
    for key in keys:
        val = _env_raw(key)
        snapshot[key] = val if val is not None else "<unset>"
        line = f"BOOT ENV {key}={snapshot[key]}"
        print(line, flush=True)
        logger.warning(line)
        log_boot("env", key, snapshot[key])
    snapshot["safe_mode_effective"] = str(is_safe_mode())
    snapshot["schedulers_enabled"] = str(schedulers_enabled())
    log_boot("env", "safe_mode_effective", snapshot["safe_mode_effective"])
    log_boot("env", "schedulers_enabled", snapshot["schedulers_enabled"])
    _ENV_SNAPSHOT = dict(snapshot)
    return snapshot


def enforce_safe_mode_required() -> None:
    """Crash fast if production expects safe mode but env disables it."""
    if str(_env_raw("KYC_REQUIRE_SAFE_MODE") or "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    if is_safe_mode():
        log_boot("safe_mode", "enforced", "ok")
        return
    msg = (
        f"KYC_REQUIRE_SAFE_MODE is set but effective safe_mode=False "
        f"(KYC_SAFE_MODE={_env_raw('KYC_SAFE_MODE')!r}). "
        "Set KYC_SAFE_MODE=true in Render Dashboard → Environment."
    )
    logger.critical(msg)
    print(msg, file=sys.stderr, flush=True)
    raise RuntimeError(msg)


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
        "schedulers_enabled": schedulers_enabled(),
        "env": dict(_ENV_SNAPSHOT),
        "entries": list(_BOOT_LOG),
    }


def safe_mode_blocked_detail(feature: str) -> str:
    return f"KYC_SAFE_MODE is enabled — {feature} is disabled during stabilization."

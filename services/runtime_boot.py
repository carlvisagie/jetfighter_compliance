"""Production boot control — safe mode, module flags, scheduler kill-switch."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse

from .production import is_production

logger = logging.getLogger(__name__)

_BOOT_LOG: list[Dict[str, Any]] = []
_ENV_SNAPSHOT: Dict[str, str] = {}


def _env_raw(name: str) -> str | None:
    return os.getenv(name)


def _env_truthy(name: str, *, default: bool) -> bool:
    raw = _env_raw(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def is_safe_mode() -> bool:
    raw = _env_raw("KYC_SAFE_MODE")
    norm = str(raw if raw is not None else "").strip().lower()
    if norm in ("0", "false", "no", "off"):
        return False
    if norm in ("1", "true", "yes", "on"):
        return True
    if is_production():
        return True
    return False


def manual_acquisition_enabled() -> bool:
    return _env_truthy("KYC_ENABLE_MANUAL_ACQUISITION", default=not is_production())


def knowledge_overlay_enabled() -> bool:
    return _env_truthy("KYC_ENABLE_KNOWLEDGE_OVERLAY", default=not is_production())


def observability_enabled() -> bool:
    return _env_truthy("KYC_ENABLE_OBSERVABILITY", default=not is_production())


def schedulers_enabled() -> bool:
    return _env_truthy("KYC_SCHEDULERS_ENABLED", default=False)


def defer_scheduler_seconds() -> float:
    return 0.0


def heavy_schedulers_enabled() -> bool:
    return schedulers_enabled() and not is_safe_mode()


def organ_scheduler_enabled(organ: str) -> bool:
    """Per-organ kill switch.

    Default: ON. Set ``KYC_DISABLE_<ORGAN>=true`` to disable a single organ
    without taking the whole scheduler down. Operator can isolate a sick
    organ from Render Dashboard env without a code change.
    """
    if not organ:
        return False
    env_name = f"KYC_DISABLE_{organ.upper()}"
    return not _env_truthy(env_name, default=False)


def should_pause_module(module: str) -> bool:
    """True when module must not run (safe mode or feature flag off)."""
    if is_safe_mode():
        return True
    if module == "acquisition":
        return not manual_acquisition_enabled()
    if module == "knowledge":
        return not knowledge_overlay_enabled()
    if module == "observability":
        return not observability_enabled()
    return False


def module_pause_payload(module: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "safe_mode": is_safe_mode(),
        "paused": True,
        "message": "Module paused during stabilization",
        "module": module,
    }


def module_pause_response(module: str) -> Optional[JSONResponse]:
    if not should_pause_module(module):
        return None
    return JSONResponse(status_code=200, content=module_pause_payload(module))


def audit_boot_env() -> Dict[str, str]:
    global _ENV_SNAPSHOT
    keys = (
        "KYC_SAFE_MODE",
        "KYC_REQUIRE_SAFE_MODE",
        "KYC_SCHEDULERS_ENABLED",
        "KYC_ENABLE_MANUAL_ACQUISITION",
        "KYC_ENABLE_KNOWLEDGE_OVERLAY",
        "KYC_ENABLE_OBSERVABILITY",
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
    if not _env_truthy("KYC_REQUIRE_SAFE_MODE", default=False):
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
        "manual_acquisition": manual_acquisition_enabled(),
        "knowledge_overlay": knowledge_overlay_enabled(),
        "observability": observability_enabled(),
        "env": dict(_ENV_SNAPSHOT),
        "entries": list(_BOOT_LOG),
    }


def safe_mode_blocked_detail(feature: str) -> str:
    return f"Module paused during stabilization ({feature})."

"""Build identity — safe for public exposure (no secrets, no filesystem paths)."""
from __future__ import annotations

import os
from typing import Any, Dict


def git_commit() -> str:
    for key in ("KYC_GIT_COMMIT", "RENDER_GIT_COMMIT", "GIT_COMMIT"):
        val = os.getenv(key, "").strip()
        if val:
            return val[:40]
    return "unknown"


def service_name() -> str:
    return "jetfighter-compliance"


def public_build_info() -> Dict[str, Any]:
    from .production import is_production

    return {
        "service": service_name(),
        "git_commit": git_commit(),
        "environment": "production" if is_production() else os.getenv("ENVIRONMENT", "development"),
    }


def operator_build_info(*, data_root: str) -> Dict[str, Any]:
    info = public_build_info()
    info["data_root"] = data_root
    return info

"""Build identity — safe for public exposure (no secrets, no filesystem paths).

Resolution order for `git_commit()`:

  1. `/app/.build_commit` — baked at Docker build time from `git rev-parse
     HEAD`. This is the authoritative source on Render because the live
     service was hand-created (not Blueprint-managed) and therefore
     RENDER_GIT_COMMIT is NOT injected at runtime. See Dockerfile.

  2. Project-relative `.build_commit` next to this file's repo root —
     same content when running via plain `python server.py` in a checked-
     out tree.

  3. Env vars (KYC_GIT_COMMIT / RENDER_GIT_COMMIT / GIT_COMMIT) — kept
     for managed-Render or CI environments that DO inject them, and as
     an emergency override.

  4. `unknown` — caller can detect this state and fail any verification
     workflow that needs to prove "the deploy I just pushed is live".
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

_CANDIDATE_PATHS = (
    Path("/app/.build_commit"),
    Path(__file__).resolve().parent.parent / ".build_commit",
)


def _read_baked_commit() -> str:
    for p in _CANDIDATE_PATHS:
        try:
            if p.is_file():
                val = p.read_text(encoding="utf-8", errors="ignore").strip()
                if val and val != "unknown":
                    return val[:40]
        except OSError:
            continue
    return ""


def git_commit() -> str:
    baked = _read_baked_commit()
    if baked:
        return baked
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

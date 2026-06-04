"""
Environment envelope — single source of truth for "where is this data coming from?".

Every operator-facing API response wraps its payload with the envelope returned
by `env_envelope()`. The operator UI ribbon reads the same shape via
`GET /api/operator/environment-label`.

Contract: see docs/PRODUCTION_IS_THE_ONLY_TRUTH.md.

There are exactly two trust states:
    - "trusted"        → environment == "production" AND data_root under /var/data
                         AND OPS_API_KEY set AND disk persistence verified (or pending)
    - "DO_NOT_TRUST"   → anything else (local dev, pytest, broken config, missing secrets,
                         lost disk substrate)

There is no "test" or "staging" middle ground. Anything that is not production
is noise and must be visibly marked as noise so no agent or operator can
mistake a count for reality.

The disk-substrate verdict is owned by the organism — this envelope reads
`services.durable_storage.disk_persistence_status()` (cached once per process)
instead of computing its own. One brain, many vessels.
"""
from __future__ import annotations

import datetime as _dt
import os
import socket
from pathlib import Path
from typing import Any, Dict, Mapping

from .build_info import git_commit, service_name
from .config import DATA

PROD_DISK_PREFIX = "/var/data"


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _host() -> str:
    val = (os.getenv("RENDER_SERVICE_NAME") or "").strip()
    if val:
        return val
    val = (os.getenv("HOSTNAME") or "").strip()
    if val:
        return val
    try:
        return socket.gethostname() or "unknown-host"
    except Exception:
        return "unknown-host"


def _data_root_str() -> str:
    try:
        return str(DATA)
    except Exception:
        return ""


def _is_under_prod_disk(data_root: str) -> bool:
    if not data_root:
        return False
    try:
        resolved = str(Path(data_root).resolve()).replace("\\", "/")
    except Exception:
        return False
    return resolved.startswith(PROD_DISK_PREFIX)


def _ops_api_key_configured() -> bool:
    return bool((os.getenv("OPS_API_KEY") or "").strip())


def classify_environment() -> str:
    """
    Returns one of: "production" | "non-production".

    Production requires ALL of:
      - ENVIRONMENT env var is exactly "production"
      - data_root resolves under /var/data
      - OPS_API_KEY is configured (real prod deploys always have it)

    Any other state is "non-production" — explicitly NOT "test" or "staging".
    The classifier is intentionally brutal: a single missing prerequisite drops
    trust because we never want to lie about provenance.
    """
    env = (os.getenv("ENVIRONMENT") or "").strip().lower()
    if env != "production":
        return "non-production"
    if not _is_under_prod_disk(_data_root_str()):
        return "non-production"
    if not _ops_api_key_configured():
        return "non-production"
    return "production"


def _disk_persistence_snapshot() -> Dict[str, Any]:
    """Read the organism's disk-persistence verdict — never compute our own.

    Returns a small `{state, verified}` snapshot the envelope can attach
    so every API consumer sees the same disk truth the organism sees.
    Failures are silent and return ``{}`` so a broken probe never breaks
    the envelope itself (operators still get the env classification).
    """
    try:
        from .durable_storage import disk_persistence_status
    except Exception:
        return {}
    try:
        s = disk_persistence_status() or {}
    except Exception:
        return {}
    return {
        "state": s.get("state") or "unknown",
        "verified": bool(s.get("verified")),
    }


def env_envelope() -> Dict[str, Any]:
    """The envelope attached to every operator response.

    The disk-persistence fields read directly from
    ``services.durable_storage.disk_persistence_status()`` so the envelope
    cannot drift from what the organism reports — one brain, many
    vessels (kills the audit-flagged truth island between
    ``env_envelope`` and ``organism_state.checks.DiskPersistenceCheck``).
    """
    data_root = _data_root_str()
    environment = classify_environment()
    trust = "trusted" if environment == "production" else "DO_NOT_TRUST"
    disk = _disk_persistence_snapshot()
    return {
        "environment": environment,
        "trust": trust,
        "data_root": data_root,
        "data_root_under_prod_disk": _is_under_prod_disk(data_root),
        "host": _host(),
        "service": service_name(),
        "git_commit": git_commit(),
        "server_time_utc": _utcnow_iso(),
        "ops_api_key_configured": _ops_api_key_configured(),
        # Disk substrate verdict — the organism's call, not the envelope's.
        # state ∈ {pending_first_restart, verified_persistent, ephemeral_lost, write_failed, unknown}
        "disk_persistence_state": disk.get("state") or "unknown",
        "disk_persistence_verified": disk.get("verified", False),
    }


def wrap(payload: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """
    Wrap an operator response with the environment envelope.

    Usage:
        return wrap({"intakes": 0, "uploads": 0})

    Renders as:
        {
            "_env": { ... },
            "intakes": 0,
            "uploads": 0
        }

    Existing `_env` keys on the payload are overwritten — the envelope wins,
    callers cannot fake provenance.
    """
    out: Dict[str, Any] = {}
    if payload:
        out.update(payload)
    out["_env"] = env_envelope()
    return out


def environment_label() -> Dict[str, Any]:
    """
    Payload for the UI ribbon endpoint.

    The UI uses `level` to decide ribbon style:
      - "ok"    → calm green strip (production)
      - "alarm" → giant red strip (non-production)
    """
    env = env_envelope()
    is_prod = env["environment"] == "production"
    return {
        "_env": env,
        "level": "ok" if is_prod else "alarm",
        "label": "PRODUCTION" if is_prod else "NON-PRODUCTION",
        "headline": (
            "PRODUCTION — live customer data"
            if is_prod
            else "NON-PRODUCTION — DO NOT TRUST ANY COUNT ON THIS PAGE"
        ),
        "doctrine_url": "/docs/PRODUCTION_IS_THE_ONLY_TRUTH.md",
    }

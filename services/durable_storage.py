"""Production durable data policy — customer intake must not use ephemeral disk."""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException

from .config import DATA, ROOT
from .production import is_production

logger = logging.getLogger(__name__)

# Process start time — used to decide whether the on-disk birth marker
# predates this container. If yes, the disk survived a restart and is real.
_PROCESS_START_MONOTONIC = time.monotonic()
_PROCESS_START_UTC = _dt.datetime.now(_dt.timezone.utc)

DISK_BIRTH_MARKER_FILENAME = ".kyc_disk_birth"
# A marker must be at least this many seconds older than the process for us to
# declare "the disk survived a restart". Tuned high enough to defeat clock
# skew on first boot, low enough to flip to verified after one redeploy.
DISK_PERSISTENCE_MIN_AGE_SECONDS = 60

# Process-level cache: disk persistence is determined ONCE per process
# (first probe) and held for the rest of the process lifetime. The disk
# doesn't unmount mid-process; if it does, the next restart classifies it.
_DISK_PERSISTENCE_CACHE: Optional[Dict[str, Any]] = None

_PUBLIC_UPLOAD_DETAIL = (
    "Paperwork upload is not available right now. "
    "Please contact support@keepyourcontracts.com and we will help you submit securely."
)


def repo_default_data_dir() -> Path:
    return (ROOT / "data").resolve()


def kyc_data_env_value() -> Optional[str]:
    return (os.getenv("KYC_DATA") or "").strip() or None


def resolved_kyc_data_path() -> Optional[Path]:
    raw = kyc_data_env_value()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def is_data_root_ephemeral_in_production() -> bool:
    """True when production is using the repo-local data dir (lost on Render redeploy)."""
    if not is_production():
        return False
    try:
        return active_data_root() == repo_default_data_dir()
    except OSError:
        return True


def is_durable_storage_configured() -> bool:
    """
    Durable storage requires explicit KYC_DATA to a writable path.
    In production the path must not be the default repo data/ directory.
    """
    path = resolved_kyc_data_path()
    if path is None:
        return False
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".kyc_storage_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        return False
    if is_production() and path == repo_default_data_dir():
        return False
    return True


def intake_pipeline_enabled() -> bool:
    from services.intake.mode import is_intake_mode

    return is_intake_mode()


def founding_pilot_intake_enabled() -> bool:
    """Deprecated alias — use intake_pipeline_enabled."""
    return intake_pipeline_enabled()


def _writable_data_root(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".kyc_storage_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def canonical_storage_ready() -> bool:
    """All environments: customer paperwork requires a writable non-ephemeral data root."""
    if is_durable_storage_configured():
        return True
    root = active_data_root()
    if root == repo_default_data_dir():
        return False
    return _writable_data_root(root)


# ─── Disk persistence proof ────────────────────────────────────────────────
#
# The mount probe ("can we write to /var/data?") only proves the path is
# writable — NOT that it's a real persistent disk. On 2026-06-04 the
# production service ran for weeks with KYC_DATA=/var/data and no disk
# attached; every upload was destroyed at the next deploy. The mount probe
# happily reported "ok" because writes worked inside the ephemeral container
# filesystem.
#
# This guardrail writes a birth-marker on first boot. On any subsequent
# boot, the marker's age (vs the current process start time) reveals
# whether the disk survived a restart. If the disk got destroyed and
# recreated between deploys, the marker is gone and we know to alarm.
#
# States returned by `disk_persistence_status`:
#   verified_persistent      Marker exists and is older than this process →
#                            disk survived at least one restart. TRUSTED.
#   pending_first_restart    Marker exists but was written during this
#                            container's lifetime → first ever boot on this
#                            disk; we cannot verify persistence until the
#                            next restart. Uploads ALLOWED (otherwise we
#                            block forever on a fresh disk), env envelope
#                            reports "pending".
#   ephemeral_lost           Marker was missing on boot AND we just created
#                            a fresh one → either first ever boot OR the
#                            previous marker was destroyed. Treated same as
#                            pending_first_restart for blocking purposes;
#                            env envelope records the loss for forensics.
#   unconfigured             KYC_DATA not set / not writable / repo default.
#                            No disk to verify.
#   write_failed             Marker write raised OSError. DO NOT TRUST.


def _disk_birth_marker_path() -> Optional[Path]:
    if not is_durable_storage_configured():
        return None
    root = active_data_root()
    return root / DISK_BIRTH_MARKER_FILENAME


def _utc_iso(dt: _dt.datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_birth_marker(path: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    birth_str = data.get("birth_utc")
    if not isinstance(birth_str, str):
        return None
    try:
        birth_dt = _dt.datetime.fromisoformat(birth_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if birth_dt.tzinfo is None:
        birth_dt = birth_dt.replace(tzinfo=_dt.timezone.utc)
    data["_birth_dt"] = birth_dt
    return data


def _write_birth_marker(path: Path) -> Optional[Dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "birth_utc": _utc_iso(_PROCESS_START_UTC),
        "birth_disk_id": uuid.uuid4().hex,
        "born_by_pid": os.getpid(),
        "born_by_host": os.getenv("RENDER_SERVICE_NAME") or os.getenv("HOSTNAME") or "",
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.critical("[disk_persistence] failed to write birth marker at %s: %s", path, exc)
        return None
    return payload


def _compute_disk_persistence_status() -> Dict[str, Any]:
    """Determine current persistence state by reading / writing the birth marker."""
    marker = _disk_birth_marker_path()
    process_start_iso = _utc_iso(_PROCESS_START_UTC)
    base: Dict[str, Any] = {
        "verified": False,
        "state": "unconfigured",
        "marker_path": str(marker) if marker else None,
        "process_started_utc": process_start_iso,
    }
    if marker is None:
        return base
    existed_before = marker.is_file()
    existing = _read_birth_marker(marker) if existed_before else None
    if existing is None:
        # Marker missing or corrupt — write a new one. This is either the
        # first ever boot of this disk OR the disk got reset (we cannot tell
        # which without history). Either way, persistence is not yet proven.
        created = _write_birth_marker(marker)
        if created is None:
            return {**base, "state": "write_failed"}
        return {
            **base,
            "state": "ephemeral_lost" if existed_before else "pending_first_restart",
            "marker_birth_utc": created["birth_utc"],
            "marker_birth_disk_id": created["birth_disk_id"],
            "verified": False,
        }
    # Marker existed and parsed. Compare birth time to process start.
    birth_dt: _dt.datetime = existing["_birth_dt"]
    age_seconds = (_PROCESS_START_UTC - birth_dt).total_seconds()
    if age_seconds >= DISK_PERSISTENCE_MIN_AGE_SECONDS:
        return {
            **base,
            "state": "verified_persistent",
            "verified": True,
            "marker_birth_utc": _utc_iso(birth_dt),
            "marker_birth_disk_id": existing.get("birth_disk_id"),
            "age_before_process_seconds": int(age_seconds),
        }
    return {
        **base,
        "state": "pending_first_restart",
        "verified": False,
        "marker_birth_utc": _utc_iso(birth_dt),
        "marker_birth_disk_id": existing.get("birth_disk_id"),
        "age_before_process_seconds": int(age_seconds),
    }


def disk_persistence_status(*, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Single source of truth: is the disk really persistent?

    Cached once per process — the disk substrate doesn't change mid-process;
    a mount loss means restart, and the new process classifies fresh.

    Test fixtures can call `reset_disk_persistence_cache_for_tests()` between
    test cases to re-probe a swapped tmp dir.
    """
    global _DISK_PERSISTENCE_CACHE
    if _DISK_PERSISTENCE_CACHE is not None and not force_refresh:
        return dict(_DISK_PERSISTENCE_CACHE)
    result = _compute_disk_persistence_status()
    _DISK_PERSISTENCE_CACHE = result
    _emit_disk_persistence_telemetry(result)
    return dict(result)


def disk_persistence_verified() -> bool:
    return disk_persistence_status().get("verified") is True


def reset_disk_persistence_cache_for_tests() -> None:
    """Test-only helper. Production callers must NEVER call this."""
    global _DISK_PERSISTENCE_CACHE
    _DISK_PERSISTENCE_CACHE = None


def _emit_disk_persistence_telemetry(status: Dict[str, Any]) -> None:
    """
    Nervous-system signal: every process classifies its disk substrate once at
    boot. Telemetry row carries enough provenance to forensically trace any
    future data-loss incident back to the offending deploy.
    """
    state = status.get("state") or "unknown"
    severity = "error" if state in ("ephemeral_lost", "write_failed", "unconfigured") else "info"
    if state == "pending_first_restart":
        severity = "warning"
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "storage",
            "disk_persistence_probe",
            severity=severity,
            message=f"disk_persistence={state}",
            metadata={
                "state": state,
                "verified": bool(status.get("verified")),
                "marker_birth_utc": status.get("marker_birth_utc"),
                "marker_birth_disk_id": status.get("marker_birth_disk_id"),
                "age_before_process_seconds": status.get("age_before_process_seconds"),
                "process_started_utc": status.get("process_started_utc"),
                "marker_path": status.get("marker_path"),
                "learning_goal": "Detect ephemeral-disk regressions before customer data loss",
            },
        )
    except Exception as exc:  # never let telemetry failure block the probe
        logger.warning("[disk_persistence] telemetry emit failed: %s", exc)
    if state == "ephemeral_lost":
        _record_disk_persistence_integrity_incident(status)


def _record_disk_persistence_integrity_incident(status: Dict[str, Any]) -> None:
    """
    Immune-system response: when the marker disappeared between this and the
    previous boot, a real data-loss event almost certainly occurred. Append a
    SEV-1 incident to the canonical integrity log so the forensic engine
    surfaces it and uploads are blocked until reviewed.
    """
    try:
        root = active_data_root()
        intakes_root = root / "intakes"
        intakes_root.mkdir(parents=True, exist_ok=True)
        incidents = intakes_root / "integrity_incidents.jsonl"
        record = {
            "incident_type": "disk_persistence_lost",
            "severity": "sev_1",
            "observed_at_utc": _utc_iso(_PROCESS_START_UTC),
            "summary": (
                "Disk birth marker was missing on this boot although storage is "
                "configured. Previous boot's customer data may have been lost."
            ),
            "marker_path": status.get("marker_path"),
            "new_marker_birth_utc": status.get("marker_birth_utc"),
            "new_marker_birth_disk_id": status.get("marker_birth_disk_id"),
            "process_started_utc": status.get("process_started_utc"),
            "doctrine": "docs/KYC_UPLOAD_IMMUTABILITY_PROOF.md",
        }
        with incidents.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        logger.critical(
            "[SEV-1] disk_persistence_lost — marker missing on boot at %s",
            status.get("marker_path"),
        )
    except OSError as exc:
        logger.critical(
            "[SEV-1] disk_persistence_lost AND incident-log write failed: %s", exc
        )


def intake_upload_allowed() -> bool:
    if not intake_pipeline_enabled():
        return False
    if not canonical_storage_ready():
        return False
    # Immune system: a lost-marker boot means previous customer data was
    # destroyed. Refuse new uploads until an operator has reviewed the
    # integrity incident and confirmed the disk is healthy.
    if disk_persistence_status().get("state") == "ephemeral_lost":
        return False
    return True


def founding_pilot_upload_allowed() -> bool:
    """Deprecated alias — use intake_upload_allowed."""
    return intake_upload_allowed()


def upload_block_reason() -> Optional[str]:
    if not intake_pipeline_enabled():
        return "intake_pipeline_disabled"
    if not canonical_storage_ready():
        if not kyc_data_env_value() and active_data_root() == repo_default_data_dir():
            return "durable_storage_required_set_KYC_DATA"
        if not kyc_data_env_value():
            return "KYC_DATA_not_configured"
        path = resolved_kyc_data_path()
        if path is None:
            return "KYC_DATA_invalid"
        if path == repo_default_data_dir():
            return "KYC_DATA_points_to_ephemeral_repo_data"
        if not is_durable_storage_configured():
            return "KYC_DATA_not_writable"
    if disk_persistence_status().get("state") == "ephemeral_lost":
        return "disk_persistence_lost"
    return None


def log_storage_boot_status() -> None:
    reason = upload_block_reason()
    allowed = intake_upload_allowed()
    msg = (
        f"data_root={active_data_root()} "
        f"durable_storage_configured={is_durable_storage_configured()} "
        f"intake_uploads_enabled={allowed}"
    )
    if reason:
        msg += f" upload_block_reason={reason}"
    logger.info("[storage] %s", msg)
    try:
        from services.runtime_boot import log_boot

        log_boot(
            "storage",
            "ok" if allowed or not is_production() else "blocked",
            msg[:240],
        )
    except Exception:
        pass
    if is_production() and not allowed:
        logger.critical("[storage] intake uploads disabled in production: %s", reason)


def _log_upload_blocked(reason: str) -> None:
    logger.critical("intake_upload_blocked reason=%s data_root=%s", reason, DATA)
    try:
        from services.runtime_boot import log_boot

        log_boot("intake_upload", "blocked", reason[:200])
    except Exception:
        pass
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(
            "intake",
            "intake_storage_unavailable",
            message=reason,
            metadata={"data_root": str(DATA.resolve()), "reason": reason},
        )
    except Exception:
        pass


def require_intake_upload_allowed() -> None:
    reason = upload_block_reason()
    if reason is None:
        return
    _log_upload_blocked(reason)
    raise HTTPException(
        status_code=503,
        detail=_PUBLIC_UPLOAD_DETAIL,
        headers={"X-KYC-Error-Code": "durable_storage_required"},
    )


def require_founding_pilot_upload_allowed() -> None:
    """Deprecated alias — use require_intake_upload_allowed."""
    require_intake_upload_allowed()


def reject_demo_order_in_production(order_id: str) -> None:
    oid = (order_id or "").strip().upper()
    if not is_production():
        return
    if oid.startswith("CP-DEMO") or oid.startswith("DEMO-") or oid.startswith("TEST-"):
        raise HTTPException(
            status_code=403,
            detail="Demo and test project creation is disabled in production.",
        )


def active_data_root() -> Path:
    """Live data root (honors KYC_DATA env even when config.DATA was imported earlier)."""
    from services.config import _resolve_data_root

    return _resolve_data_root()


def get_storage_status() -> Dict[str, Any]:
    reason = upload_block_reason()
    kyc = resolved_kyc_data_path()
    root = active_data_root()
    allowed = intake_upload_allowed()
    from services.intake.durable_root import mount_status_for_operator

    mount = mount_status_for_operator()
    persistence = disk_persistence_status()
    return {
        "ok": True,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "data_root": str(root),
        "kyc_data_env": kyc_data_env_value(),
        "kyc_data_path": str(kyc) if kyc else None,
        "durable_storage_configured": is_durable_storage_configured(),
        "data_root_ephemeral_in_production": is_data_root_ephemeral_in_production(),
        "disk_persistence": persistence,
        "disk_persistence_verified": persistence.get("verified") is True,
        "mount_probe": mount,
        "intake_pipeline_enabled": intake_pipeline_enabled(),
        "intake_uploads_enabled": allowed,
        "founding_pilot_intake_enabled": intake_pipeline_enabled(),
        "founding_pilot_uploads_enabled": allowed,
        "upload_block_reason": reason,
        "operator_message": (
            None
            if allowed
            else "Durable paperwork storage not configured — uploads disabled."
        ),
    }

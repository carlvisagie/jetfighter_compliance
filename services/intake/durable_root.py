"""Durable disk root — prove Render mount and reject ephemeral writes."""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from services.durable_storage import active_data_root, is_durable_storage_configured, kyc_data_env_value
from services.defensive_wiring import safe_write_text, safe_write_json

logger = logging.getLogger(__name__)

MOUNT_PROBE_FILENAME = ".kyc_durable_mount_probe"
_MOUNT_PROBE_ID: Optional[str] = None


def durable_data_root() -> Path:
    return active_data_root().resolve()


def mount_probe_path() -> Path:
    return durable_data_root() / MOUNT_PROBE_FILENAME


def initialize_mount_probe() -> Dict[str, Any]:
    """Write persistent probe under KYC_DATA — survives container restart if disk is mounted."""
    global _MOUNT_PROBE_ID
    root = durable_data_root()
    root.mkdir(parents=True, exist_ok=True)
    probe = mount_probe_path()
    if probe.is_file():
        try:
            _MOUNT_PROBE_ID = probe.read_text(encoding="utf-8").strip().splitlines()[0]
            return {
                "ok": True,
                "action": "existing",
                "probe_path": str(probe),
                "probe_id": _MOUNT_PROBE_ID,
                "data_root": str(root),
            }
        except OSError:
            pass
    probe_id = f"kyc-mount-{uuid.uuid4().hex}"
    payload = f"{probe_id}\nwritten_under={root}\n"
    tmp = probe.with_suffix(".tmp")
    safe_write_text(

        tmp,

        payload,

        component="intake_durable",

        context="durable root"

    )
    _fsync_path(tmp)
    tmp.replace(probe)
    _fsync_path(probe)
    _MOUNT_PROBE_ID = probe_id
    logger.info("[durable_root] mount probe written path=%s id=%s", probe, probe_id)
    return {
        "ok": True,
        "action": "created",
        "probe_path": str(probe),
        "probe_id": probe_id,
        "data_root": str(root),
    }


def verify_mount_probe() -> Dict[str, Any]:
    root = durable_data_root()
    probe = mount_probe_path()
    out: Dict[str, Any] = {
        "data_root": str(root),
        "kyc_data_env": kyc_data_env_value(),
        "durable_storage_configured": is_durable_storage_configured(),
        "probe_path": str(probe),
        "probe_exists": probe.is_file(),
        "probe_id": None,
        "ok": False,
    }
    if probe.is_file():
        try:
            first_line = probe.read_text(encoding="utf-8").splitlines()[0].strip()
            out["probe_id"] = first_line
            out["ok"] = bool(first_line)
        except OSError as exc:
            out["error"] = str(exc)
    else:
        out["error"] = "mount_probe_missing"
    return out


def assert_durable_write_path(path: Path) -> Path:
    """
    Every intake artifact (uploads, audit, index, quarantine, ledger) must resolve under KYC_DATA.
    """
    root = durable_data_root()
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        msg = f"Refusing write outside durable root: {resolved} (required under {root})"
        logger.critical("[SEV-1] %s", msg)
        raise ValueError(msg)
    mount = verify_mount_probe()
    if not mount.get("probe_exists"):
        initialize_mount_probe()
        mount = verify_mount_probe()
    if not mount.get("probe_exists"):
        msg = f"Durable mount probe missing at {mount_probe_path()} — refusing write to {resolved}"
        logger.critical("[SEV-1] %s", msg)
        raise ValueError(msg)
    return resolved


def mount_status_for_operator() -> Dict[str, Any]:
    probe = verify_mount_probe()
    root = durable_data_root()
    intakes = root / "intakes"
    quarantine = root / "intake_quarantine"
    ledger = intakes / "hash_ledger.jsonl"
    return {
        **probe,
        "intakes_root": str(intakes.resolve()) if intakes.exists() else str(intakes),
        "quarantine_root": str(quarantine.resolve()) if quarantine.exists() else str(quarantine),
        "hash_ledger_path": str(ledger),
        "writes_must_be_under": str(root),
    }


def _fsync_path(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    try:
        parent = path.parent
        if parent.is_dir():
            fd = os.open(str(parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except OSError:
        pass

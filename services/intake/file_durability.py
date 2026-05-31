"""Per-upload durability markers — prove path, size, hash at write time."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .durable_root import assert_durable_write_path, durable_data_root
from .storage import atomic_write_json, intake_dir

DURABILITY_SIDECAR_SUFFIX = ".durability.json"


def is_upload_payload_file(name: str) -> bool:
    return bool(name) and not name.endswith(DURABILITY_SIDECAR_SUFFIX)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def durability_sidecar_path(upload_file: Path) -> Path:
    return upload_file.parent / f"{upload_file.name}{DURABILITY_SIDECAR_SUFFIX}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def durable_write_upload_payload(dest: Path, data: bytes) -> Dict[str, Any]:
    """
    Durable upload payload write — must complete before customer success.

    Sequence: write temp → fsync temp → rename → fsync file → fsync parent dir
    → reopen → re-hash → verify size.
    """
    from .storage import _fsync_written_file, assert_canonical_write_path

    assert_canonical_write_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected_sha = sha256_bytes(data)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    _fsync_written_file(tmp)
    tmp.replace(dest)
    _fsync_written_file(dest)

    resolved = dest.resolve()
    if not resolved.is_file():
        raise OSError(f"Durable upload missing after rename: {resolved}")
    if resolved.stat().st_size != len(data):
        raise OSError(f"Post-write size mismatch for {resolved}")

    with resolved.open("rb") as fh:
        read_back = fh.read()
    actual_sha = sha256_bytes(read_back)
    if actual_sha != expected_sha:
        raise OSError(f"Post-write hash mismatch for {resolved}")
    if read_back != data:
        raise OSError(f"Post-write content mismatch for {resolved}")

    return {
        "absolute_path": str(resolved),
        "size_bytes": len(data),
        "sha256": actual_sha,
    }


def write_upload_with_durability_markers(
    dest: Path,
    data: bytes,
    *,
    intake_id: str,
) -> Dict[str, Any]:
    """
    Write upload bytes under canonical uploads/ with fsync + sidecar + read-back hash verify.
    """
    written = durable_write_upload_payload(dest, data)
    resolved = dest.resolve()
    sha = written["sha256"]

    sidecar = {
        "intake_id": intake_id,
        "filename": dest.name,
        "absolute_path": str(resolved),
        "data_root": str(durable_data_root()),
        "size_bytes": len(data),
        "sha256": sha,
        "written_at_utc": _utc_now(),
    }
    sc_path = durability_sidecar_path(resolved)
    assert_durable_write_path(sc_path)
    atomic_write_json(sc_path, sidecar)
    return sidecar


def list_durability_sidecars(intake_id: str) -> List[Dict[str, Any]]:
    uploads = intake_dir(intake_id) / "uploads"
    if not uploads.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for path in sorted(uploads.glob(f"*{DURABILITY_SIDECAR_SUFFIX}")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["_sidecar_path"] = str(path.resolve())
                out.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def sidecar_orphan_reasons(intake_id: str) -> List[str]:
    """Sidecar exists but payload file missing — SEV-1 data loss."""
    uploads = intake_dir(intake_id) / "uploads"
    if not uploads.is_dir():
        return []
    reasons: List[str] = []
    for sc in list_durability_sidecars(intake_id):
        name = str(sc.get("filename") or "")
        if not name:
            continue
        payload = uploads / name
        if not payload.is_file():
            reasons.append(f"durability_sidecar_without_file:{name}")
    return reasons


def verify_upload_file_durable(intake_id: str, filename: str) -> Dict[str, Any]:
    """Operator/diagnostic: path, size, sha256, existence."""
    dest = intake_dir(intake_id) / "uploads" / filename
    sc_path = durability_sidecar_path(dest)
    exists = dest.is_file()
    out: Dict[str, Any] = {
        "intake_id": intake_id,
        "filename": filename,
        "absolute_path": str(dest.resolve()),
        "exists": exists,
        "size_bytes": dest.stat().st_size if exists else 0,
        "sha256": sha256_file(dest) if exists else None,
        "sidecar_exists": sc_path.is_file(),
        "sidecar_path": str(sc_path.resolve()),
    }
    if sc_path.is_file():
        try:
            out["sidecar"] = json.loads(sc_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            out["sidecar"] = None
    return out

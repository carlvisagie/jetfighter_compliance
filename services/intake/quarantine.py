"""Immutable quarantine mirror — second durable copy per intake upload batch."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .storage import intake_dir

logger = logging.getLogger(__name__)


def assert_quarantine_write_path(path: Path) -> None:
    root = quarantine_root().resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Refusing non-quarantine write: {resolved} (required under {root})")

MANIFEST_FILENAME = "quarantine_manifest.json"


def _data_root() -> Path:
    from .storage import _data_root as storage_root

    return storage_root()


def quarantine_root() -> Path:
    p = _data_root() / "intake_quarantine"
    p.mkdir(parents=True, exist_ok=True)
    return p


def quarantine_intake_dir(intake_id: str) -> Path:
    if not intake_id.startswith("FB-") or ".." in intake_id or "/" in intake_id:
        raise ValueError("Invalid intake_id")
    p = quarantine_root() / intake_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mirror_intake_uploads(intake_id: str) -> Dict[str, Any]:
    """
    Copy canonical uploads/ into intake_quarantine/{id}/uploads/ with manifest.
    Idempotent — refreshes manifest hashes on each successful upload gate pass.
    """
    canonical_uploads = intake_dir(intake_id) / "uploads"
    if not canonical_uploads.is_dir():
        return {"ok": False, "error": "no_uploads_dir", "intake_id": intake_id}

    qdir = quarantine_intake_dir(intake_id)
    quarantine_uploads = qdir / "uploads"
    quarantine_uploads.mkdir(parents=True, exist_ok=True)

    mirrored: List[Dict[str, Any]] = []
    for src in sorted(canonical_uploads.iterdir()):
        if not src.is_file():
            continue
        dest = quarantine_uploads / src.name
        assert_quarantine_write_path(dest)
        shutil.copy2(src, dest)
        mirrored.append(
            {
                "name": src.name,
                "size": src.stat().st_size,
                "sha256": _sha256_file(dest),
            }
        )

    manifest = {
        "intake_id": intake_id,
        "mirrored_at_utc": _utc_now(),
        "canonical_uploads": str(canonical_uploads.resolve()),
        "quarantine_uploads": str(quarantine_uploads.resolve()),
        "files": mirrored,
        "file_count": len(mirrored),
    }
    manifest_path = qdir / MANIFEST_FILENAME
    assert_quarantine_write_path(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Quarantine mirror intake=%s files=%s", intake_id, len(mirrored))
    return {
        "ok": True,
        "intake_id": intake_id,
        "mirrored_file_count": len(mirrored),
        "quarantine_dir": str(qdir.resolve()),
        "manifest_path": str(manifest_path.resolve()),
    }


def load_quarantine_manifest(intake_id: str) -> Dict[str, Any] | None:
    path = quarantine_intake_dir(intake_id) / MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None

"""Founding beta filesystem storage — canonical paths and intake inventory."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _data_root() -> Path:
    """Always resolve live config.DATA (supports KYC_DATA + test monkeypatch)."""
    from services import config

    return config.DATA

PENDING_REVIEW_STATUSES = frozenset(
    {
        "pending_review",
        "pending",
        "received",
        "submitted",
        "needs_info",
        "high_value",
        "new",
        "",
    }
)


def founding_beta_root() -> Path:
    p = _data_root() / "founding_beta"
    p.mkdir(parents=True, exist_ok=True)
    return p


def intakes_root() -> Path:
    p = founding_beta_root() / "intakes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def index_jsonl() -> Path:
    p = founding_beta_root() / "intakes_index.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def intake_dir(intake_id: str) -> Path:
    if not intake_id.startswith("FB-") or ".." in intake_id or "/" in intake_id:
        raise ValueError("Invalid intake_id")
    return intakes_root() / intake_id


def intake_json_path(intake_id: str) -> Path:
    return intake_dir(intake_id) / "intake.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize_review_status(status: Optional[str]) -> str:
    s = (status or "").strip().lower()
    if s in ("archived", "approved"):
        return s
    if s in ("received", "submitted", "new", ""):
        return "pending_review"
    if not s:
        return "pending_review"
    return s


def is_pending_review(status: Optional[str]) -> bool:
    s = normalize_review_status(status)
    return s not in ("archived", "approved")


def normalize_intake_record(data: Dict[str, Any], *, intake_id: str = "") -> Dict[str, Any]:
    out = dict(data)
    if intake_id:
        out["intake_id"] = intake_id
    rs = normalize_review_status(out.get("review_status") or out.get("status"))
    out["review_status"] = rs
    out["status"] = out.get("status") or rs
    if "created_at_utc" not in out and out.get("created_utc"):
        out["created_at_utc"] = out["created_utc"]
    return out


def recover_intake_from_disk(intake_id: str) -> Dict[str, Any]:
    """Rebuild intake metadata from directory + uploads when intake.json is missing."""
    idir = intake_dir(intake_id)
    if not idir.is_dir():
        raise FileNotFoundError(intake_id)
    uploads = idir / "uploads"
    files: List[Dict[str, Any]] = []
    total_bytes = 0
    if uploads.is_dir():
        for p in sorted(uploads.iterdir()):
            if not p.is_file():
                continue
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            total_bytes += size
            files.append(
                {
                    "name": p.name,
                    "size": size,
                    "ext": p.suffix.lower(),
                    "uploaded_at_utc": _utc_now(),
                    "recovered": True,
                }
            )
    try:
        mtime = datetime.fromtimestamp(idir.stat().st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except OSError:
        mtime = _utc_now()
    return normalize_intake_record(
        {
            "intake_id": intake_id,
            "created_at_utc": mtime,
            "updated_at_utc": _utc_now(),
            "status": "pending_review",
            "review_status": "pending_review",
            "company": "",
            "email": "",
            "phone": "",
            "context": "",
            "deadline": "",
            "urgent": False,
            "files": files,
            "file_count": len(files),
            "total_bytes": total_bytes,
            "recovered_from_disk": True,
        },
        intake_id=intake_id,
    )


def load_intake_record(intake_id: str, *, persist_recovery: bool = True) -> Dict[str, Any]:
    """Load intake.json; recover from uploads/ when missing or corrupt."""
    path = intake_json_path(intake_id)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                rec = normalize_intake_record(data, intake_id=intake_id)
                if rec.get("review_status") != data.get("review_status"):
                    atomic_write_json(path, rec)
                return rec
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("intake.json corrupt for %s: %s", intake_id, exc)
    rec = recover_intake_from_disk(intake_id)
    if persist_recovery:
        try:
            atomic_write_json(path, rec)
            append_index_row(
                {
                    "intake_id": intake_id,
                    "created_at_utc": rec.get("created_at_utc"),
                    "status": rec.get("review_status"),
                    "company": rec.get("company"),
                    "email": rec.get("email"),
                    "urgent": rec.get("urgent"),
                    "file_count": rec.get("file_count", 0),
                    "recovered": True,
                }
            )
        except OSError as exc:
            logger.warning("Could not persist recovered intake %s: %s", intake_id, exc)
    return rec


def list_intake_ids(*, limit: int = 500) -> List[str]:
    """Filesystem source of truth — all FB-* intake directories, newest first."""
    root = intakes_root()
    if not root.is_dir():
        return []
    entries: List[tuple[float, str]] = []
    for path in root.iterdir():
        if not path.is_dir() or not path.name.startswith("FB-"):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        entries.append((mtime, path.name))
    entries.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in entries[:limit]]


def index_intake_ids(*, tail_lines: int = 500) -> List[str]:
    from ..lazy_io import iter_jsonl_lines

    seen: List[str] = []
    found: Set[str] = set()
    for row in iter_jsonl_lines(index_jsonl(), tail_lines=tail_lines):
        iid = row.get("intake_id")
        if iid and str(iid) not in found:
            found.add(str(iid))
            seen.append(str(iid))
    return seen


def all_intake_ids(*, limit: int = 500) -> List[str]:
    """Merge filesystem + index; filesystem wins ordering for discovery."""
    merged: List[str] = []
    seen: Set[str] = set()
    for iid in list_intake_ids(limit=limit):
        if iid not in seen:
            seen.add(iid)
            merged.append(iid)
    for iid in index_intake_ids(tail_lines=max(limit, 500)):
        if iid not in seen:
            seen.add(iid)
            merged.append(iid)
    return merged[:limit]


def append_index_row(row: Dict[str, Any]) -> None:
    path = index_jsonl()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sync_index_from_filesystem(*, max_rows: int = 200) -> int:
    """Append index rows for on-disk intakes missing from index tail."""
    tail = set(index_intake_ids(tail_lines=max_rows * 2))
    added = 0
    for iid in list_intake_ids(limit=max_rows):
        if iid in tail:
            continue
        try:
            rec = load_intake_record(iid, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        append_index_row(
            {
                "intake_id": iid,
                "created_at_utc": rec.get("created_at_utc"),
                "status": rec.get("review_status"),
                "company": rec.get("company"),
                "email": rec.get("email"),
                "urgent": rec.get("urgent"),
                "file_count": rec.get("file_count", 0),
                "synced_from_disk": True,
            }
        )
        added += 1
    return added


def count_upload_files() -> int:
    total = 0
    for iid in list_intake_ids(limit=300):
        uploads = intake_dir(iid) / "uploads"
        if uploads.is_dir():
            total += sum(1 for p in uploads.iterdir() if p.is_file())
    return total


def intake_diagnostics() -> Dict[str, Any]:
    root = intakes_root()
    ids = list_intake_ids(limit=200)
    pending_ids: List[str] = []
    for iid in ids[:50]:
        try:
            rec = load_intake_record(iid, persist_recovery=False)
            if is_pending_review(rec.get("review_status")):
                pending_ids.append(iid)
        except (FileNotFoundError, ValueError, OSError):
            continue
    return {
        "data_root": str(_data_root().resolve()),
        "founding_beta_root": str(founding_beta_root().resolve()),
        "intakes_root": str(root.resolve()),
        "index_jsonl": str(index_jsonl().resolve()),
        "index_exists": index_jsonl().is_file(),
        "index_size_bytes": index_jsonl().stat().st_size if index_jsonl().is_file() else 0,
        "intake_directories_found": len(ids),
        "intake_ids_sample": ids[:25],
        "pending_intake_ids_sample": pending_ids[:25],
        "upload_files_on_disk": count_upload_files(),
    }

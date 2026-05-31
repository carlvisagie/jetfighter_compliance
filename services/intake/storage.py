"""Founding beta filesystem storage — canonical paths and intake inventory."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _data_root() -> Path:
    """Durable root: KYC_DATA when set; else isolated config.DATA (tests); else live resolver."""
    from services import config
    from services.durable_storage import active_data_root, kyc_data_env_value

    if kyc_data_env_value():
        return active_data_root()
    data = Path(config.DATA).resolve()
    default = (config.ROOT / "data").resolve()
    if data != default:
        return data
    return active_data_root()

PENDING_REVIEW_STATUSES = frozenset(
    {
        "pending_review",
        "pending",
        "received",
        "submitted",
        "needs_info",
        "high_value",
        "partial_upload",
        "abandoned_upload",
        "rejected_files",
        "integrity_failure",
        "verified_complete",
        "new",
        "",
    }
)


def founding_beta_root() -> Path:
    """Deprecated layout root — reads only; new writes use intakes_root()."""
    return _data_root() / "founding_beta"


def intakes_root() -> Path:
    """Canonical customer paperwork storage (not rollout-branded)."""
    p = _data_root() / "intakes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def assert_canonical_write_path(path: Path) -> None:
    """All intake writes must land under canonical intakes/ — never legacy founding_beta/intakes."""
    from .durable_root import assert_durable_write_path

    canonical = intakes_root().resolve()
    resolved = assert_durable_write_path(path)
    if resolved != canonical and canonical not in resolved.parents:
        raise ValueError(
            f"Refusing non-canonical write: {resolved} (required under {canonical})"
        )


def legacy_intakes_roots() -> List[Path]:
    """Read-only legacy trees merged into inventory scans."""
    roots: List[Path] = []
    old = founding_beta_root() / "intakes"
    if old.is_dir():
        roots.append(old)
    return roots


def index_jsonl() -> Path:
    p = intakes_root() / "index.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    legacy = founding_beta_root() / "intakes_index.jsonl"
    if not p.is_file() and legacy.is_file():
        return legacy
    return p


def canonical_intake_dir(intake_id: str) -> Path:
    if not intake_id.startswith("FB-") or ".." in intake_id or "/" in intake_id:
        raise ValueError("Invalid intake_id")
    return intakes_root() / intake_id


def intake_dir(intake_id: str) -> Path:
    """Resolve intake directory — canonical write path; legacy read fallback."""
    canonical = canonical_intake_dir(intake_id)
    if canonical.is_dir():
        return canonical
    for legacy_root in legacy_intakes_roots():
        leg = legacy_root / intake_id
        if leg.is_dir():
            return leg
    return canonical


def ensure_canonical_intake_dir(intake_id: str) -> Path:
    """All writes land on canonical intakes/ tree (migrate legacy dir on first write)."""
    import shutil

    canonical = canonical_intake_dir(intake_id)
    current = intake_dir(intake_id)
    if current.is_dir() and current != canonical and not canonical.exists():
        shutil.copytree(current, canonical)
    canonical.mkdir(parents=True, exist_ok=True)
    return canonical


def intake_json_path(intake_id: str) -> Path:
    return ensure_canonical_intake_dir(intake_id) / "intake.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    assert_canonical_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    _fsync_written_file(tmp)
    tmp.replace(path)
    _fsync_written_file(path)
    if not path.is_file() or path.stat().st_size != len(data):
        raise OSError(f"Durable write verification failed for {path}")


def _fsync_written_file(path: Path) -> None:
    import os

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


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    assert_canonical_write_path(path)
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    encoded = payload.encode("utf-8")
    last_err: Optional[Exception] = None
    for attempt in range(8):
        tmp = path.with_suffix(path.suffix + f".tmp.{attempt}")
        try:
            tmp.write_bytes(encoded)
            _fsync_written_file(tmp)
            tmp.replace(path)
            _fsync_written_file(path)
            if not path.is_file() or path.stat().st_size != len(encoded):
                raise OSError(f"Durable JSON write verification failed for {path}")
            return
        except OSError as exc:
            last_err = exc
            time.sleep(0.02 * (attempt + 1))
        finally:
            if tmp.is_file() and not path.is_file():
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
    if last_err:
        raise last_err


def durable_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    """Append one JSON line with fsync — index, transaction log, hash ledger."""
    import os

    assert_canonical_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass


def normalize_review_status(status: Optional[str]) -> str:
    s = (status or "").strip().lower()
    if s in ("archived", "approved"):
        return s
    if s in ("received", "submitted", "new", ""):
        return "pending_review"
    if s in ("partial_upload", "rejected_files", "integrity_failure", "verified_complete"):
        return s
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
    from .file_durability import is_upload_payload_file

    idir = intake_dir(intake_id)
    if not idir.is_dir():
        raise FileNotFoundError(intake_id)
    uploads = idir / "uploads"
    files: List[Dict[str, Any]] = []
    total_bytes = 0
    if uploads.is_dir():
        for p in sorted(uploads.iterdir()):
            if not p.is_file() or not is_upload_payload_file(p.name):
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
                from .inventory import ghost_intake_reasons

                reasons = ghost_intake_reasons(intake_id, record=rec)
                if reasons:
                    rec["ghost_intake"] = True
                    rec["ghost_intake_reasons"] = reasons
                    if is_pending_review(rec.get("review_status")):
                        rec["review_status"] = "integrity_failure"
                        rec["custody_status"] = "integrity_failure"
                return rec
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("intake.json corrupt for %s: %s", intake_id, exc)
    rec = recover_intake_from_disk(intake_id)
    from .inventory import ghost_intake_reasons

    reasons = ghost_intake_reasons(intake_id, record=rec)
    if reasons:
        rec["ghost_intake"] = True
        rec["ghost_intake_reasons"] = reasons
        rec["review_status"] = "integrity_failure"
        rec["custody_status"] = "integrity_failure"
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


def _collect_intake_dir_entries(roots: List[Path]) -> List[tuple[float, str]]:
    entries: List[tuple[float, str]] = []
    seen: Set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if not path.is_dir() or not path.name.startswith("FB-"):
                continue
            if path.name in seen:
                continue
            seen.add(path.name)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            entries.append((mtime, path.name))
    entries.sort(key=lambda x: x[0], reverse=True)
    return entries


def list_intake_ids(*, limit: int = 500) -> List[str]:
    """Filesystem source of truth — all FB-* intake directories, newest first."""
    roots = [intakes_root(), *legacy_intakes_roots()]
    entries = _collect_intake_dir_entries(roots)
    return [name for _, name in entries[:limit]]


def index_intake_ids(*, tail_lines: int = 500) -> List[str]:
    """Latest row per intake wins (jsonl append log)."""
    order: List[str] = []
    for row in _iter_index_rows(tail_lines=tail_lines):
        iid = str(row.get("intake_id") or "")
        if not iid:
            continue
        if iid in order:
            order.remove(iid)
        order.append(iid)
    return list(reversed(order))


def _iter_index_rows(*, tail_lines: int = 500):
    from ..lazy_io import iter_jsonl_lines

    return iter_jsonl_lines(index_jsonl(), tail_lines=tail_lines)


def latest_index_row(intake_id: str) -> Optional[Dict[str, Any]]:
    row: Optional[Dict[str, Any]] = None
    for candidate in _iter_index_rows(tail_lines=2000):
        if str(candidate.get("intake_id") or "") == intake_id:
            row = candidate
    return row


def upsert_index_row(row: Dict[str, Any]) -> None:
    append_index_row(row)


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
    durable_append_jsonl(index_jsonl(), row)


def max_index_file_count(intake_id: str) -> int:
    """Highest file_count ever recorded in index tail for this intake."""
    best = 0
    for candidate in _iter_index_rows(tail_lines=5000):
        if str(candidate.get("intake_id") or "") != intake_id:
            continue
        best = max(best, int(candidate.get("file_count") or 0))
    return best


def sync_index_from_filesystem(*, max_rows: int = 200) -> int:
    """Append index rows for on-disk intakes missing from index — only if commit complete."""
    from .transactions import intake_commit_complete

    tail = set(index_intake_ids(tail_lines=max_rows * 2))
    added = 0
    for iid in list_intake_ids(limit=max_rows):
        if iid in tail:
            continue
        try:
            rec = load_intake_record(iid, persist_recovery=False)
        except (FileNotFoundError, ValueError, OSError):
            continue
        file_count = int(rec.get("file_count") or 0)
        uploads = intake_dir(iid) / "uploads"
        disk_files = sum(1 for p in uploads.iterdir() if p.is_file()) if uploads.is_dir() else 0
        if disk_files > 0 and not intake_commit_complete(iid):
            continue
        upsert_index_row(
            {
                "intake_id": iid,
                "created_at_utc": rec.get("created_at_utc"),
                "status": rec.get("review_status"),
                "company": rec.get("company"),
                "email": rec.get("email"),
                "urgent": rec.get("urgent"),
                "file_count": rec.get("file_count", 0),
                "synced_from_disk": True,
                "committed": file_count == 0 or intake_commit_complete(iid),
            }
        )
        added += 1
    return added


def count_upload_files() -> int:
    from .inventory import build_intake_inventory

    return int(build_intake_inventory(limit=500).get("upload_files") or 0)


def legacy_migration_status() -> Dict[str, Any]:
    """Read-only scan of legacy founding_beta/ intakes not yet copied to canonical intakes/."""
    legacy_root = founding_beta_root() / "intakes"
    canonical = intakes_root()
    pending: List[str] = []
    if legacy_root.is_dir():
        for path in legacy_root.iterdir():
            if not path.is_dir() or not path.name.startswith("FB-"):
                continue
            if not (canonical / path.name).is_dir():
                pending.append(path.name)
    pending.sort()
    status = {
        "legacy_root": str(legacy_root.resolve()) if legacy_root.is_dir() else None,
        "legacy_intakes_pending_migration": pending[:100],
        "legacy_pending_count": len(pending),
        "migration_complete": len(pending) == 0,
    }
    if pending:
        logger.info(
            "legacy intake migration pending count=%s sample=%s",
            len(pending),
            pending[:5],
        )
    return status


def intake_diagnostics() -> Dict[str, Any]:
    from services.durable_storage import get_storage_status

    from .inventory import build_intake_inventory

    storage = get_storage_status()
    root = intakes_root()
    inv = build_intake_inventory(limit=200)
    ids = list(inv.get("intake_ids_sample") or [])
    pending_ids = list(inv.get("pending_intake_ids_sample") or [])
    write_root = _data_root().resolve()
    read_root = write_root
    mismatch_sample = None
    try:
        from .integrity import latest_integrity_mismatch_from_records

        recs = []
        for iid in ids[:15]:
            try:
                recs.append(load_intake_record(iid, persist_recovery=False))
            except (FileNotFoundError, ValueError, OSError):
                continue
        mismatch_sample = latest_integrity_mismatch_from_records(recs)
    except Exception:
        mismatch_sample = None

    dirs = int(inv.get("intake_directories") or 0)
    files = int(inv.get("upload_files") or 0)

    return {
        "data_root": str(write_root),
        "write_root": str(write_root),
        "read_root": str(read_root),
        "roots_match": write_root == read_root,
        "durable_storage_configured": storage["durable_storage_configured"],
        "intake_uploads_enabled": storage["intake_uploads_enabled"],
        "founding_beta_uploads_enabled": storage.get("founding_beta_uploads_enabled"),
        "upload_block_reason": storage.get("upload_block_reason"),
        "canonical_intakes_root": str(root.resolve()),
        "legacy_intakes_roots": [str(p.resolve()) for p in legacy_intakes_roots()],
        "intakes_root": str(root.resolve()),
        "index_jsonl": str(index_jsonl().resolve()),
        "index_exists": index_jsonl().is_file(),
        "index_size_bytes": index_jsonl().stat().st_size if index_jsonl().is_file() else 0,
        "intake_directories_found": dirs,
        "intake_directories": dirs,
        "intake_ids_sample": ids,
        "pending_intake_ids_sample": pending_ids,
        "pending_review_count": int(inv.get("pending_review_count") or 0),
        "upload_files_on_disk": files,
        "upload_files": files,
        "inventory": inv,
        "latest_integrity_mismatch": mismatch_sample,
        "legacy_migration": legacy_migration_status(),
    }

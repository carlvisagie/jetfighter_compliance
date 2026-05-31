"""Append-only hash ledger under durable intakes root."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .durable_root import assert_durable_write_path
from .storage import intakes_root


def hash_ledger_path() -> Path:
    p = intakes_root() / "hash_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append_hash_ledger(
    *,
    intake_id: str,
    stored_filename: str,
    sha256: str,
    size_bytes: int,
    data_root: str,
    write_path: str,
) -> None:
    path = hash_ledger_path()
    assert_durable_write_path(path)
    row = {
        "at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "intake_id": intake_id,
        "stored_filename": stored_filename,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "data_root": data_root,
        "write_path": write_path,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        try:
            import os

            os.fsync(fh.fileno())
        except OSError:
            pass


def ledger_entries_for_intake(intake_id: str, *, tail: int = 500) -> List[Dict[str, Any]]:
    path = hash_ledger_path()
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in reversed(lines[-tail:]):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("intake_id") == intake_id:
            out.append(row)
    return list(reversed(out))

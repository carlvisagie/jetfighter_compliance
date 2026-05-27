"""Lazy file reads with size guards — no eager large-file loads at import."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

DEFAULT_MAX_READ_BYTES = 5 * 1024 * 1024  # 5MB


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def iter_jsonl_lines(
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
    tail_lines: int = 500,
) -> Iterator[Dict[str, Any]]:
    """Yield JSON objects line-by-line; large files read tail only."""
    if not path.is_file():
        return
    size = file_size(path)
    if size > max_bytes:
        yield from _tail_jsonl(path, tail_lines)
        return
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_jsonl(
    path: Path,
    *,
    limit: int = 300,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in iter_jsonl_lines(path, max_bytes=max_bytes, tail_lines=max(limit, 500)):
        rows.append(row)
        if len(rows) > limit * 2:
            break
    return rows[-limit:]


def _tail_jsonl(path: Path, max_lines: int) -> Iterator[Dict[str, Any]]:
    """Read last N lines of a large jsonl without loading entire file."""
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk = min(size, 256 * 1024)
            f.seek(max(0, size - chunk))
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return
    lines = [ln for ln in data.splitlines() if ln.strip()]
    for line in lines[-max_lines:]:
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def read_text_bounded(path: Path, *, max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
    if not path.is_file():
        return ""
    if file_size(path) > max_bytes:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")

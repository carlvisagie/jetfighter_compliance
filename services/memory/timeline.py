"""Unified timeline per entity_id."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .entity_graph import memory_dir, utc_now

TIMELINES_FILE = "timelines.jsonl"


def append_timeline(
    entity_id: str,
    event_type: str,
    ref_type: str,
    ref_id: str,
    payload: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "entity_id": entity_id,
        "event_type": event_type,
        "ref_type": ref_type,
        "ref_id": ref_id,
        "when_utc": utc_now(),
        "payload": payload or {},
    }
    path = memory_dir(base) / TIMELINES_FILE
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_timeline(entity_id: str = "", base: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = memory_dir(base) / TIMELINES_FILE
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not entity_id or row.get("entity_id") == entity_id:
            rows.append(row)
    return sorted(rows, key=lambda x: x.get("when_utc", ""))

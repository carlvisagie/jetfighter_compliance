"""Acquisition and operational signals indexed to entity_id."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .entity_graph import memory_dir, utc_now

SIGNALS_FILE = "signals.jsonl"


def append_signal(
    entity_id: str,
    signal_type: str,
    source: str,
    strength: float = 1.0,
    payload: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "entity_id": entity_id,
        "signal_type": signal_type,
        "source": source,
        "strength": strength,
        "when_utc": utc_now(),
        "payload": payload or {},
    }
    path = memory_dir(base) / SIGNALS_FILE
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_signals(entity_id: str = "", base: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = memory_dir(base) / SIGNALS_FILE
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not entity_id or row.get("entity_id") == entity_id:
            out.append(row)
    return out

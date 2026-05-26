"""Alert history and central memory linkage."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import FAILURES_JSONL, HISTORY_JSONL, ensure_alerts_dir


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_history(record: Dict[str, Any]) -> Dict[str, Any]:
    ensure_alerts_dir()
    path = ensure_alerts_dir() / HISTORY_JSONL
    rec = dict(record)
    rec.setdefault("alert_id", f"ALT-{uuid.uuid4().hex[:10]}")
    rec.setdefault("when_utc", _utc())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def append_failure(record: Dict[str, Any]) -> None:
    path = ensure_alerts_dir() / FAILURES_JSONL
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**record, "when_utc": _utc()}, ensure_ascii=False) + "\n")


def load_history(*, limit: int = 100, unacknowledged_only: bool = False) -> List[Dict[str, Any]]:
    path = ensure_alerts_dir() / HISTORY_JSONL
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if unacknowledged_only:
        rows = [r for r in rows if not r.get("acknowledged")]
    return rows[-limit:]


def acknowledge_alert(alert_id: str) -> bool:
    path = ensure_alerts_dir() / HISTORY_JSONL
    if not path.is_file():
        return False
    updated = []
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
        if row.get("alert_id") == alert_id:
            row["acknowledged"] = True
            row["acknowledged_utc"] = _utc()
            found = True
        updated.append(json.dumps(row, ensure_ascii=False))
    if found:
        path.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")
    return found


def link_memory(event: str, *, alert_id: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "operational_alerts",
            event,
            severity="info",
            message=alert_id,
            metadata={"alert_id": alert_id, **(metadata or {})},
        )
    except Exception:
        pass
    try:
        from services.memory.central_memory import safe_link_acquisition_organism_event

        safe_link_acquisition_organism_event(
            event,
            metadata={"subsystem": "operational_alerts", "alert_id": alert_id, **(metadata or {})},
        )
    except Exception:
        pass

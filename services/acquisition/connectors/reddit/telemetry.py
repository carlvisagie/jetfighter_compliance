"""Reddit connector telemetry — local jsonl + central organism."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import REDDIT_TELEMETRY_JSONL, ensure_reddit_dir
from ...models import utc_now

SUBSYSTEM = "reddit_acquisition"


def _append_local(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> None:
    path = ensure_reddit_dir(base) / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def emit(
    event_type: str,
    *,
    post_id: str = "",
    subreddit: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    meta = dict(metadata or {})
    if post_id:
        meta["post_id"] = post_id
    if subreddit:
        meta["subreddit"] = subreddit
    rec = {
        "event_id": f"RDT-{uuid.uuid4().hex[:10]}",
        "event_type": event_type,
        "post_id": post_id,
        "subreddit": subreddit,
        "when_utc": utc_now(),
        "metadata": meta,
    }
    _append_local(REDDIT_TELEMETRY_JSONL, rec, base)
    try:
        from services.organism_observability.emit import organism_emit

        organism_emit(SUBSYSTEM, event_type, message=post_id, metadata=meta, base=base)
        aliases = {
            "reddit_discovery_started": "acquisition_cycle_started",
            "reddit_discovery_completed": "acquisition_cycle_completed",
            "reddit_reply_approved": "operator_approved",
            "reddit_post_ignored": "operator_denied",
        }
        if event_type in aliases:
            organism_emit(
                "acquisition_organism",
                aliases[event_type],
                message=post_id,
                metadata={**meta, "source_event": event_type},
                base=base,
            )
        if event_type == "prey_scored":
            organism_emit(
                "acquisition_organism",
                "prey_scored",
                message=post_id,
                metadata={**meta, "connector": SUBSYSTEM},
                base=base,
            )
    except Exception:
        pass
    try:
        from ... import telemetry as acq_telemetry

        acq_telemetry.emit(
            event_type,
            metadata={"connector": SUBSYSTEM, **meta},
            base=base,
        )
    except Exception:
        pass


def load_events(
    *,
    limit: int = 200,
    event_type: str = "",
    base: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = ensure_reddit_dir(base) / REDDIT_TELEMETRY_JSONL
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_type and row.get("event_type") != event_type:
            continue
        rows.append(row)
    return rows[-limit:]

"""Knowledge cockpit telemetry — central memory transport only."""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from services.acquisition.models import utc_now

from .paths import OPERATOR_LEARNING_FILE, RECENT_LOOKUPS_FILE, ensure_knowledge_dir


def _append_jsonl(path, record: Dict[str, Any]) -> None:
    ensure_knowledge_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def emit_knowledge_event(
    event_type: str,
    *,
    concept_id: str = "",
    query: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    meta = metadata or {}
    _append_jsonl(
        RECENT_LOOKUPS_FILE,
        {
            "event_id": f"KL-{uuid.uuid4().hex[:8]}",
            "event_type": event_type,
            "concept_id": concept_id,
            "query": query[:300],
            "when_utc": utc_now(),
            "metadata": meta,
        },
    )
    if event_type in ("concept_explained", "knowledge_lookup", "operator_learning_signal"):
        _append_jsonl(
            OPERATOR_LEARNING_FILE,
            {
                "event_id": f"KOL-{uuid.uuid4().hex[:8]}",
                "event_type": event_type,
                "concept_id": concept_id,
                "when_utc": utc_now(),
                "metadata": meta,
            },
        )
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "knowledge_cockpit",
            event_type,
            message=query[:200] or concept_id,
            metadata={"concept_id": concept_id, **meta},
        )
    except Exception:
        pass
    try:
        from .memory_context import link_operator_learning

        link_operator_learning(event_type, concept_id=concept_id, metadata=meta)
    except Exception:
        pass

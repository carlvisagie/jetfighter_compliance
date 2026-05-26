"""Reddit organism learning — daily incremental updates from outcomes and telemetry."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...models import utc_now
from .paths import (
    EXPERIMENTS_JSONL,
    FAILURES_JSONL,
    LEARNING_STATE_JSON,
    OUTCOMES_JSONL,
    WINNERS_JSONL,
    ensure_reddit_dir,
)


def load_learning_state(base: Optional[Path] = None) -> Dict[str, Any]:
    path = ensure_reddit_dir(base) / LEARNING_STATE_JSON
    defaults: Dict[str, Any] = {
        "version": 1,
        "last_daily_learning_utc": "",
        "default_cooldown_hours": 24,
        "default_follow_up_hours": 48,
        "min_fit_threshold": 50,
        "subreddit_stats": {},
        "wording_winners": {"A": 0, "B": 0},
        "outcome_totals": {
            "operator_approved": 0,
            "operator_denied": 0,
            "uploads_completed": 0,
            "clicks": 0,
            "continuations": 0,
            "moderation_removed": 0,
            "ignored_replies": 0,
        },
    }
    if not path.is_file():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults.update(data)
    except json.JSONDecodeError:
        pass
    return defaults


def save_learning_state(state: Dict[str, Any], base: Optional[Path] = None) -> None:
    path = ensure_reddit_dir(base) / LEARNING_STATE_JSON
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _append_jsonl(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> None:
    path = ensure_reddit_dir(base) / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_outcome(
    event_type: str,
    *,
    post_id: str = "",
    subreddit: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Track moderation, engagement, uploads, denials, etc."""
    rec = {
        "outcome_id": f"RDO-{uuid.uuid4().hex[:8]}",
        "event_type": event_type,
        "post_id": post_id,
        "subreddit": (subreddit or "").lower(),
        "when_utc": utc_now(),
        "metadata": metadata or {},
    }
    _append_jsonl(OUTCOMES_JSONL, rec, base)
    state = load_learning_state(base)
    totals = state.setdefault("outcome_totals", {})
    key = event_type.replace("reddit_", "")
    totals[key] = int(totals.get(key, 0)) + 1
    if subreddit:
        sub_stats = state.setdefault("subreddit_stats", {}).setdefault(subreddit.lower(), {})
        sub_stats[event_type] = int(sub_stats.get(event_type, 0)) + 1
        if event_type == "operator_approved":
            sub_stats["last_approved_utc"] = utc_now()
            sub_stats["operator_approved"] = int(sub_stats.get("operator_approved", 0)) + 1
        elif event_type == "operator_denied":
            sub_stats["operator_denied"] = int(sub_stats.get("operator_denied", 0)) + 1
        elif event_type == "uploads_completed":
            sub_stats["uploads_completed"] = int(sub_stats.get("uploads_completed", 0)) + 1
        elif event_type == "moderation_removed":
            sub_stats["moderation_removed"] = int(sub_stats.get("moderation_removed", 0)) + 1
            sub_stats["cooldown_hours"] = min(168, float(sub_stats.get("cooldown_hours", 24)) * 2)
        elif event_type == "wording_win":
            variant = (metadata or {}).get("variant", "A")
            ww = state.setdefault("wording_winners", {"A": 0, "B": 0})
            ww[variant] = int(ww.get(variant, 0)) + 1
    save_learning_state(state, base)
    try:
        from ... import learning as acq_learning

        if event_type in ("operator_approved", "uploads_completed", "clicks"):
            acq_learning.record_winner(
                reason=f"reddit_{event_type}",
                metadata={"post_id": post_id, "subreddit": subreddit, **(metadata or {})},
                base=base,
            )
        elif event_type in ("operator_denied", "moderation_removed", "ignored_replies"):
            acq_learning.record_failure(
                reason=f"reddit_{event_type}",
                metadata={"post_id": post_id, "subreddit": subreddit},
                base=base,
            )
    except Exception:
        pass
    return rec


def ingest_funnel_signal(
    stage: str,
    *,
    project_id: str = "",
    lead_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    """Hook acquisition/customer funnel into reddit learning."""
    meta = metadata or {}
    if not str(lead_id).startswith("LD-RDT-") and "reddit" not in str(meta.get("campaign_id", "")).lower():
        return
    post_id = lead_id.replace("LD-RDT-", "")[:8] if lead_id else ""
    mapping = {
        "upload_started": "clicks",
        "upload_completed": "clicks",
        "workspace_created": "uploads_completed",
        "intake_completed": "uploads_completed",
    }
    event = mapping.get(stage)
    if event:
        record_outcome(event, post_id=post_id, metadata=meta, base=base)


def run_daily_reddit_learning(base: Optional[Path] = None) -> Dict[str, Any]:
    """Incremental daily evolution from telemetry and outcomes."""
    from . import telemetry as rdt

    state = load_learning_state(base)
    events = rdt.load_events(limit=500, base=base)
    approved = sum(1 for e in events if e.get("event_type") == "reddit_reply_approved")
    ignored = sum(1 for e in events if e.get("event_type") == "reddit_post_ignored")

    if approved > ignored:
        state["min_fit_threshold"] = max(45, int(state.get("min_fit_threshold", 50)) - 1)
    elif ignored > approved * 2 and ignored > 3:
        state["min_fit_threshold"] = min(75, int(state.get("min_fit_threshold", 50)) + 2)

    state["last_daily_learning_utc"] = utc_now()
    save_learning_state(state, base)

    _append_jsonl(
        EXPERIMENTS_JSONL,
        {
            "experiment_id": f"REXP-{uuid.uuid4().hex[:6]}",
            "when_utc": utc_now(),
            "name": "reddit_daily_increment",
            "min_fit_threshold": state["min_fit_threshold"],
            "wording_winners": state.get("wording_winners"),
            "outcome_totals": state.get("outcome_totals"),
        },
        base,
    )

    try:
        from ... import learning as acq_learning

        acq_learning.run_learning_cycle(base)
    except Exception:
        pass

    return {"ok": True, "state": state, "when_utc": utc_now()}

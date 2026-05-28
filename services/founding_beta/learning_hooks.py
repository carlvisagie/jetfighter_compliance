"""Safe learning_state updates for founding beta operational events."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.config import DATA

_LEARNING = DATA / "memory" / "learning_state.json"
_MAX_WRITE_BYTES = 128 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, data: Dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, indent=2)
    if len(raw.encode("utf-8")) > _MAX_WRITE_BYTES:
        return False
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(raw, encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def _load() -> Dict[str, Any]:
    if not _LEARNING.is_file():
        return {
            "status": "warming_up",
            "cycles_completed": 0,
            "approvals_seen": 0,
            "uploads_seen": 0,
            "last_learning_event": None,
            "signal_effectiveness": {},
            "conversion_counts": {},
        }
    try:
        return json.loads(_LEARNING.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def record_founding_beta_learning(
    event_type: str,
    *,
    intake_id: str = "",
    success: bool = True,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Bump founding-beta counters without heavy memory graph imports."""
    try:
        state = _load()
        if not isinstance(state, dict):
            state = {}
        state["last_learning_event"] = event_type
        state["updated_utc"] = _utc_now()

        if event_type in (
            "intake_received",
            "beta_upload_completed",
            "intake_classified",
        ):
            state["uploads_seen"] = int(state.get("uploads_seen") or 0) + 1

        if event_type in ("operator_approved", "operator_high_value"):
            state["approvals_seen"] = int(state.get("approvals_seen") or 0) + 1

        if event_type.startswith("operator_") or event_type in (
            "intake_classified",
            "missing_documents_detected",
        ):
            state["cycles_completed"] = int(state.get("cycles_completed") or 0) + 1

        if state.get("uploads_seen", 0) > 0 or state.get("approvals_seen", 0) > 0:
            if str(state.get("status") or "") == "warming_up":
                state["status"] = "healthy"

        eff = state.setdefault("signal_effectiveness", {})
        key = f"founding_beta:{event_type}"
        bucket = eff.setdefault(key, {"success": 0, "fail": 0, "outcomes": []})
        if success:
            bucket["success"] = int(bucket.get("success") or 0) + 1
        else:
            bucket["fail"] = int(bucket.get("fail") or 0) + 1
        outcomes = list(bucket.get("outcomes") or [])
        tag = intake_id or event_type
        bucket["outcomes"] = (outcomes + [tag])[-20:]

        if extra:
            fb = state.setdefault("founding_beta", {})
            if isinstance(fb, dict):
                fb.update({k: v for k, v in extra.items() if k in ("last_intake_id", "queue_depth")})

        _atomic_write(_LEARNING, state)

        try:
            from services.memory.learning import record_learning_signal

            record_learning_signal(
                f"founding_beta:{event_type}",
                event_type,
                success=success,
                segment="founding_beta",
                paperwork_hint=extra.get("primary_category", "") if extra else "",
            )
        except Exception:
            pass
    except Exception:
        pass

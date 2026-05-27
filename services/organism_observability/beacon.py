"""Customer-side telemetry beacons (inquiry page, no continuation token)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .emit import organism_emit


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_customer_beacon(
    event_type: str,
    *,
    session_id: str = "",
    project_id: str = "",
    duration_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a customer funnel beacon; never raises to caller."""
    allowed = frozenset(
        {
            "upload_page_view",
            "helper_opened",
            "helper_closed",
            "hesitation_before_upload",
            "upload_started",
            "upload_completed",
            "upload_cancelled",
            "upload_failed",
            "onboarding_abandoned",
            "min_info_requested",
            "magic_link_copied",
        }
    )
    et = event_type if event_type in allowed else "customer_beacon"
    meta = dict(metadata or {})
    meta["client_beacon"] = True
    if session_id:
        meta["session_id"] = session_id
    if meta.get("page_loaded_at") and not meta.get("seconds_to_first_interaction"):
        try:
            loaded = datetime.fromisoformat(str(meta["page_loaded_at"]).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            meta["seconds_to_first_interaction"] = max(0, int((now - loaded).total_seconds()))
        except (TypeError, ValueError):
            pass

    organism_emit(
        "customer_session",
        et,
        project_id=project_id,
        message=session_id,
        duration_ms=duration_ms,
        metadata=meta,
    )
    return {"ok": True, "event_type": et, "recorded_at": _utc_now()}

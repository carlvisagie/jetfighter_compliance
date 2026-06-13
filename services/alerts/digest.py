"""Daily and weekly operational digests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from . import engine
from .email import render_alert_html
from .paths import ensure_alerts_dir, load_config
from .severity import Severity
from services.defensive_wiring import safe_write_text, safe_write_json


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gather_stats() -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "targets_discovered": 0,
        "uploads_started": 0,
        "uploads_completed": 0,
        "conversions": 0,
        "abandonments": 0,
        "best_campaigns": [],
        "top_sources": [],
        "organism_insights": "",
    }
    try:
        from services.acquisition.orchestration import get_operator_dashboard

        acq = get_operator_dashboard()
        conv = acq.get("upload_conversion") or {}
        stats["uploads_started"] = conv.get("started", 0)
        stats["uploads_completed"] = conv.get("completed", 0)
        stats["conversions"] = conv.get("completed", 0)
        stats["organism_insights"] = acq.get("what_organism_is_learning", "")
        stats["best_campaigns"] = acq.get("best_channels", [])[:5]
        stats["targets_discovered"] = len(acq.get("hottest_targets") or [])
    except Exception:
        pass
    try:
        from services.alerts.telemetry import load_history

        recent = load_history(limit=500)
        stats["abandonments"] = sum(1 for r in recent if r.get("event_type") == "upload_abandonment")
    except Exception:
        pass
    return stats


def generate_daily_digest() -> Dict[str, Any]:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = _gather_stats()
    digest = {
        "kind": "daily",
        "day": day,
        "generated_utc": _utc(),
        "stats": stats,
        "summary": (
            f"Targets: {stats.get('targets_discovered', 0)} · "
            f"Uploads: {stats.get('uploads_completed', 0)}/{stats.get('uploads_started', 0)} · "
            f"Abandonments: {stats.get('abandonments', 0)}"
        ),
    }
    path = ensure_alerts_dir() / "digests" / f"daily-{day}.json"
    safe_write_json(

        path,

        digest,

        component="alerts_digest",

        context="digest generation"

    )
    engine.raise_alert(
        "digest_daily",
        title=f"Daily digest — {day}",
        body=digest["summary"],
        context=stats,
        force=True,
    )
    return digest


def generate_weekly_digest() -> Dict[str, Any]:
    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    stats = _gather_stats()
    digest = {
        "kind": "weekly",
        "week": week,
        "generated_utc": _utc(),
        "stats": stats,
        "summary": f"Week {week}: upload conversion focus; review acquisition learning in Control.",
    }
    path = ensure_alerts_dir() / "digests" / f"weekly-{week}.json"
    safe_write_json(

        path,

        digest,

        component="alerts_digest",

        context="digest generation"

    )
    engine.raise_alert(
        "digest_weekly",
        title=f"Weekly digest — {week}",
        body=digest["summary"],
        context=stats,
        force=True,
    )
    return digest

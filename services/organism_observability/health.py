"""Silent failure and anomaly detection."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_ts(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def detect_silent_failures(*, base: Optional[Path] = None, limit: int = 4000) -> List[Dict[str, Any]]:
    from services.memory.telemetry import load_telemetry

    from .emit import write_failure_count

    rows = load_telemetry(limit=limit, base=base)
    warnings: List[Dict[str, Any]] = []

    if write_failure_count() > 0:
        warnings.append(
            {
                "id": "telemetry_write_failed",
                "severity": "critical",
                "message": f"Telemetry write failures in-process: {write_failure_count()}",
                "action": "Check disk permissions and data/memory/telemetry.jsonl",
            }
        )

    tf = _count(rows, "telemetry_write_failed")
    if tf:
        warnings.append(
            {
                "id": "telemetry_persist_failed",
                "severity": "critical",
                "message": f"{tf} telemetry_write_failed events logged",
                "action": "Repair central telemetry transport",
            }
        )

    for et in ("overlay_failure", "evidence_mapping_failure", "reddit_discovery_failed", "acquisition_failure"):
        c = _count(rows, et)
        if c:
            warnings.append(
                {
                    "id": et,
                    "severity": "warning",
                    "message": f"{c} {et} event(s)",
                    "action": "Inspect subsystem logs",
                }
            )

    starvation = _count(rows, "queue_starvation")
    if starvation:
        warnings.append(
            {
                "id": "queue_starvation",
                "severity": "warning",
                "message": f"{starvation} acquisition queue starvation signal(s)",
                "action": "Tune prey threshold or expand discovery",
            }
        )

    zero_cycles = 0
    for r in rows:
        if r.get("event_type") in ("acquisition_cycle_completed", "reddit_discovery_completed"):
            meta = r.get("metadata") or {}
            if meta.get("queued") == 0:
                zero_cycles += 1
    if zero_cycles:
        warnings.append(
            {
                "id": "zero_result_acquisition",
                "severity": "warning",
                "message": f"{zero_cycles} discovery cycle(s) queued zero prospects",
                "action": "Review discovery expansion and prey tuning",
            }
        )

    stuck = _count(rows, "stuck_session_detected") + _count(rows, "upload_first_abandoned")
    if stuck >= 3:
        warnings.append(
            {
                "id": "stuck_or_abandoned_sessions",
                "severity": "info",
                "message": f"{stuck} abandoned/stuck session signal(s)",
                "action": "Review upload-first UX and inquiry friction",
            }
        )

    return warnings


def detect_anomalies(*, base: Optional[Path] = None, limit: int = 4000) -> List[Dict[str, Any]]:
    from services.memory.telemetry import load_telemetry

    rows = load_telemetry(limit=limit, base=base)
    anomalies: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=24)

    sub_counts: Counter = Counter()
    recent_sub: Counter = Counter()
    for r in rows:
        sub = r.get("subsystem", "unknown")
        sub_counts[sub] += 1
        ts = _parse_ts(r.get("observed_at_utc", ""))
        if ts and ts >= recent_cutoff:
            recent_sub[sub] += 1

    expected = {
        "customer_session",
        "acquisition_organism",
        "reddit_acquisition",
        "knowledge_cockpit",
        "evidence_intelligence",
    }
    for sub in expected:
        if recent_sub[sub] == 0 and sub_counts[sub] > 0:
            anomalies.append(
                {
                    "id": f"dead_zone_{sub}",
                    "severity": "warning",
                    "message": f"No {sub} telemetry in last 24h (historical data exists)",
                    "action": f"Verify {sub} subsystem is emitting",
                }
            )
        elif sub_counts[sub] == 0:
            anomalies.append(
                {
                    "id": f"never_observed_{sub}",
                    "severity": "info",
                    "message": f"Subsystem {sub} never observed in window",
                    "action": "Wire organism_emit on critical paths",
                }
            )

    fail_rate: Dict[str, int] = {}
    fail_total: Dict[str, int] = {}
    for r in rows:
        sub = r.get("subsystem", "unknown")
        fail_total[sub] = fail_total.get(sub, 0) + 1
        if not r.get("success", True):
            fail_rate[sub] = fail_rate.get(sub, 0) + 1
    for sub, fails in fail_rate.items():
        total = fail_total.get(sub, 1)
        if fails / total > 0.25 and fails >= 3:
            anomalies.append(
                {
                    "id": f"high_failure_{sub}",
                    "severity": "warning",
                    "message": f"{sub} failure rate {fails}/{total}",
                    "action": "Investigate repeated failures",
                }
            )

    return anomalies


def _count(rows: List[Dict[str, Any]], event_type: str) -> int:
    return sum(1 for r in rows if r.get("event_type") == event_type)

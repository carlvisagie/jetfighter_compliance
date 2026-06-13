"""Actionable telemetry diagnostics for operator cockpit and COTE."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .defensive_wiring import safe_write_text
from typing import Any, Dict, List, Optional, Tuple

from .config import DATA
from .lazy_io import file_size, iter_jsonl_lines

_JOBS_DIR = DATA / "jobs"


def telemetry_storage_path() -> Path:
    return DATA / "memory" / "telemetry.jsonl"
_STALE_HOURS = 24
_INGEST_WINDOW_HOURS = 1
_QUEUE_BACKLOG_THRESHOLD = 50
_HIGH_LATENCY_MS = 1500
_TAIL_LINES = 500


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_queue_depth() -> int:
    if not _JOBS_DIR.is_dir():
        return 0
    return len(list(_JOBS_DIR.glob("J-*.json")))


def _scan_parse_errors(path: Path, *, tail_raw: int = 200) -> int:
    if not path.is_file():
        return 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    errors = 0
    for line in lines[-tail_raw:]:
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            errors += 1
    return errors


def _ingest_stats(rows: List[Dict[str, Any]]) -> Tuple[float, Optional[str], int]:
    """Events per hour in ingest window, last write ISO, recent-hour count."""
    now = _utc_now()
    window = timedelta(hours=_INGEST_WINDOW_HOURS)
    recent = 0
    last_ts: Optional[datetime] = None
    for row in rows:
        ts = _parse_ts(row.get("observed_at_utc"))
        if not ts:
            continue
        if last_ts is None or ts > last_ts:
            last_ts = ts
        if now - ts <= window:
            recent += 1
    rate = float(recent) / max(_INGEST_WINDOW_HOURS, 1)
    last_write = last_ts.strftime("%Y-%m-%dT%H:%M:%SZ") if last_ts else None
    return rate, last_write, recent


def _collect_last_errors(rows: List[Dict[str, Any]], *, limit: int = 8) -> List[Dict[str, Any]]:
    errors: List[Tuple[datetime, Dict[str, Any]]] = []
    for row in rows:
        failed = row.get("success") is False
        et = str(row.get("event_type") or "")
        if not failed and "fail" not in et.lower() and "error" not in et.lower():
            continue
        ts = _parse_ts(row.get("observed_at_utc")) or _utc_now()
        errors.append(
            (
                ts,
                {
                    "observed_at_utc": row.get("observed_at_utc"),
                    "subsystem": row.get("subsystem"),
                    "event_type": et,
                    "error_code": row.get("error_code"),
                    "message": (row.get("message") or "")[:240],
                },
            )
        )
    errors.sort(key=lambda x: x[0], reverse=True)
    return [e[1] for e in errors[:limit]]


def _high_latency_count(rows: List[Dict[str, Any]]) -> int:
    n = 0
    for row in rows:
        dur = row.get("duration_ms")
        if isinstance(dur, (int, float)) and dur >= _HIGH_LATENCY_MS:
            n += 1
    return n


def _dropped_event_count(rows: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for r in rows
        if str(r.get("event_type") or "") in ("telemetry_write_failed", "telemetry_dropped")
        or str(r.get("error_code") or "") == "telemetry_dropped"
    )


def _failing_subsystems(rows: List[Dict[str, Any]]) -> List[str]:
    """Return subsystems with failures in the last 24 hours."""
    counts: Dict[str, int] = {}
    now = _utc_now()
    cutoff = now - timedelta(hours=24)
    
    for row in rows:
        if row.get("success") is False:
            # Only count failures from last 24 hours
            ts = _parse_ts(row.get("observed_at_utc"))
            if ts and ts > cutoff:
                sub = str(row.get("subsystem") or "unknown")
                counts[sub] = counts.get(sub, 0) + 1
    
    return [s for s, _ in sorted(counts.items(), key=lambda x: -x[1])[:5]]


def build_telemetry_status() -> Dict[str, Any]:
    path = telemetry_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(iter_jsonl_lines(path, tail_lines=_TAIL_LINES)) if path.is_file() else []
    sample_count = len(rows)
    parse_errors = _scan_parse_errors(path)
    ingest_rate, last_write, recent_hour = _ingest_stats(rows)
    queue_depth = _job_queue_depth()
    last_errors = _collect_last_errors(rows)
    latency_hits = _high_latency_count(rows)
    dropped = _dropped_event_count(rows)
    failing_subs = _failing_subsystems(rows)

    try:
        from services.organism_observability.emit import write_failure_count

        in_process_write_failures = write_failure_count()
    except Exception:
        in_process_write_failures = 0

    now = _utc_now()
    last_dt = _parse_ts(last_write)
    hours_since_write = (
        (now - last_dt).total_seconds() / 3600.0 if last_dt else None
    )
    stale_threshold_exceeded = bool(
        path.is_file()
        and sample_count > 0
        and hours_since_write is not None
        and hours_since_write > _STALE_HOURS
    )

    degraded_reasons: List[Dict[str, Any]] = []

    if in_process_write_failures > 0:
        degraded_reasons.append(
            {
                "code": "write_failure",
                "subsystem": "telemetry",
                "message": f"In-process telemetry write failures: {in_process_write_failures}",
                "recommended_action": "Check data root permissions and disk space on telemetry storage path.",
            }
        )

    persist_failures = sum(
        1 for r in rows if str(r.get("event_type") or "") == "telemetry_write_failed"
    )
    if persist_failures:
        degraded_reasons.append(
            {
                "code": "write_failure",
                "subsystem": "telemetry",
                "message": f"{persist_failures} telemetry_write_failed event(s) in recent tail",
                "recommended_action": "Repair central telemetry transport; verify memory/telemetry.jsonl is writable.",
            }
        )

    if parse_errors:
        degraded_reasons.append(
            {
                "code": "parser_failure",
                "subsystem": "telemetry",
                "message": f"{parse_errors} corrupt JSON line(s) in telemetry tail",
                "recommended_action": "Inspect telemetry.jsonl for manual edits or partial writes; trim corrupt lines.",
            }
        )

    if queue_depth >= _QUEUE_BACKLOG_THRESHOLD:
        degraded_reasons.append(
            {
                "code": "queue_backup",
                "subsystem": "job_queue",
                "message": f"Job queue depth {queue_depth} (threshold {_QUEUE_BACKLOG_THRESHOLD})",
                "recommended_action": "Enable schedulers or drain data/jobs backlog before accepting heavy load.",
            }
        )

    if latency_hits >= 3:
        degraded_reasons.append(
            {
                "code": "storage_latency",
                "subsystem": "telemetry",
                "message": f"{latency_hits} telemetry events exceeded {_HIGH_LATENCY_MS}ms duration",
                "recommended_action": "Check disk latency and reduce concurrent heavy writes to data root.",
            }
        )

    if dropped:
        degraded_reasons.append(
            {
                "code": "dropped_events",
                "subsystem": "telemetry",
                "message": f"{dropped} dropped/failed telemetry transport signal(s)",
                "recommended_action": "Review organism emit paths; fix underlying subsystem errors.",
            }
        )

    if failing_subs:
        degraded_reasons.append(
            {
                "code": "subsystem_failure",
                "subsystem": ", ".join(failing_subs),
                "message": "Recent telemetry failures by subsystem: " + ", ".join(failing_subs),
                "recommended_action": "Open organism observability and inspect failing subsystem logs.",
            }
        )

    if not path.is_file() or sample_count == 0:
        degraded_reasons.append(
            {
                "code": "no_traffic",
                "subsystem": "telemetry",
                "message": "No telemetry events in canonical store",
                "recommended_action": "Confirm subsystems emit via emit_telemetry; exercise intake or health/ready probe.",
            }
        )
    elif recent_hour == 0 and not stale_threshold_exceeded:
        degraded_reasons.append(
            {
                "code": "no_traffic",
                "subsystem": "telemetry",
                "message": f"No telemetry ingested in the last {_INGEST_WINDOW_HOURS}h",
                "recommended_action": "Normal during quiet periods; trigger a known event (login, upload) to verify flow.",
            }
        )

    if stale_threshold_exceeded:
        degraded_reasons.append(
            {
                "code": "stale_telemetry",
                "subsystem": "telemetry",
                "message": f"Last telemetry write {hours_since_write:.1f}h ago (threshold {_STALE_HOURS}h)",
                "recommended_action": "Verify schedulers and subsystem activity; check for silent write failures.",
            }
        )

    try:
        from services.organism_observability.health import detect_silent_failures

        for w in detect_silent_failures(base=DATA, limit=800)[:4]:
            wid = str(w.get("id") or "")
            if wid in ("telemetry_write_failed", "telemetry_persist_failed"):
                continue
            degraded_reasons.append(
                {
                    "code": "silent_failure",
                    "subsystem": wid,
                    "message": w.get("message") or wid,
                    "recommended_action": w.get("action") or "Inspect organism observability.",
                }
            )
    except Exception:
        pass

    # Dedupe by code+message
    seen = set()
    unique_reasons: List[Dict[str, Any]] = []
    for r in degraded_reasons:
        key = (r["code"], r.get("message"))
        if key in seen:
            continue
        seen.add(key)
        unique_reasons.append(r)
    degraded_reasons = unique_reasons

    codes = {r["code"] for r in degraded_reasons}
    if "write_failure" in codes or in_process_write_failures > 0:
        telemetry_health = "failed"
        telemetry_pulse = "write_failure"
    elif "queue_backup" in codes:
        telemetry_health = "degraded"
        telemetry_pulse = "backlog"
    elif "stale_telemetry" in codes:
        telemetry_health = "degraded"
        telemetry_pulse = "stale"
    elif degraded_reasons:
        telemetry_health = "degraded"
        telemetry_pulse = "stale" if "no_traffic" in codes else "degraded"
    else:
        telemetry_health = "healthy"
        telemetry_pulse = "healthy_flow"

    writable = path.parent.exists() and path.parent.is_dir()
    try:
        probe = path.parent / ".tel_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except OSError:
        writable = False
        degraded_reasons.append(
            {
                "code": "write_failure",
                "subsystem": "telemetry",
                "message": "Telemetry storage path not writable",
                "recommended_action": "Fix permissions on data/memory directory.",
            }
        )
        telemetry_health = "failed"
        telemetry_pulse = "write_failure"

    return {
        "ok": True,
        "telemetry_health": telemetry_health,
        "telemetry_pulse": telemetry_pulse,
        "telemetry_sample_count": sample_count,
        "telemetry_ingest_rate_per_hour": round(ingest_rate, 2),
        "last_telemetry_write_utc": last_write,
        "hours_since_last_write": round(hours_since_write, 2) if hours_since_write is not None else None,
        "telemetry_storage_path": str(path.resolve()),
        "telemetry_storage_bytes": file_size(path) if path.is_file() else 0,
        "storage_writable": writable,
        "queue_depth": queue_depth,
        "queue_backlog_threshold": _QUEUE_BACKLOG_THRESHOLD,
        "last_telemetry_errors": last_errors,
        "parse_error_count": parse_errors,
        "dropped_event_count": dropped,
        "high_latency_event_count": latency_hits,
        "failing_subsystems": failing_subs,
        "stale_threshold_hours": _STALE_HOURS,
        "stale_threshold_exceeded": stale_threshold_exceeded,
        "degraded_reasons": degraded_reasons,
        "recent_hour_event_count": recent_hour,
    }

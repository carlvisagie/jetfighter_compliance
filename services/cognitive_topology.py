"""
Cognitive Operational Topology Engine (COTE) — lightweight summarized organism state.

No acquisition orchestration, schedulers, or full memory graph loads.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import DATA, PROJECTS
from .lazy_io import file_size, iter_jsonl_lines, read_text_bounded
from .production import readiness_checks
from .runtime_boot import (
    is_safe_mode,
    knowledge_overlay_enabled,
    manual_acquisition_enabled,
    observability_enabled,
    schedulers_enabled,
)

_TELEMETRY = DATA / "memory" / "telemetry.jsonl"
_ALERTS = DATA / "alerts" / "alerts.jsonl"
_LEARNING = DATA / "memory" / "learning_state.json"
_LEARNING_STALE_HOURS = 168
_LEARNING_FAIL_WINDOW_HOURS = 24
_LEARNING_FAIL_THRESHOLD = 3

_LEARNING_SEED: Dict[str, Any] = {
    "version": 1,
    "status": "warming_up",
    "cycles_completed": 0,
    "approvals_seen": 0,
    "uploads_seen": 0,
    "last_learning_event": None,
    "updated_utc": "",
    "signal_effectiveness": {},
    "conversion_counts": {
        "lead_to_inquiry": 0,
        "inquiry_to_intake": 0,
        "intake_to_evidence": 0,
        "lead_failed": 0,
    },
    "paperwork_patterns": {"high_fit": [], "low_fit": []},
    "segment_performance": {},
}

_TELEM_MAP = {
    "acquisition": "acquisition",
    "reddit": "acquisition",
    "usaspending": "acquisition",
    "knowledge": "knowledge",
    "knowledge_cockpit": "knowledge",
    "observability": "observability",
    "organism": "observability",
    "upload": "upload_pipeline",
    "intake": "upload_pipeline",
    "upload_pipeline": "upload_pipeline",
    "evidence": "evidence_processing",
    "evidence_intelligence": "evidence_processing",
    "learning": "learning",
    "memory": "learning",
    "telemetry": "telemetry",
    "email": "alerts",
    "alerts": "alerts",
    "system": "system_health",
}

_RING_KEYS = (
    "acquisition",
    "knowledge",
    "observability",
    "upload_pipeline",
    "evidence_processing",
    "learning",
    "telemetry",
    "alerts",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _round3(v: float) -> float:
    return round(_clamp(v), 3)


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        s = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _tail_telemetry(limit: int = 120) -> List[Dict[str, Any]]:
    if not _TELEMETRY.is_file():
        return []
    return list(iter_jsonl_lines(_TELEMETRY, tail_lines=limit))


def _telemetry_stats(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    buckets: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"events": 0, "failures": 0, "latency_sum": 0.0, "latency_n": 0}
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        sub = str(row.get("subsystem") or "system")
        key = _TELEM_MAP.get(sub, "telemetry")
        b = buckets[key]
        b["events"] += 1
        if row.get("success") is False:
            b["failures"] += 1
        dur = row.get("duration_ms")
        if isinstance(dur, (int, float)) and dur >= 0:
            b["latency_sum"] += float(dur)
            b["latency_n"] += 1
        ts = _parse_ts(row.get("observed_at_utc"))
        if ts and (now - ts).total_seconds() < 3600:
            b["recent"] = b.get("recent", 0) + 1
    out: Dict[str, Dict[str, float]] = {}
    for key, b in buckets.items():
        events = b["events"] or 1
        fail_rate = b["failures"] / events
        lat = (b["latency_sum"] / b["latency_n"] / 2000.0) if b["latency_n"] else 0.0
        recent = b.get("recent", 0)
        activity = _clamp(recent / 12.0 + min(events, 40) / 80.0)
        pressure = _clamp(fail_rate * 0.7 + lat * 0.3 + (0.15 if recent > 8 else 0))
        health = _clamp(1.0 - fail_rate * 0.65 - lat * 0.2)
        confidence = _clamp(health - fail_rate * 0.15)
        out[key] = {
            "health": health,
            "pressure": pressure,
            "activity": activity,
            "confidence": confidence,
            "latency": _clamp(lat),
            "alerts": int(b["failures"]),
            "anomaly": fail_rate > 0.35 or (recent > 15 and fail_rate > 0.2),
        }
    return out


def _project_upload_signal() -> Tuple[float, float, float]:
    """Activity / health proxies from project dir mtimes (no project file reads)."""
    if not PROJECTS.is_dir():
        return 0.2, 0.75, 0.7
    now = datetime.now(timezone.utc).timestamp()
    recent = 0
    total = 0
    for child in PROJECTS.iterdir():
        if not child.is_dir():
            continue
        total += 1
        try:
            age_h = (now - child.stat().st_mtime) / 3600.0
            if age_h < 72:
                recent += 1
        except OSError:
            continue
    activity = _clamp(recent / max(total, 1) + min(total, 20) / 40.0)
    health = _clamp(0.55 + activity * 0.35)
    confidence = _clamp(0.5 + min(total, 10) / 20.0)
    return activity, health, confidence


def _alerts_signal() -> Tuple[int, float]:
    if not _ALERTS.is_file():
        return 0, 0.0
    open_count = 0
    for row in iter_jsonl_lines(_ALERTS, tail_lines=40):
        if row.get("acknowledged"):
            continue
        sev = str(row.get("severity") or "").lower()
        if sev in ("high", "critical", "warning"):
            open_count += 1
    pressure = _clamp(open_count / 8.0)
    return open_count, pressure


def _seed_learning_state_if_missing() -> bool:
    """Create default learning_state on first boot (bounded, no heavy imports)."""
    if _LEARNING.is_file():
        return False
    try:
        _LEARNING.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(_LEARNING_SEED)
        payload["updated_utc"] = _utc_now()
        tmp = _LEARNING.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(_LEARNING)
        return True
    except OSError:
        return False


def _learning_telemetry_failures(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Count learning-related telemetry failures (total, recent window)."""
    total = 0
    recent = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        sub = str(row.get("subsystem") or "").lower()
        et = str(row.get("event_type") or "").lower()
        if sub not in ("learning", "memory") and "learning" not in et:
            continue
        if row.get("success") is not False:
            continue
        total += 1
        ts = _parse_ts(row.get("observed_at_utc"))
        if ts and (now - ts).total_seconds() < _LEARNING_FAIL_WINDOW_HOURS * 3600:
            recent += 1
    return total, recent


def _learning_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    eff = data.get("signal_effectiveness") if isinstance(data.get("signal_effectiveness"), dict) else {}
    counts = data.get("conversion_counts") if isinstance(data.get("conversion_counts"), dict) else {}
    cycles = int(data.get("cycles_completed") or 0)
    if cycles <= 0 and eff:
        cycles = len(eff)
    uploads = int(data.get("uploads_seen") or 0)
    if uploads <= 0:
        uploads = int(counts.get("intake_to_evidence") or 0)
    approvals = int(data.get("approvals_seen") or 0)
    if approvals <= 0:
        ob = eff.get("onboarding:completed")
        if isinstance(ob, dict):
            approvals = int(ob.get("success") or 0)
    last_event = data.get("last_learning_event")
    if last_event is None or last_event == "":
        last_event = data.get("updated_utc") or None
    signal_events = 0
    for bucket in eff.values():
        if not isinstance(bucket, dict):
            continue
        signal_events += int(bucket.get("success") or 0) + int(bucket.get("fail") or 0)
    return {
        "cycles_completed": cycles,
        "uploads_seen": uploads,
        "approvals_seen": approvals,
        "last_learning_event": last_event,
        "signal_events": signal_events,
    }


def _learning_stale(data: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
    """Stale only when there was prior learning activity but nothing recent."""
    if metrics["signal_events"] <= 0 and metrics["cycles_completed"] <= 0:
        return False
    ts = _parse_ts(data.get("updated_utc"))
    if not ts:
        return False
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
    return age_h > _LEARNING_STALE_HOURS


def _assess_learning_node(telem_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Classify central-memory learning health for COTE.

    warming_up: MVP / no history yet (not degraded).
    degraded: unreadable state, stale, or repeated failures.
    failed: explicit cycle error or severe failure burst.
    healthy: active learning signals present.
    """
    seeded = _seed_learning_state_if_missing()
    raw = read_text_bounded(_LEARNING, max_bytes=64 * 1024)
    fail_total, fail_recent = _learning_telemetry_failures(telem_rows)

    if not _LEARNING.is_file() and not raw.strip():
        if seeded:
            raw = read_text_bounded(_LEARNING, max_bytes=64 * 1024)
        if not raw.strip():
            return _learning_node_payload(
                status="warming_up",
                reason="awaiting first learning cycle",
                metrics={
                    "cycles_completed": 0,
                    "uploads_seen": 0,
                    "approvals_seen": 0,
                    "last_learning_event": None,
                    "signal_events": 0,
                },
            )

    if _LEARNING.is_file() and not raw.strip():
        return _learning_node_payload(
            status="degraded",
            reason="learning state file unreadable",
            metrics={
                "cycles_completed": 0,
                "uploads_seen": 0,
                "approvals_seen": 0,
                "last_learning_event": None,
                "signal_events": 0,
            },
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _learning_node_payload(
            status="degraded",
            reason="learning state JSON corrupt",
            metrics={
                "cycles_completed": 0,
                "uploads_seen": 0,
                "approvals_seen": 0,
                "last_learning_event": None,
                "signal_events": 0,
            },
        )

    if not isinstance(data, dict):
        data = {}

    metrics = _learning_metrics(data)
    explicit = str(data.get("status") or "").lower()
    cycle_error = data.get("last_cycle_error") or data.get("learning_cycle_error")

    if explicit == "failed" or (cycle_error and str(cycle_error).strip()):
        return _learning_node_payload(
            status="failed",
            reason=str(cycle_error or "learning cycle error"),
            metrics=metrics,
        )

    if fail_recent >= _LEARNING_FAIL_THRESHOLD:
        return _learning_node_payload(
            status="failed",
            reason=f"{fail_recent} learning failures in last {_LEARNING_FAIL_WINDOW_HOURS}h",
            metrics=metrics,
        )

    if _learning_stale(data, metrics):
        return _learning_node_payload(
            status="degraded",
            reason=f"no learning updates in {_LEARNING_STALE_HOURS}h",
            metrics=metrics,
        )

    if fail_total > 0 and fail_recent > 0:
        return _learning_node_payload(
            status="degraded",
            reason="recent learning telemetry failures",
            metrics=metrics,
        )

    has_history = (
        metrics["signal_events"] > 0
        or metrics["cycles_completed"] > 0
        or metrics["uploads_seen"] > 0
        or metrics["approvals_seen"] > 0
    )

    if explicit == "warming_up" or (not has_history and not seeded):
        return _learning_node_payload(
            status="warming_up",
            reason="collecting first learning signals",
            metrics=metrics,
        )

    if has_history:
        improving = metrics["uploads_seen"] > 0 or metrics["approvals_seen"] > 0
        return _learning_node_payload(
            status="healthy",
            reason="uploads observed" if improving else "learning signals active",
            metrics=metrics,
        )

    return _learning_node_payload(
        status="warming_up",
        reason="collecting first learning signals",
        metrics=metrics,
    )


def _learning_node_payload(
    *,
    status: str,
    reason: str,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    activity = _clamp(
        metrics["cycles_completed"] / 20.0
        + metrics["uploads_seen"] / 40.0
        + metrics["approvals_seen"] / 30.0
        + metrics["signal_events"] / 200.0
    )
    if status == "healthy":
        health = _clamp(0.72 + activity * 0.2)
        pressure = _clamp(0.12 + (1.0 - activity) * 0.1)
        confidence = _clamp(0.68 + activity * 0.25)
        anomaly = False
    elif status == "warming_up":
        health = 0.64
        pressure = 0.14
        confidence = 0.58
        anomaly = False
    elif status == "failed":
        health = 0.28
        pressure = 0.55
        confidence = 0.32
        anomaly = True
    else:  # degraded
        health = 0.46
        pressure = 0.38
        confidence = 0.4
        anomaly = True

    return {
        "health": health,
        "activity": activity if status != "warming_up" else max(activity, 0.12),
        "confidence": confidence,
        "pressure": pressure,
        "latency": 0.03,
        "alerts": 0,
        "anomaly": anomaly,
        "learning_status": status,
        "learning_reason": reason,
        "last_learning_event": metrics.get("last_learning_event"),
        "cycles_completed": metrics["cycles_completed"],
        "approvals_seen": metrics["approvals_seen"],
        "uploads_seen": metrics["uploads_seen"],
    }


def _paused_state(label: str = "") -> Dict[str, Any]:
    return {
        "health": 0.52,
        "pressure": 0.06,
        "activity": 0.03,
        "confidence": 0.48,
        "latency": 0.0,
        "alerts": 0,
        "paused": True,
        "anomaly": False,
        "label": label or "paused",
    }


def _merge_state(
    base: Dict[str, float],
    *,
    paused: bool = False,
    alerts: int = 0,
) -> Dict[str, Any]:
    return {
        "health": _round3(base.get("health", 0.7)),
        "pressure": _round3(base.get("pressure", 0.2)),
        "activity": _round3(base.get("activity", 0.3)),
        "confidence": _round3(base.get("confidence", 0.65)),
        "latency": _round3(base.get("latency", 0.0)),
        "alerts": int(alerts if alerts else base.get("alerts", 0)),
        "paused": paused,
        "anomaly": bool(base.get("anomaly")),
    }


def build_cognitive_topology() -> Dict[str, Any]:
    """Summarized topology for COTE visualization."""
    ready = readiness_checks()
    telem_rows = _tail_telemetry(120)
    telem_stats = _telemetry_stats(telem_rows)
    upload_act, upload_health, upload_conf = _project_upload_signal()
    fb_flow: Dict[str, Any] = {}
    try:
        from .founding_beta.intake import intake_flow_metrics

        fb_flow = intake_flow_metrics()
    except Exception:
        fb_flow = {}
    proj_count = (
        sum(1 for p in PROJECTS.iterdir() if p.is_dir()) if PROJECTS.is_dir() else 0
    )
    alert_count, alert_pressure = _alerts_signal()
    learn = _assess_learning_node(telem_rows)

    safe = is_safe_mode()
    acq_paused = safe or not manual_acquisition_enabled()
    know_paused = safe or not knowledge_overlay_enabled()
    obs_paused = safe or not observability_enabled()

    def from_telem(key: str, default_health: float = 0.72) -> Dict[str, float]:
        if key in telem_stats:
            return telem_stats[key]
        return {
            "health": default_health,
            "pressure": 0.18,
            "activity": 0.22,
            "confidence": 0.62,
            "latency": 0.05,
            "alerts": 0,
            "anomaly": False,
        }

    subsystems: Dict[str, Dict[str, Any]] = {}

    if acq_paused:
        subsystems["acquisition"] = _paused_state("stabilization")
    else:
        subsystems["acquisition"] = _merge_state(from_telem("acquisition", 0.78))

    if know_paused:
        subsystems["knowledge"] = _paused_state("stabilization")
    else:
        subsystems["knowledge"] = _merge_state(from_telem("knowledge", 0.74))

    if obs_paused:
        subsystems["observability"] = _paused_state("stabilization")
    else:
        subsystems["observability"] = _merge_state(from_telem("observability", 0.7))

    fb_activity = float(fb_flow.get("activity", 0))
    fb_pressure = float(fb_flow.get("pressure", 0))
    fb_health = float(fb_flow.get("health", upload_health))
    upload_activity = _clamp(max(upload_act, fb_activity))
    upload_pressure = _clamp(max((1.0 - upload_act) * 0.35, fb_pressure))
    upload_anomaly = bool(fb_flow.get("failed_recent")) or (
        upload_act < 0.08 and proj_count > 0
    )
    subsystems["upload_pipeline"] = _merge_state(
        {
            "health": _clamp((upload_health + fb_health) / 2),
            "pressure": upload_pressure,
            "activity": upload_activity,
            "confidence": upload_conf,
            "latency": 0.08,
            "alerts": int(fb_flow.get("pending_review", 0)),
            "anomaly": upload_anomaly,
            "flow_active": bool(fb_flow.get("uploads_active")),
            "pending_review": int(fb_flow.get("pending_review", 0)),
        }
    )

    subsystems["evidence_processing"] = _merge_state(
        from_telem("evidence_processing", 0.68)
    )

    subsystems["learning"] = _merge_state(learn)
    for key in (
        "learning_status",
        "learning_reason",
        "last_learning_event",
        "cycles_completed",
        "approvals_seen",
        "uploads_seen",
    ):
        if key in learn:
            subsystems["learning"][key] = learn[key]

    tel_n = len(telem_rows)
    tel_health = _clamp(0.4 + min(tel_n, 100) / 120.0) if _TELEMETRY.is_file() else 0.35
    subsystems["telemetry"] = _merge_state(
        {
            "health": tel_health,
            "pressure": _clamp(file_size(_TELEMETRY) / (5 * 1024 * 1024)),
            "activity": _clamp(tel_n / 80.0),
            "confidence": _clamp(0.5 + tel_health * 0.4),
            "latency": 0.04,
            "alerts": sum(1 for r in telem_rows if r.get("success") is False),
            "anomaly": file_size(_TELEMETRY) > 5 * 1024 * 1024,
        }
    )

    subsystems["alerts"] = _merge_state(
        {
            "health": _clamp(1.0 - alert_count / 6.0),
            "pressure": alert_pressure,
            "activity": _clamp(alert_count / 5.0),
            "confidence": 0.7 if alert_count == 0 else 0.45,
            "latency": 0.02,
            "alerts": alert_count,
            "anomaly": alert_count >= 3,
        }
    )

    core_health = sum(s["health"] for s in subsystems.values()) / max(len(subsystems), 1)
    if not ready.get("data_writable"):
        core_health *= 0.6
    if not ready.get("smtp_configured"):
        core_health *= 0.92
    subsystems["system_health"] = _merge_state(
        {
            "health": core_health,
            "pressure": sum(s["pressure"] for s in subsystems.values()) / len(subsystems),
            "activity": sum(s["activity"] for s in subsystems.values()) / len(subsystems),
            "confidence": sum(s["confidence"] for s in subsystems.values()) / len(subsystems),
            "latency": 0.03,
            "alerts": alert_count,
            "anomaly": any(s.get("anomaly") for s in subsystems.values()),
        }
    )

    global_pressure = sum(s["pressure"] for s in subsystems.values()) / len(subsystems)
    system_health = subsystems["system_health"]["health"]

    attention: List[str] = []
    if safe:
        attention.append("Safe mode active — intelligence modules paused; core intake/upload paths remain.")
    if alert_count:
        attention.append(f"{alert_count} operational alert(s) need review.")
    for key in _RING_KEYS:
        st = subsystems.get(key, {})
        if st.get("paused"):
            continue
        if key == "learning":
            ls = st.get("learning_status")
            if ls == "degraded":
                reason = st.get("learning_reason") or "inspect learning state"
                attention.append(f"Learning health degraded ({reason}).")
            elif ls == "failed":
                reason = st.get("learning_reason") or "learning cycle error"
                attention.append(f"Learning cycle failed ({reason}).")
            elif ls == "warming_up":
                pass
            elif st.get("health", 1) < 0.55:
                attention.append(f"{key.replace('_', ' ').title()} health degraded.")
        elif st.get("health", 1) < 0.55:
            attention.append(f"{key.replace('_', ' ').title()} health degraded.")
        if st.get("pressure", 0) > 0.62:
            attention.append(f"{key.replace('_', ' ').title()} under elevated pressure.")
        if st.get("anomaly") and key != "learning":
            attention.append(f"Anomaly pattern detected in {key.replace('_', ' ')}.")
        elif key == "learning" and st.get("learning_status") in ("degraded", "failed") and st.get("anomaly"):
            pass

    if not schedulers_enabled():
        attention.append("Background schedulers are off (stabilization).")

    return {
        "ok": True,
        "generated_at_utc": _utc_now(),
        "safe_mode": safe,
        "schedulers_enabled": schedulers_enabled(),
        "system_health": _round3(system_health),
        "global_pressure": _round3(global_pressure),
        "global_activity": _round3(
            sum(s["activity"] for s in subsystems.values()) / len(subsystems)
        ),
        "global_confidence": _round3(
            sum(s["confidence"] for s in subsystems.values()) / len(subsystems)
        ),
        "subsystems": subsystems,
        "operator_attention_required": attention[:8],
        "topology_meta": {
            "telemetry_sample": tel_n,
            "project_dirs": proj_count,
            "data_writable": bool(ready.get("data_writable")),
        },
    }

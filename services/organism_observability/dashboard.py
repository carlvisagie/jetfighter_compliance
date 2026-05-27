"""Operator cockpit organism observability dashboard."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .funnels import (
    compute_acquisition_funnel,
    compute_evidence_metrics,
    compute_overlay_metrics,
    compute_upload_funnel,
)
from .health import detect_anomalies, detect_silent_failures


def get_operator_cockpit_observability(
    *,
    telemetry_limit: int = 500,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Actionable observability for Control Center — no vanity metrics."""
    from services.memory.organism_observability import get_observability_dashboard

    core = get_observability_dashboard(telemetry_limit=telemetry_limit, base=base)
    upload = compute_upload_funnel(base=base, limit=telemetry_limit)
    acquisition = compute_acquisition_funnel(base=base, limit=telemetry_limit)
    overlay = compute_overlay_metrics(base=base, limit=telemetry_limit)
    evidence = compute_evidence_metrics(base=base, limit=telemetry_limit)
    silent = detect_silent_failures(base=base, limit=telemetry_limit)
    anomalies = detect_anomalies(base=base, limit=telemetry_limit)

    top_confusion = overlay.get("top_concepts") or []
    dead_zones = [a for a in anomalies if a.get("id", "").startswith("dead_zone")]

    actionable = []
    for w in silent:
        actionable.append(w.get("action", ""))
    for a in anomalies[:5]:
        actionable.append(a.get("action", ""))
    actionable.extend(upload.get("abandonment_hotspots") or [])
    actionable.extend(core.get("recommended_improvements") or [])

    return {
        "ok": True,
        "audit_utc": core.get("audit_utc"),
        "verdict": core.get("verdict"),
        "upload_funnel": upload,
        "acquisition_funnel": acquisition,
        "overlay_usefulness": overlay,
        "evidence_mapping": evidence,
        "abandonment_hotspots": upload.get("abandonment_hotspots", []),
        "top_confusion_concepts": [{"concept_id": c, "count": n} for c, n in top_confusion],
        "telemetry_anomalies": anomalies,
        "silent_failure_warnings": silent,
        "organism_dead_zones": dead_zones,
        "subsystem_health": core.get("subsystem_health", {}),
        "recommended_actions": [x for x in dict.fromkeys(actionable) if x][:12],
        "telemetry_sample_size": core.get("telemetry_count", 0),
    }

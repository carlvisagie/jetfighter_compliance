"""Derive GREEN / AMBER / RED + bottleneck + next action from checks."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def derive_health(
    checks: List[Dict[str, Any]],
    *,
    intake: Dict[str, Any],
    storage: Dict[str, Any],
) -> Tuple[str, str, str, List[str]]:
    """
    Returns: (health_state, current_bottleneck, next_recommended_action, mismatches)
    """
    mismatches: List[str] = []
    red_checks: List[Dict[str, Any]] = []
    amber_checks: List[Dict[str, Any]] = []

    for c in checks:
        if c.get("severity") == "red":
            red_checks.append(c)
            mismatches.append(c["name"])
        elif c.get("severity") == "amber":
            amber_checks.append(c)
            mismatches.append(c["name"])

    if not storage.get("durable_storage_configured", False):
        if storage.get("environment") == "production":
            return (
                "RED",
                "durable_storage_not_configured",
                "Set KYC_DATA env var in Render to point to the mounted persistent disk (e.g. /var/data).",
                ["durable_storage"] + mismatches,
            )

    if red_checks:
        first = red_checks[0]
        return ("RED", first["name"], _action_for(first, intake), mismatches)

    if amber_checks:
        first = amber_checks[0]
        return ("AMBER", first["name"], _action_for(first, intake), mismatches)

    queue_depth = int(intake.get("queue_depth") or 0)
    if queue_depth > 0:
        return (
            "GREEN",
            "none",
            f"Review the {queue_depth} pending intake(s) in the queue.",
            [],
        )
    return (
        "GREEN",
        "none",
        "Idle. Run the acquisition cycle to surface new leads.",
        [],
    )


def _action_for(check: Dict[str, Any], intake: Dict[str, Any]) -> str:
    name = check.get("name", "")
    ev = check.get("evidence") or {}
    if name == "beta_residue_scan":
        if ev.get("beta_imports_remaining"):
            return f"Remove founding_beta imports from: {', '.join(ev['beta_imports_remaining'][:3])}"
        if ev.get("beta_routes_remaining"):
            return f"Remove founding_beta routes from: {', '.join(ev['beta_routes_remaining'][:3])}"
        if ev.get("active_file_count", 0) > 0:
            return "Clean residual founding_beta strings from active source files."
        return "Residue is in docs/tests only — non-blocking."
    if name == "disk_vs_intake_index":
        return "Run /api/operator/intake/reconcile to reconcile disk and index."
    if name == "intake_index_vs_queue":
        return "Investigate why active intakes are not surfacing in the queue — check review_status fields."
    if name == "queue_vs_vio":
        return "Verify build_vio_overview is calling get_operator_review_queue with include_archived=True."
    if name == "evidence_vs_files":
        return "Run evidence intelligence extraction on uploaded files."
    if name == "archives_vs_active":
        return "Sanity check intake archive flags — counts do not sum."
    return "Investigate the failing check."

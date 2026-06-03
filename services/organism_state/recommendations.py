"""KYC recommendation registry — maps each check name to its next action."""
from __future__ import annotations

from organism_core import RecommendationRegistry
from organism_core.health.checks import CheckResult


def _beta_residue_action(r: CheckResult) -> str:
    ev = r.evidence or {}
    if ev.get("beta_imports_remaining"):
        return f"Remove founding_beta imports from: {', '.join(ev['beta_imports_remaining'][:3])}"
    if ev.get("beta_routes_remaining"):
        return f"Remove founding_beta routes from: {', '.join(ev['beta_routes_remaining'][:3])}"
    if ev.get("active_file_count", 0) > 0:
        return "Clean residual founding_beta strings from active source files."
    return "Residue is in docs/tests only — non-blocking."


def kyc_recommendations() -> RecommendationRegistry:
    reg = RecommendationRegistry(
        idle_action="Idle. Run the acquisition cycle to surface new leads.",
        active_action="Review pending intakes in the queue.",
        fallback="Investigate the failing check.",
    )
    reg.register_many({
        "disk_vs_intake_index": "Run /api/operator/intake/reconcile to reconcile disk and index.",
        "intake_index_vs_queue": "Investigate why active intakes are not surfacing in the queue — check review_status fields.",
        "queue_vs_vio": "Verify build_vio_overview is calling get_operator_review_queue with include_archived=True.",
        "queue_vs_control": "Control is healthy.",
        "evidence_vs_files": "Run evidence intelligence extraction on uploaded files.",
        "projects_vs_completed_intakes": "Sanity ok.",
        "archives_vs_active": "Sanity check intake archive flags — counts do not sum.",
        "beta_residue_scan": _beta_residue_action,
    })
    return reg

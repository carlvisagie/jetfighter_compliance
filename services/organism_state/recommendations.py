"""KYC recommendation registry — maps each check name to its next action."""
from __future__ import annotations

from organism_core import RecommendationRegistry
from organism_core.health.checks import CheckResult


def _pilot_residue_action(r: CheckResult) -> str:
    ev = r.evidence or {}
    if ev.get("pilot_imports_remaining"):
        return f"Remove founding_pilot imports from: {', '.join(ev['pilot_imports_remaining'][:3])}"
    if ev.get("pilot_routes_remaining"):
        return f"Remove founding_pilot routes from: {', '.join(ev['pilot_routes_remaining'][:3])}"
    if ev.get("active_file_count", 0) > 0:
        return "Clean residual founding_pilot strings from active source files."
    return "Residue is in docs/tests only — non-blocking."


def kyc_recommendations() -> RecommendationRegistry:
    reg = RecommendationRegistry(
        idle_action="Idle. Run the acquisition cycle to surface new leads.",
        active_action="Review pending intakes in the queue.",
        fallback="Investigate the failing check.",
    )
    reg.register_many({
        "disk_persistence_check": _disk_persistence_action,
        "disk_vs_intake_index": "Run /api/operator/intake/reconcile to reconcile disk and index.",
        "intake_index_vs_queue": "Investigate why active intakes are not surfacing in the queue — check review_status fields.",
        "queue_vs_vio": "Verify build_vio_overview is calling get_operator_review_queue with include_archived=True.",
        "queue_vs_control": "Control is healthy.",
        "evidence_vs_files": "Run evidence intelligence extraction on uploaded files.",
        "projects_vs_completed_intakes": "Sanity ok.",
        "archives_vs_active": "Sanity check intake archive flags — counts do not sum.",
        "pilot_residue_scan": _pilot_residue_action,
    })
    return reg


def _disk_persistence_action(r: CheckResult) -> str:
    state = (r.evidence or {}).get("state") or "unknown"
    if state == "verified_persistent":
        return "Disk substrate is persistent — no action."
    if state == "pending_first_restart":
        return (
            "Fresh disk — trigger one redeploy (Render dashboard or `gh api ...`) "
            "to confirm persistence. Uploads remain allowed."
        )
    if state == "ephemeral_lost":
        return (
            "SEV-1: previous customer data was likely destroyed. "
            "1) Stop accepting uploads (already blocked by intake gate). "
            "2) Inspect Render disks: any service that recently lost its mount? "
            "3) Review docs/KYC_UPLOAD_IMMUTABILITY_PROOF.md and the integrity_incidents.jsonl entry. "
            "4) Restore from snapshot if available. "
            "5) Re-attach the disk before clearing the marker."
        )
    if state == "write_failed":
        return "Storage is unwritable — check Render disk mount and disk space."
    if state == "unconfigured":
        return "Set KYC_DATA to a persistent disk mount path (e.g. /var/data on Render) and attach the disk."
    return f"Investigate disk persistence state: {state!r}"

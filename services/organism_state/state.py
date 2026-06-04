"""KYC adapter — assembles an organism_core AwarenessEngine for KYC.

This module preserves the legacy public API used by server.py and tests:

  - compute_organism_state()           -> dict (with KYC top-level keys)
  - write_organism_state_snapshot(...) -> Path
  - ORGANISM_STATE_PATH (callable)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from organism_core import AwarenessEngine, SignalBundle
from organism_core.persistence.snapshot_writer import (
    append_snapshot_history,
    read_snapshot_history,
    write_snapshot,
)

from services.organism_state.checks import all_checks
from services.organism_state.collectors import (
    DiskPersistenceCollector,
    EvidenceCollector,
    GitCollector,
    IntakeCollector,
    ProjectsCollector,
    SchedulerHeartbeatCollector,
    StorageCollector,
    VioCollector,
)
from services.organism_state.recommendations import kyc_recommendations
from services.organism_state.residue_config import kyc_residue_scanner

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _default_snapshot_path() -> Path:
    try:
        from services.durable_storage import active_data_root
        root = active_data_root()
    except Exception:
        root = _REPO_ROOT / "data"
    return Path(root) / "organism_state.json"


ORGANISM_STATE_PATH = _default_snapshot_path


def _kyc_gating(signals: SignalBundle):
    """
    In production, two substrate failures force RED before any other check runs:

    1. KYC_DATA misconfiguration → disk not even attempted.
    2. Disk persistence lost (`ephemeral_lost`) → previous boot's data destroyed.

    A fresh disk (`pending_first_restart`) is NOT RED — uploads still proceed
    and persistence is confirmed by the next restart. That state is AMBER in
    the check, surfaced as a warning, but does not gate the organism.
    """
    storage = signals.section("storage") or {}
    if storage.get("environment") == "production" and not storage.get("durable_storage_configured", False):
        return ("durable_storage_not_configured", "KYC_DATA env not configured in production")
    persistence = signals.section("disk_persistence") or {}
    state = (persistence.get("state") or "").lower()
    if storage.get("environment") == "production":
        if state == "ephemeral_lost":
            return (
                "disk_persistence_lost",
                "Disk birth marker missing on this boot — previous customer data likely destroyed.",
            )
        if state == "write_failed":
            return ("disk_persistence_write_failed", "Cannot write disk birth marker.")
    return None


def _kyc_workload(signals: SignalBundle) -> bool:
    """GREEN-with-work indicator: queue has pending items."""
    return int(signals.get("intake", "queue_depth", 0)) > 0


def build_kyc_engine(*, repo_root: Optional[Path] = None) -> AwarenessEngine:
    """Construct the canonical KYC AwarenessEngine."""
    root = (repo_root or _REPO_ROOT).resolve()

    projects = ProjectsCollector()

    def _project_ids_provider():
        return projects.collect().get("_all_project_ids", [])

    return AwarenessEngine(
        organism_name="kyc",
        collectors=[
            IntakeCollector(),
            VioCollector(),
            projects,
            EvidenceCollector(project_ids_provider=_project_ids_provider),
            StorageCollector(),
            DiskPersistenceCollector(),
            SchedulerHeartbeatCollector(),
            GitCollector(repo_root=root),
        ],
        checks=list(all_checks()),
        recommendations=kyc_recommendations(),
        residue_scanner=kyc_residue_scanner(),
        residue_root=root,
        snapshot_path=None,
        gating=_kyc_gating,
        green_workload_indicator=_kyc_workload,
        metadata={"product": "KYC Compliance"},
    )


def _flatten_for_legacy_api(core_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Lift KYC-specific signal fields to top-level for backwards compat.

    The legacy ``compute_organism_state()`` contract returned top-level
    keys like ``intake_count_total``, ``queue_depth``, ``vio_company_count``.
    The new core nests those under ``signals.<collector>``. We surface them
    so existing tests / server.py / control card keep working.
    """
    sigs = core_snapshot.get("signals", {}) or {}
    intake = sigs.get("intake", {}) or {}
    vio = sigs.get("vio", {}) or {}
    projects = sigs.get("projects", {}) or {}
    evidence = sigs.get("evidence", {}) or {}
    storage = sigs.get("storage", {}) or {}
    persistence = sigs.get("disk_persistence", {}) or {}
    git = sigs.get("git", {}) or {}
    residue = core_snapshot.get("residue", {}) or {}

    beta_imports: list = []
    beta_routes: list = []
    active_files: list = []
    for m in residue.get("matches", []):
        cls = m.get("classification")
        pid = m.get("pattern_id")
        rel = m.get("rel_path")
        if pid == "beta_import" and cls == "active":
            beta_imports.append(rel)
        elif pid == "beta_route" and cls == "active":
            beta_routes.append(rel)
        if cls == "active" and rel not in active_files:
            active_files.append(rel)

    cls_counts = residue.get("classification_counts") or {}
    legacy = dict(core_snapshot)
    legacy.update({
        "timestamp_utc": core_snapshot["timestamp_utc"],
        "git_commit": git.get("git_commit", ""),
        "deploy_commit": git.get("deploy_commit", ""),
        "environment": storage.get("environment", "development"),
        "data_root": storage.get("data_root", ""),
        "durable_storage_configured": bool(storage.get("durable_storage_configured", False)),
        "disk_persistence_state": persistence.get("state", "unknown"),
        "disk_persistence_verified": bool(persistence.get("verified", False)),
        "disk_persistence": dict(persistence),
        "intake_count_total": int(intake.get("intake_count_total", 0)),
        "intake_count_active": int(intake.get("intake_count_active", 0)),
        "intake_count_archived": int(intake.get("intake_count_archived", 0)),
        "uploaded_file_count": int(intake.get("uploaded_file_count", 0)),
        "evidence_artifact_count": int(evidence.get("evidence_artifact_count", 0)),
        "project_count": int(projects.get("project_count", 0)),
        "queue_depth": int(intake.get("queue_depth", 0)),
        "vio_company_count": int(vio.get("vio_company_count", 0)),
        "control_queue_count": int(intake.get("queue_depth", 0)),
        "beta_residue_detected": bool(residue.get("detected", False)),
        "beta_routes_remaining": beta_routes[:10],
        "beta_files_remaining": int(sum(cls_counts.values())) + len(residue.get("critical_paths", []) or []),
        "residue_detail": {
            "critical_count": int(residue.get("critical_count", 0)),
            "active_file_count": int(cls_counts.get("active", 0)),
            "docs_file_count": int(cls_counts.get("docs", 0)),
            "artifact_file_count": int(cls_counts.get("artifact", 0)),
            "active_files": active_files[:25],
            "beta_imports_remaining": beta_imports[:10],
        },
    })
    return legacy


def compute_organism_state(*, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Backward-compatible: build engine, run snapshot, flatten for legacy callers."""
    engine = build_kyc_engine(repo_root=repo_root)
    core_snapshot = engine.snapshot(persist=False)
    return _flatten_for_legacy_api(core_snapshot)


def write_organism_state_snapshot(state: Dict[str, Any], *, path: Optional[Path] = None) -> Path:
    target = Path(path) if path else _default_snapshot_path()
    written = write_snapshot(state, path=target)
    # Append-only history sidecar so operators can reconstruct the
    # awareness signal over time. Never raises on failure.
    append_snapshot_history(state, path=target)
    return written if written is not None else target


def load_organism_state_history(
    *, path: Optional[Path] = None, limit: int = 200
) -> list:
    """Return the most recent organism-state snapshots, oldest first.

    Backs the GET /api/operator/organism/history endpoint surfaced in
    the operator cockpit / VIO header strip.
    """
    target = Path(path) if path else _default_snapshot_path()
    return read_snapshot_history(target, limit=limit)

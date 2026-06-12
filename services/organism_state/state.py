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
    UnconfirmedPaymentsCollector,
    VioCollector,
    CognitionValidationCollector,
    ComplianceIntelligenceStatusCollector,
)
from services.organism_state.recommendations import kyc_recommendations
from services.organism_state.residue_config import kyc_residue_scanner

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_intake_for_project(project_id: str) -> Optional[str]:
    """Extract intake ID from project ID."""
    # Project IDs are formatted like: P-FB-xxxx-timestamp
    if not project_id:
        return None
    parts = project_id.split("-")
    if len(parts) >= 3 and parts[0] == "P" and parts[1] == "FB":
        # Reconstruct intake ID: FB-{middle_parts}
        # P-FB-97bbf7703-20260611T113217Z -> FB-97bbf7703e74 (need original intake_id)
        return None  # Can't reliably reconstruct, need VIO mapping
    return None


def _compute_classification_health(
    core_snapshot: Dict[str, Any],
    classifications: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """PATCH PRODUCTION-ONLY-2: Compute classification-aware health metrics."""
    
    # Build intake->classification mapping
    intake_class_map: Dict[str, str] = {}
    for intake_id, record in classifications.items():
        intake_class_map[intake_id] = record.get("classification", "UNKNOWN")
    
    # Get checks from core snapshot
    checks = core_snapshot.get("checks", []) or []
    health_state = core_snapshot.get("health_state", "UNKNOWN")
    
    # Count projects by classification using VIO data
    try:
        from services.vio_overview import build_vio_overview
        vio = build_vio_overview(limit=500, include_organism=False) or {}
        companies = vio.get("companies", []) or []
    except Exception:
        companies = []
    
    # Build project->intake mapping from VIO
    project_intake_map: Dict[str, str] = {}
    for company in companies:
        intake_id = company.get("intake_id")
        project_id = company.get("project_id")
        if intake_id and project_id:
            project_intake_map[project_id] = intake_id
    
    # Count projects by classification
    real_project_count = 0
    test_project_count = 0
    validation_project_count = 0
    
    for project_id, intake_id in project_intake_map.items():
        cls = intake_class_map.get(intake_id, "UNKNOWN")
        if cls == "REAL":
            real_project_count += 1
        elif cls == "TEST":
            test_project_count += 1
        elif cls == "VALIDATION":
            validation_project_count += 1
    
    # Analyze blockers by classification
    # A blocker is a RED check - need to identify which projects cause each RED
    real_blockers: List[Dict[str, Any]] = []
    test_blockers: List[Dict[str, Any]] = []
    validation_blockers: List[Dict[str, Any]] = []
    demo_blockers: List[Dict[str, Any]] = []
    unknown_blockers: List[Dict[str, Any]] = []
    
    for check in checks:
        if check.get("severity") != "RED":
            continue
        
        check_name = check.get("name", "")
        evidence = check.get("evidence", {}) or {}
        
        # Determine if this blocker is caused by real or test data
        # For cognition/compliance checks, we need to look at which projects are involved
        affected_projects = []
        
        # Check if evidence contains project-related info
        if "projects_with_safety_warnings" in evidence or "projects_checked" in evidence:
            # This is a cognition check - all projects in the system
            affected_projects = list(project_intake_map.keys())
        elif "coverage_data" in evidence:
            # Compliance coverage - affects all projects
            affected_projects = list(project_intake_map.keys())
        
        # Classify blocker by project types involved
        blocker_by_real = False
        blocker_by_test = False
        blocker_by_validation = False
        
        for proj_id in affected_projects:
            intake_id = project_intake_map.get(proj_id)
            if not intake_id:
                continue
            cls = intake_class_map.get(intake_id, "UNKNOWN")
            if cls == "REAL":
                blocker_by_real = True
            elif cls == "TEST":
                blocker_by_test = True
            elif cls == "VALIDATION":
                blocker_by_validation = True
        
        blocker_info = {
            "check_name": check_name,
            "detail": check.get("detail", ""),
            "affected_project_count": len(affected_projects),
        }
        
        # If blocker affects real projects, it's a real blocker
        # If only test/validation, it's test contamination
        if blocker_by_real:
            real_blockers.append(blocker_info)
        elif blocker_by_test:
            test_blockers.append(blocker_info)
        elif blocker_by_validation:
            validation_blockers.append(blocker_info)
        elif affected_projects:
            # Has projects but couldn't classify
            unknown_blockers.append(blocker_info)
        else:
            # No projects affected - likely test contamination or missing classification
            test_blockers.append(blocker_info)
    
    # Calculate health states
    all_red_checks = [c for c in checks if c.get("severity") == "RED"]
    all_amber_checks = [c for c in checks if c.get("severity") == "AMBER"]
    
    # ALL_DATA_HEALTH: Current overall health
    all_data_health = health_state
    
    # REAL_ONLY_HEALTH: Health if we only count real customers
    # If there are no real projects and no real blockers, health is GREEN
    if real_project_count == 0 and len(real_blockers) == 0:
        real_only_health = "GREEN"
    elif len(real_blockers) > 0:
        real_only_health = "RED"
    else:
        real_only_health = "GREEN"
    
    # TEST_ONLY_HEALTH: Health of test/validation data
    if (test_project_count + validation_project_count) == 0:
        test_only_health = "N/A"
    elif len(test_blockers) + len(validation_blockers) > 0:
        test_only_health = "RED"
    else:
        test_only_health = "GREEN"
    
    # REAL_ONLY_LAUNCH_VERDICT
    if real_project_count == 0:
        real_only_launch_verdict = "NO_REAL_CUSTOMERS"
    elif len(real_blockers) > 0:
        real_only_launch_verdict = "BLOCKED"
    else:
        real_only_launch_verdict = "READY"
    
    return {
        "real_project_count": real_project_count,
        "test_project_count": test_project_count,
        "validation_project_count": validation_project_count,
        "real_blocker_count": len(real_blockers),
        "test_blocker_count": len(test_blockers),
        "validation_blocker_count": len(validation_blockers),
        "demo_blocker_count": len(demo_blockers),
        "unknown_blocker_count": len(unknown_blockers),
        "all_data_health": all_data_health,
        "real_only_health": real_only_health,
        "test_only_health": test_only_health,
        "real_only_launch_verdict": real_only_launch_verdict,
        "real_blockers": real_blockers,
        "test_blockers": test_blockers,
        "validation_blockers": validation_blockers,
    }


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
            UnconfirmedPaymentsCollector(),
            GitCollector(repo_root=root),
            CognitionValidationCollector(),
            ComplianceIntelligenceStatusCollector(),
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
    ci_status = sigs.get("compliance_intelligence_status", {}) or {}
    residue = core_snapshot.get("residue", {}) or {}

    pilot_imports: list = []
    pilot_routes: list = []
    active_files: list = []
    for m in residue.get("matches", []):
        cls = m.get("classification")
        pid = m.get("pattern_id")
        rel = m.get("rel_path")
        if pid == "legacy_import" and cls == "active":
            pilot_imports.append(rel)
        elif pid == "legacy_route" and cls == "active":
            pilot_routes.append(rel)
        if cls == "active" and rel not in active_files:
            active_files.append(rel)

    cls_counts = residue.get("classification_counts") or {}
    
    # PATCH 13A-9: Add intake classification summary for operational purification
    try:
        from services.intake.classification import get_classification_summary, load_classifications
        classification_summary = get_classification_summary()
        all_classifications = load_classifications()
    except Exception:
        classification_summary = {
            "real_customer_count": 0,
            "first_real_customer_arrived": False,
            "by_type": {},
        }
        all_classifications = {}
    
    # PATCH PRODUCTION-ONLY-2: Classification-aware health
    try:
        classification_health = _compute_classification_health(core_snapshot, all_classifications)
    except Exception:
        classification_health = {
            "real_project_count": 0,
            "test_project_count": 0,
            "validation_project_count": 0,
            "real_blocker_count": 0,
            "test_blocker_count": 0,
            "validation_blocker_count": 0,
            "demo_blocker_count": 0,
            "unknown_blocker_count": 0,
            "all_data_health": "UNKNOWN",
            "real_only_health": "GREEN",
            "test_only_health": "UNKNOWN",
            "real_only_launch_verdict": "UNKNOWN",
        }
    
    # PATCH 13A-12: Add customer intelligence metrics
    try:
        from services.acquisition.ideal_customer_profile import get_intelligence_summary
        intelligence_summary = get_intelligence_summary()
    except Exception:
        intelligence_summary = {
            "total_records": 0,
            "by_icp_tier": {},
            "by_recommendation": {},
            "intelligence_completeness": {},
            "contactable": 0,
            "average_completeness": 0,
        }
    
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
        "compliance_intelligence": dict(ci_status),
        "pilot_residue_detected": bool(residue.get("detected", False)),
        "pilot_routes_remaining": pilot_routes[:10],
        "pilot_files_remaining": int(sum(cls_counts.values())) + len(residue.get("critical_paths", []) or []),
        "residue_detail": {
            "critical_count": int(residue.get("critical_count", 0)),
            "active_file_count": int(cls_counts.get("active", 0)),
            "docs_file_count": int(cls_counts.get("docs", 0)),
            "artifact_file_count": int(cls_counts.get("artifact", 0)),
            "active_files": active_files[:25],
            "pilot_imports_remaining": pilot_imports[:10],
        },
        # PATCH 13A-9: First customer detection metrics
        "real_customer_count": classification_summary.get("real_customer_count", 0),
        "first_real_customer_arrived": classification_summary.get("first_real_customer_arrived", False),
        "first_real_customer_id": classification_summary.get("first_real_customer_id"),
        "classification_summary": classification_summary,
        # PATCH 13A-12: Customer Intelligence Engine metrics
        "discovered_entities": intelligence_summary.get("total_records", 0),
        "qualified_entities": (
            intelligence_summary.get("by_icp_tier", {}).get("TIER_1", 0) +
            intelligence_summary.get("by_icp_tier", {}).get("TIER_2", 0)
        ),
        "intelligence_complete_entities": intelligence_summary.get("intelligence_completeness", {}).get("81-100", 0),
        "contactable_entities": intelligence_summary.get("contactable", 0),
        "ideal_customers": intelligence_summary.get("by_icp_tier", {}).get("TIER_1", 0),
        "unknown_entities": intelligence_summary.get("by_recommendation", {}).get("ENRICH", 0),
        "intelligence_summary": intelligence_summary,
        # PATCH PRODUCTION-ONLY-2: Classification-aware health
        "real_project_count": classification_health.get("real_project_count", 0),
        "test_project_count": classification_health.get("test_project_count", 0),
        "validation_project_count": classification_health.get("validation_project_count", 0),
        "real_blocker_count": classification_health.get("real_blocker_count", 0),
        "test_blocker_count": classification_health.get("test_blocker_count", 0),
        "validation_blocker_count": classification_health.get("validation_blocker_count", 0),
        "demo_blocker_count": classification_health.get("demo_blocker_count", 0),
        "unknown_blocker_count": classification_health.get("unknown_blocker_count", 0),
        "all_data_health": classification_health.get("all_data_health", "UNKNOWN"),
        "real_only_health": classification_health.get("real_only_health", "GREEN"),
        "test_only_health": classification_health.get("test_only_health", "UNKNOWN"),
        "real_only_launch_verdict": classification_health.get("real_only_launch_verdict", "UNKNOWN"),
        "classification_health": classification_health,
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

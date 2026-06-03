"""Compute and persist the organism state snapshot."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .detector import (
    collect_evidence_signals,
    collect_git_signals,
    collect_intake_signals,
    collect_project_signals,
    collect_storage_signals,
    collect_vio_signals,
    run_reconciliation_checks,
)
from .health import derive_health
from .residue import scan_repo_for_beta_residue

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _organism_state_path(data_root: Optional[Path] = None) -> Path:
    """Snapshot lives in the durable data root, not in the repo."""
    if data_root is None:
        try:
            from services.durable_storage import active_data_root
            data_root = active_data_root()
        except Exception:
            data_root = _REPO_ROOT / "data"
    return Path(data_root) / "organism_state.json"


ORGANISM_STATE_PATH = _organism_state_path


def compute_organism_state(*, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Reconcile every source of truth and return a single state document."""
    root = (repo_root or _REPO_ROOT).resolve()

    storage = collect_storage_signals()
    intake = collect_intake_signals()
    vio = collect_vio_signals()
    projects = collect_project_signals()
    evidence = collect_evidence_signals(projects.get("project_ids_sample") or [])
    residue = scan_repo_for_beta_residue(root)
    git = collect_git_signals()

    checks = run_reconciliation_checks(
        intake=intake,
        vio=vio,
        projects=projects,
        evidence=evidence,
        residue=residue,
    )

    health, bottleneck, next_action, mismatches = derive_health(
        checks,
        intake=intake,
        storage=storage,
    )

    return {
        "ok": True,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": git.get("git_commit", ""),
        "deploy_commit": git.get("deploy_commit", ""),
        "environment": storage.get("environment", "development"),
        "data_root": storage.get("data_root", ""),
        "durable_storage_configured": storage.get("durable_storage_configured", False),
        "intake_count_total": intake.get("intake_count_total", 0),
        "intake_count_active": intake.get("intake_count_active", 0),
        "intake_count_archived": intake.get("intake_count_archived", 0),
        "uploaded_file_count": intake.get("uploaded_file_count", 0),
        "evidence_artifact_count": evidence.get("evidence_artifact_count", 0),
        "project_count": projects.get("project_count", 0),
        "queue_depth": intake.get("queue_depth", 0),
        "vio_company_count": vio.get("vio_company_count", 0),
        "control_queue_count": intake.get("queue_depth", 0),
        "beta_residue_detected": residue.get("beta_residue_detected", False),
        "beta_routes_remaining": residue.get("beta_routes_remaining", []),
        "beta_files_remaining": residue.get("beta_files_remaining", 0),
        "visibility_mismatches": mismatches,
        "health_state": health,
        "current_bottleneck": bottleneck,
        "next_recommended_action": next_action,
        "checks": checks,
        "residue_detail": {
            "critical_count": residue.get("critical_count", 0),
            "active_file_count": residue.get("active_file_count", 0),
            "docs_file_count": residue.get("docs_file_count", 0),
            "artifact_file_count": residue.get("artifact_file_count", 0),
            "active_files": residue.get("active_files", []),
            "beta_imports_remaining": residue.get("beta_imports_remaining", []),
        },
    }


def write_organism_state_snapshot(state: Dict[str, Any], *, path: Optional[Path] = None) -> Path:
    """Persist the snapshot to data/organism_state.json (best-effort)."""
    target = path or _organism_state_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        logger.warning("organism_state: snapshot write failed (%s): %s", target, exc)
    return target

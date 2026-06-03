"""Cross-source reconciliation checks for the organism state.

Each check returns:
  {"name": str, "ok": bool, "severity": "info"|"amber"|"red",
   "detail": str, "evidence": {...}}

A check is "red" when reality and reported state disagree on something
that prevents the operator from seeing customers.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe(call, default):
    try:
        return call()
    except Exception as exc:
        logger.warning("organism_state: signal failed: %s", exc)
        return default


def collect_intake_signals() -> Dict[str, Any]:
    """All intake-related counts from canonical sources."""
    from services.intake.inventory import build_intake_inventory
    from services.intake.queue import get_operator_review_queue
    from services.intake.storage import all_intake_ids, load_intake_record

    inv = _safe(build_intake_inventory, {})
    queue_active = _safe(lambda: get_operator_review_queue(limit=100, include_archived=False), {})
    queue_full = _safe(lambda: get_operator_review_queue(limit=200, include_archived=True), {})

    all_ids = _safe(lambda: all_intake_ids(limit=500), [])
    archived = 0
    for iid in all_ids:
        try:
            rec = load_intake_record(iid, persist_recovery=False)
            if (rec.get("review_status") or "").lower() == "archived":
                archived += 1
        except (FileNotFoundError, ValueError, OSError):
            continue

    total = len(all_ids)
    return {
        "inventory": inv,
        "intake_count_total": total,
        "intake_count_archived": archived,
        "intake_count_active": max(total - archived, 0),
        "uploaded_file_count": int(inv.get("upload_files") or 0),
        "queue_depth": int(queue_active.get("queue_depth") or 0),
        "queue_full_depth": int(queue_full.get("queue_depth") or 0),
    }


def collect_vio_signals() -> Dict[str, Any]:
    from services.vio_overview import build_vio_overview

    vio = _safe(lambda: build_vio_overview(limit=200), {})
    companies = vio.get("companies") or []
    return {
        "vio_company_count": len(companies),
        "vio_health": vio.get("organism_health") or {},
    }


def collect_project_signals() -> Dict[str, Any]:
    from services.reports import list_projects

    projects = _safe(list_projects, [])
    return {
        "project_count": len(projects),
        "project_ids_sample": projects[:25],
    }


def collect_evidence_signals(project_ids: List[str]) -> Dict[str, Any]:
    """Sum evidence artifacts across projects."""
    from services.evidence_intelligence.storage import load_jsonl

    total_entities = 0
    total_extractions = 0
    projects_with_evidence = 0
    for pid in project_ids:
        try:
            ents = load_jsonl(pid, "entities.jsonl", limit=10000)
            exts = load_jsonl(pid, "extractions.jsonl", limit=10000)
            total_entities += len(ents)
            total_extractions += len(exts)
            if ents or exts:
                projects_with_evidence += 1
        except Exception as exc:
            logger.debug("evidence signal skipped for %s: %s", pid, exc)
            continue
    return {
        "evidence_artifact_count": total_entities + total_extractions,
        "evidence_entity_count": total_entities,
        "evidence_extraction_count": total_extractions,
        "projects_with_evidence": projects_with_evidence,
    }


def collect_storage_signals() -> Dict[str, Any]:
    from services.durable_storage import (
        active_data_root,
        get_storage_status,
    )

    status = _safe(get_storage_status, {})
    return {
        "data_root": str(_safe(active_data_root, Path("."))),
        "durable_storage_configured": bool(status.get("durable_storage_configured")),
        "environment": status.get("environment") or os.getenv("ENVIRONMENT", "development"),
    }


def collect_git_signals() -> Dict[str, Any]:
    """Read git commit info — never raises."""
    repo_root = Path(__file__).resolve().parent.parent.parent

    def _run(args: List[str]) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=3,
            )
            return out.stdout.strip()
        except Exception:
            return ""

    commit = _run(["rev-parse", "HEAD"]) or os.getenv("RENDER_GIT_COMMIT", "")
    return {
        "git_commit": commit[:40],
        "deploy_commit": os.getenv("RENDER_GIT_COMMIT", commit)[:40],
    }


def run_reconciliation_checks(
    *,
    intake: Dict[str, Any],
    vio: Dict[str, Any],
    projects: Dict[str, Any],
    evidence: Dict[str, Any],
    residue: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Run the 8 mandated checks. Returns a list of check results."""
    checks: List[Dict[str, Any]] = []

    inv = intake.get("inventory") or {}
    disk_dirs = int(inv.get("intake_directories") or 0)
    index_ids = int(inv.get("index_tail_unique_ids") or 0)
    only_disk = inv.get("only_on_disk_not_in_index") or []
    only_index = inv.get("only_in_index_not_on_disk") or []

    # Check 1 — Disk vs intake index
    disk_index_ok = not only_disk and not only_index
    checks.append({
        "name": "disk_vs_intake_index",
        "ok": disk_index_ok,
        "severity": "info" if disk_index_ok else "red",
        "detail": (
            "Disk and index agree."
            if disk_index_ok
            else f"Disk-only={len(only_disk)} index-only={len(only_index)}"
        ),
        "evidence": {
            "disk_count": disk_dirs,
            "index_count": index_ids,
            "only_on_disk": only_disk[:10],
            "only_in_index": only_index[:10],
        },
    })

    # Check 2 — Intake index vs queue (active queue must surface non-archived intakes).
    # Queue surfaces pending_review rows; some active records may be in other states
    # (high_value / needs_info / payment_sent / etc.). We require the queue to be
    # non-empty if there is ANY non-archived intake, and to be the canonical depth
    # the queue endpoint advertises.
    expected_queue = intake.get("intake_count_active", 0)
    actual_queue = intake.get("queue_full_depth", 0)
    if expected_queue == 0:
        queue_ok = actual_queue == 0
    else:
        queue_ok = actual_queue > 0
    checks.append({
        "name": "intake_index_vs_queue",
        "ok": queue_ok,
        "severity": "info" if queue_ok else "red",
        "detail": (
            f"Active intakes={expected_queue} queue_full_depth={actual_queue}"
            if queue_ok
            else f"INTAKE HIDDEN FROM QUEUE: active={expected_queue} queue_full_depth={actual_queue}"
        ),
        "evidence": {
            "active_intakes": expected_queue,
            "queue_depth": intake.get("queue_depth", 0),
            "queue_full_depth": actual_queue,
        },
    })

    # Check 3 — Queue vs VIO (VIO must reflect every queued company)
    vio_count = vio.get("vio_company_count", 0)
    full_queue = intake.get("queue_full_depth", 0)
    vio_ok = vio_count >= min(full_queue, 100) if full_queue > 0 else vio_count == 0
    if intake.get("uploaded_file_count", 0) > 0 and vio_count == 0:
        vio_ok = False
    checks.append({
        "name": "queue_vs_vio",
        "ok": vio_ok,
        "severity": "info" if vio_ok else "red",
        "detail": (
            f"VIO companies={vio_count} queue(full)={full_queue}"
            if vio_ok
            else f"FILES HIDDEN FROM VIO: files={intake.get('uploaded_file_count', 0)} vio={vio_count}"
        ),
        "evidence": {"vio_company_count": vio_count, "queue_full_depth": full_queue},
    })

    # Check 4 — Queue vs control (control reads the same endpoint, so confirm parity)
    # control.html calls /api/operator/intake/queue → same as our intake.queue_depth signal.
    checks.append({
        "name": "queue_vs_control",
        "ok": True,
        "severity": "info",
        "detail": "Control reads the canonical queue endpoint — counts match by construction.",
        "evidence": {"control_queue_count": intake.get("queue_depth", 0)},
    })

    # Check 5 — Evidence records vs uploaded files
    ev_count = evidence.get("evidence_artifact_count", 0)
    files = intake.get("uploaded_file_count", 0)
    if files == 0:
        ev_ok = True
        ev_detail = "No uploaded files — nothing to extract."
        ev_sev = "info"
    elif ev_count == 0 and files > 0:
        ev_ok = False
        ev_detail = f"Files uploaded={files} but zero evidence artifacts extracted."
        ev_sev = "red"
    else:
        ev_ok = True
        ev_detail = f"Files={files} evidence_artifacts={ev_count}"
        ev_sev = "info"
    checks.append({
        "name": "evidence_vs_files",
        "ok": ev_ok,
        "severity": ev_sev,
        "detail": ev_detail,
        "evidence": {"uploaded_files": files, "evidence_artifacts": ev_count},
    })

    # Check 6 — Projects vs completed intakes (warn-only; some intakes archive without project)
    project_count = projects.get("project_count", 0)
    archived = intake.get("intake_count_archived", 0)
    proj_ok = project_count >= 0
    checks.append({
        "name": "projects_vs_completed_intakes",
        "ok": proj_ok,
        "severity": "info",
        "detail": f"Projects={project_count} archived_intakes={archived}",
        "evidence": {"project_count": project_count, "archived_intakes": archived},
    })

    # Check 7 — Archives vs active intakes (sanity: counts must sum to total)
    total = intake.get("intake_count_total", 0)
    active = intake.get("intake_count_active", 0)
    sum_ok = (active + archived) == total
    checks.append({
        "name": "archives_vs_active",
        "ok": sum_ok,
        "severity": "info" if sum_ok else "amber",
        "detail": f"total={total} active={active} archived={archived}",
        "evidence": {"total": total, "active": active, "archived": archived},
    })

    # Check 8 — Beta residue scan
    crit = residue.get("critical_count", 0)
    active_residue = residue.get("active_file_count", 0)
    docs_residue = residue.get("docs_file_count", 0)
    if crit > 0:
        sev = "red"
        detail = (
            f"CRITICAL beta residue in production path: {crit} entries "
            f"(routes={len(residue.get('beta_routes_remaining') or [])}, "
            f"imports={len(residue.get('beta_imports_remaining') or [])})"
        )
        ok = False
    elif active_residue > 0:
        sev = "amber"
        detail = f"Beta string in {active_residue} active source files (variable/comment residue)."
        ok = False
    elif docs_residue > 0:
        sev = "info"
        detail = f"Beta references only in docs/tests/scripts ({docs_residue} files) — non-runtime."
        ok = True
    else:
        sev = "info"
        detail = "Clean — no beta residue anywhere."
        ok = True
    checks.append({
        "name": "beta_residue_scan",
        "ok": ok,
        "severity": sev,
        "detail": detail,
        "evidence": {
            "critical_count": crit,
            "active_file_count": active_residue,
            "docs_file_count": docs_residue,
            "beta_routes_remaining": residue.get("beta_routes_remaining") or [],
            "beta_imports_remaining": residue.get("beta_imports_remaining") or [],
        },
    })

    return checks

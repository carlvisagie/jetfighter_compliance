"""KYC-specific SignalCollectors — domain adapters over canonical sources."""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from organism_core import SignalCollector

logger = logging.getLogger(__name__)


class IntakeCollector(SignalCollector):
    name = "intake"

    def collect(self) -> Dict[str, Any]:
        from services.intake.inventory import build_intake_inventory
        from services.intake.queue import get_operator_review_queue
        from services.intake.storage import all_intake_ids, load_intake_record

        inv = build_intake_inventory() or {}
        queue_active = get_operator_review_queue(limit=100, include_archived=False) or {}
        queue_full = get_operator_review_queue(limit=200, include_archived=True) or {}

        ids = all_intake_ids(limit=500)
        archived = 0
        for iid in ids:
            try:
                rec = load_intake_record(iid, persist_recovery=False)
                if (rec.get("review_status") or "").lower() == "archived":
                    archived += 1
            except (FileNotFoundError, ValueError, OSError):
                continue
        total = len(ids)
        return {
            "inventory": inv,
            "intake_count_total": total,
            "intake_count_archived": archived,
            "intake_count_active": max(total - archived, 0),
            "uploaded_file_count": int(inv.get("upload_files") or 0),
            "queue_depth": int(queue_active.get("queue_depth") or 0),
            "queue_full_depth": int(queue_full.get("queue_depth") or 0),
        }


class VioCollector(SignalCollector):
    name = "vio"

    def collect(self) -> Dict[str, Any]:
        from services.vio_overview import build_vio_overview

        # include_organism=False prevents infinite recursion:
        # build_vio_overview → _organism_summary → compute_organism_state → VioCollector
        vio = build_vio_overview(limit=200, include_organism=False) or {}
        companies = vio.get("companies") or []
        return {
            "vio_company_count": len(companies),
            "vio_health": vio.get("organism_health") or {},
        }


class ProjectsCollector(SignalCollector):
    name = "projects"

    def collect(self) -> Dict[str, Any]:
        from services.reports import list_projects

        projects = list_projects() or []
        return {
            "project_count": len(projects),
            "project_ids_sample": projects[:25],
            "_all_project_ids": projects,
        }


class EvidenceCollector(SignalCollector):
    """Counts evidence artifacts across all projects.

    Depends on ProjectsCollector having run already (the engine runs
    collectors in registration order, so register Projects first).
    """

    name = "evidence"

    def __init__(self, project_ids_provider):
        self._provider = project_ids_provider

    def collect(self) -> Dict[str, Any]:
        from services.evidence_intelligence.storage import load_jsonl

        pids: List[str] = list(self._provider() or [])
        ents = 0
        exts = 0
        with_evidence = 0
        for pid in pids:
            try:
                e = load_jsonl(pid, "entities.jsonl", limit=10000)
                x = load_jsonl(pid, "extractions.jsonl", limit=10000)
            except Exception:
                continue
            ents += len(e)
            exts += len(x)
            if e or x:
                with_evidence += 1
        return {
            "evidence_artifact_count": ents + exts,
            "evidence_entity_count": ents,
            "evidence_extraction_count": exts,
            "projects_with_evidence": with_evidence,
        }


class StorageCollector(SignalCollector):
    name = "storage"

    def collect(self) -> Dict[str, Any]:
        from services.durable_storage import active_data_root, get_storage_status

        status = get_storage_status() or {}
        return {
            "data_root": str(active_data_root()),
            "durable_storage_configured": bool(status.get("durable_storage_configured")),
            "environment": status.get("environment") or os.getenv("ENVIRONMENT", "development"),
        }


class GitCollector(SignalCollector):
    name = "git"

    def __init__(self, repo_root: Path):
        self._root = Path(repo_root)

    def collect(self) -> Dict[str, Any]:
        commit = self._git(["rev-parse", "HEAD"]) or os.getenv("RENDER_GIT_COMMIT", "")
        return {
            "git_commit": commit[:40],
            "deploy_commit": os.getenv("RENDER_GIT_COMMIT", commit)[:40],
        }

    def _git(self, args: List[str]) -> str:
        try:
            out = subprocess.run(
                ["git", *args], cwd=str(self._root),
                capture_output=True, text=True, timeout=3,
            )
            return out.stdout.strip()
        except Exception:
            return ""

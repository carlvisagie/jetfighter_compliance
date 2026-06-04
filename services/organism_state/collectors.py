"""KYC-specific SignalCollectors — domain adapters over canonical sources."""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from organism_core import SignalCollector

logger = logging.getLogger(__name__)


def _parse_utc(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        clean = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


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


class DiskPersistenceCollector(SignalCollector):
    """
    Observes the disk-substrate proof — distinct from StorageCollector which
    only knows "is KYC_DATA writable". This collector knows "did the disk
    survive a restart".

    Contract: docs/KYC_UPLOAD_IMMUTABILITY_PROOF.md (2026-06-04 incident).
    The first probe per process writes the birth marker and emits a
    telemetry row (`storage / disk_persistence_probe`). Subsequent probes
    return the cached verdict.
    """

    name = "disk_persistence"

    def collect(self) -> Dict[str, Any]:
        from services.durable_storage import disk_persistence_status

        s = disk_persistence_status() or {}
        return {
            "state": s.get("state") or "unknown",
            "verified": bool(s.get("verified")),
            "marker_path": s.get("marker_path"),
            "marker_birth_utc": s.get("marker_birth_utc"),
            "marker_birth_disk_id": s.get("marker_birth_disk_id"),
            "age_before_process_seconds": s.get("age_before_process_seconds"),
            "process_started_utc": s.get("process_started_utc"),
        }


class UnconfirmedPaymentsCollector(SignalCollector):
    """Counts intakes whose payment link is unconfirmed past the SLA.

    Forensic-audit fix (2026-06-04, Revenue Pipeline): payment links
    are generated but no PayPal webhook closes the loop. Until an
    operator manually confirms via the new
    `confirm_payment_received` action, the platform has no idea who
    paid. This collector quantifies the gap so the awareness layer
    can flag it.

    Threshold defaults to 24h; tune via `KYC_PAYMENT_CONFIRM_SLA_H`.
    """

    name = "unconfirmed_payments"

    def __init__(self, *, sla_hours_default: int = 24):
        try:
            self._sla = int(
                os.environ.get("KYC_PAYMENT_CONFIRM_SLA_H")
                or sla_hours_default
            )
        except (TypeError, ValueError):
            self._sla = sla_hours_default

    def collect(self) -> Dict[str, Any]:
        from services.intake.storage import all_intake_ids, load_intake_record

        now_utc = datetime.now(timezone.utc)
        sla_secs = max(1, self._sla) * 3600
        breached: List[Dict[str, Any]] = []
        pending = 0
        confirmed = 0
        for iid in all_intake_ids(limit=500):
            try:
                rec = load_intake_record(iid, persist_recovery=False)
            except (FileNotFoundError, ValueError, OSError):
                continue
            payment = rec.get("payment") or {}
            sent_at = _parse_utc(
                payment.get("payment_link_generated_at_utc")
            )
            if not sent_at:
                continue
            if payment.get("payment_received_at_utc"):
                confirmed += 1
                continue
            pending += 1
            age = int((now_utc - sent_at).total_seconds())
            if age > sla_secs:
                breached.append({
                    "intake_id": iid,
                    "product_id":   payment.get("product_id"),
                    "age_seconds": age,
                    "age_hours":   round(age / 3600.0, 1),
                    "sent_utc":    payment.get(
                                      "payment_link_generated_at_utc"),
                })
        breached.sort(key=lambda r: -int(r.get("age_seconds") or 0))
        return {
            "sla_hours":       self._sla,
            "links_confirmed": confirmed,
            "links_pending":   pending,
            "links_breached":  len(breached),
            "samples":         breached[:10],
        }


class SchedulerHeartbeatCollector(SignalCollector):
    """Observes the background scheduler's pulse.

    Forensic-audit fix (2026-06-04, Organism Awareness): the scheduler
    emits `system / scheduler_*` telemetry rows when it starts, when
    organs are registered, and when each periodic job runs. Until now
    nothing read those rows back — so a silently-starved scheduler
    looked identical to a healthy one in the awareness layer.

    This collector scans recent telemetry and surfaces:
      • `last_started_utc`   — most recent scheduler_started row
      • `last_organ_run_utc` — most recent scheduler_*_ran row
      • `seconds_since_last_run`
      • `recent_failure_count`
      • `expected_max_interval_seconds` — what the awareness check
        treats as "still alive" (defaults to 90 minutes — slightly
        more than the longest interval job to avoid false alarms).
    """

    name = "scheduler_heartbeat"

    # Job IDs we expect to fire periodically.
    _LIVENESS_EVENTS = {
        "scheduler_started",
        "scheduler_organ_registered",
        "scheduler_organ_module_registered",
        "scheduler_forensic_reconcile_ran",
    }
    _FAILURE_EVENTS = {
        "scheduler_create_failed",
        "scheduler_start_failed",
        "scheduler_organ_failed",
        "scheduler_organ_module_failed",
        "scheduler_forensic_reconcile_failed",
        "scheduler_forensic_reconcile_import_failed",
    }

    def __init__(self, *, expected_max_interval_seconds: int = 90 * 60):
        self._expected = int(expected_max_interval_seconds)

    def collect(self) -> Dict[str, Any]:
        try:
            from services.memory.telemetry import load_telemetry
        except Exception:
            return {
                "available": False,
                "reason": "telemetry_unavailable",
            }

        try:
            rows = load_telemetry(limit=500) or []
        except Exception:
            return {
                "available": False,
                "reason": "telemetry_read_failed",
            }

        last_started: Optional[datetime] = None
        last_run: Optional[datetime] = None
        recent_failures = 0
        sample_failures: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            event = str(row.get("event_type") or row.get("event") or "")
            ts = _parse_utc(
                row.get("created_utc")
                or row.get("ts")
                or row.get("timestamp")
            )
            if not ts:
                continue
            if event == "scheduler_started" and (
                last_started is None or ts > last_started
            ):
                last_started = ts
            if event in self._LIVENESS_EVENTS and (
                last_run is None or ts > last_run
            ):
                last_run = ts
            if event in self._FAILURE_EVENTS:
                recent_failures += 1
                if len(sample_failures) < 5:
                    sample_failures.append({
                        "event": event,
                        "ts": row.get("created_utc")
                              or row.get("ts")
                              or row.get("timestamp"),
                        "message": row.get("message"),
                    })

        now_utc = datetime.now(timezone.utc)
        seconds_since_last_run = (
            int((now_utc - last_run).total_seconds()) if last_run else None
        )
        return {
            "available":              True,
            "last_started_utc":       last_started.isoformat().replace(
                                          "+00:00", "Z")
                                      if last_started else None,
            "last_organ_run_utc":     last_run.isoformat().replace(
                                          "+00:00", "Z")
                                      if last_run else None,
            "seconds_since_last_run": seconds_since_last_run,
            "expected_max_interval_seconds": self._expected,
            "recent_failure_count":   recent_failures,
            "recent_failure_samples": sample_failures,
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

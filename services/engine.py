import json, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler

from .config import DATA, SETTINGS
from .projects import new_project
from .emails import send_email
from .security import make_intake_token
from .ledger import record_event, register_artifact
from .reports import export_binder, list_projects, project_changed_within, send_digest

JOBS = DATA / "jobs"
JOBS.mkdir(parents=True, exist_ok=True)

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def enqueue(kind: str, payload: Dict[str, Any]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    jpath = JOBS / f"J-{kind}-{ts}.json"
    job = {"job_id": jpath.stem, "kind": kind, "status": "queued", "created_utc": _now(),
           "attempts": 0, "last_error": "", "payload": payload, "history": []}
    jpath.write_text(json.dumps(job, indent=2))
    try:
        from services.memory.telemetry import emit_telemetry

        pending = len(list(JOBS.glob("J-*.json")))
        if pending > 50:
            emit_telemetry("job_queue", "queue_congestion", severity="warning", metadata={"pending": pending})
    except Exception:
        pass
    return jpath

def _mark(job: Dict[str, Any], status: str, note: str = ""):
    job["status"] = status; job["history"].append({"ts": _now(), "status": status, "note": note})

def step_create_project(p):
    meta = new_project(p["order_id"], p["email"], p.get("name",""), p.get("skus",[]))
    evt_id = f"EVT-{meta['project_id']}-ORDER"
    record_event({"event_id": evt_id,"event_type":"ATTEST","why":"Order paid; project created",
                  "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                  "where":{"address":"System"},"what":[{"id": meta["project_id"], "qty":1}]})
    try:
        from services.memory.organism_integration import safe_write_after_job_kickoff

        safe_write_after_job_kickoff(
            meta["project_id"],
            p["order_id"],
            p["email"],
            p.get("name", ""),
            p.get("skus", []),
            evt_id,
        )
    except Exception:
        pass
    return meta["project_id"]

def step_send_intake(p, project_id):
    token = make_intake_token(project_id, p["email"])
    intake_url = f"{SETTINGS.public_base_url}/ui/intake?token={token}"
    html = f"<h2>Welcome</h2><p>Project <b>{project_id}</b> ready.</p><p>Intake: <a href='{intake_url}'>{intake_url}</a></p>"
    if SETTINGS.smtp_host and SETTINGS.smtp_user and SETTINGS.smtp_pass:
        send_email(p["email"], "Welcome  Your Compliance Project", html)
    record_event({"event_id": f"EVT-{project_id}-INTAKE-REQ","event_type":"ATTEST","why":"Intake link sent",
                  "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                  "where":{"address":"System"},"what":[{"id": project_id,"qty":1}]})
    return intake_url

def step_create_placeholders(project_id):
    pdir = DATA / "projects" / project_id / "evidence"; pdir.mkdir(parents=True, exist_ok=True)
    mf = pdir / "00_manifest.txt"; mf.write_text("Evidence placeholders reserved.")
    register_artifact(project_id, mf, "text/plain", "System", related_event=f"EVT-{project_id}-ORDER")

def step_set_sla(project_id):
    mins = int(getattr(SETTINGS, "auto_sla_escalation_minutes", 1440))
    due = (datetime.now(timezone.utc) + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = DATA / "projects" / project_id / "communications" / "sla_intake_due.json"; s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text(json.dumps({"project_id": project_id, "sla":"intake_received", "due_utc": due, "escalated": False}, indent=2))

def run_post_payment_playbook(p: Dict[str, Any]):
    try:
        pid = step_create_project(p)
        intake = step_send_intake(p, pid)
        step_create_placeholders(pid)
        step_set_sla(pid)
        return {"ok": True, "project_id": pid, "intake_url": intake}
    except Exception as e:
        return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

def _process_one(jpath: Path):
    job = json.loads(jpath.read_text())
    if job["status"] not in ("queued","retry"): return
    job["attempts"] += 1; _mark(job,"running","start"); jpath.write_text(json.dumps(job, indent=2))
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "job_queue",
            "job_started",
            metadata={"job_id": job.get("job_id"), "kind": job.get("kind"), "attempt": job["attempts"]},
        )
    except Exception:
        pass
    try:
        if job["kind"] == "post_payment":
            res = run_post_payment_playbook(job["payload"])
            if not res.get("ok"): raise RuntimeError(res.get("error","unknown"))
            job["result"] = res; _mark(job,"done","ok")
            try:
                from services.memory.telemetry import emit_telemetry

                emit_telemetry(
                    "job_queue",
                    "job_completed",
                    project_id=res.get("project_id", ""),
                    metadata={"job_id": job.get("job_id"), "kind": job.get("kind")},
                )
            except Exception:
                pass
        else:
            _mark(job,"failed",f"unknown kind {job['kind']}")
            try:
                from services.memory.telemetry import emit_telemetry

                emit_telemetry(
                    "job_queue",
                    "job_failed",
                    severity="error",
                    success=False,
                    message=f"unknown kind {job['kind']}",
                )
            except Exception:
                pass
    except Exception as e:
        job["last_error"] = f"{e}"; _mark(job,"retry","will retry")
        try:
            from services.memory.telemetry import emit_telemetry

            ev = "retry_exhausted" if job["attempts"] >= 5 else "retry_scheduled"
            emit_telemetry(
                "job_queue",
                ev,
                severity="error" if ev == "retry_exhausted" else "warning",
                success=False,
                error_code=type(e).__name__,
                message=str(e)[:200],
                metadata={"job_id": job.get("job_id"), "attempts": job["attempts"]},
            )
            if ev != "retry_exhausted":
                emit_telemetry("job_queue", "job_failed", severity="error", success=False, message=str(e)[:120])
        except Exception:
            pass
    finally:
        jpath.write_text(json.dumps(job, indent=2))

def sweep_queue():
    """Process every queued job through _process_one (retry + telemetry + memory)."""
    JOBS.mkdir(parents=True, exist_ok=True)
    for j in sorted(JOBS.glob("J-*.json")):
        try:
            _process_one(j)
        except Exception:
            pass


def _scheduled_forensic_reconcile():
    """Hourly fleet reconcile + integrity-proof refresh.

    Hardens the on-demand-only reconcile flagged in the 2026-06-04
    forensic audit: silent disk replacement and unsigned audit-receipt
    tampering were only detectable when someone manually triggered.
    Emits a `system` telemetry row so the organism's awareness sees
    the run, and a CRITICAL row if reconcile fails.
    """
    try:
        from services.intake.forensic_reconcile import (
            build_integrity_proof,
            run_forensic_reconciliation,
        )
    except Exception as exc:
        _emit_scheduler_event(
            "scheduler_forensic_reconcile_import_failed",
            success=False,
            severity="warning",
            message=f"{type(exc).__name__}: {exc}",
        )
        return

    try:
        report = run_forensic_reconciliation()
        proof  = build_integrity_proof(use_cache=False)
    except Exception as exc:
        _emit_scheduler_event(
            "scheduler_forensic_reconcile_failed",
            success=False,
            severity="critical",
            message=f"{type(exc).__name__}: {exc}",
        )
        return

    # Opportunistic entity-graph compaction. Cheap; dedupes the
    # append-only entities.jsonl that the forensic audit flagged as
    # bloated. Never raises.
    compact_report: Dict[str, Any] = {}
    try:
        from services.memory.entity_graph import compact_entities
        compact_report = compact_entities() or {}
    except Exception as exc:
        compact_report = {"ok": False, "error": str(exc)}

    _emit_scheduler_event(
        "scheduler_forensic_reconcile_ran",
        success=True,
        severity="info" if proof.get("ok") else "warning",
        message=("clean" if proof.get("ok") else "integrity issues detected"),
        metadata={
            "proof_ok":                proof.get("ok"),
            "signature_failure_count": proof.get("signature_failure_count", 0),
            "missing_audit_files":     proof.get("missing_audit_files", 0),
            "unindexed_files":         proof.get("unindexed_files", 0),
            "ghost_intake_count":      proof.get("ghost_intake_count", 0),
            "reconcile_intakes":       report.get("intakes_checked")
                                       if isinstance(report, dict) else None,
            "entity_compact":          {
                k: compact_report.get(k)
                for k in ("ok", "rows_before", "rows_after",
                          "rows_removed", "entities_kept", "compacted")
            },
        },
    )

def check_slas():
    # minimal SLA escalator (email optional)
    for pdir in (DATA / "projects").glob("P-*"):
        s = pdir / "communications" / "sla_intake_due.json"
        if not s.exists(): continue
        data = json.loads(s.read_text())
        if not data.get("escalated") and data.get("due_utc","") < _now():
            data["escalated"] = True; s.write_text(json.dumps(data, indent=2))
            evt_id = f"EVT-{pdir.name}-SLA-ESC"
            record_event({"event_id": evt_id,"event_type":"EXCEPTION","why":"Intake SLA breach escalated",
                          "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                          "where":{"address":"System"},"what":[{"id": pdir.name,"qty":1}]})
            try:
                from services.memory.organism_integration import safe_write_after_sla_event

                safe_write_after_sla_event(pdir.name, evt_id, "Intake SLA breach escalated")
            except Exception:
                pass

scheduler = None


def _emit_scheduler_event(
    event_type: str,
    *,
    success: bool = True,
    severity: str = "info",
    message: str = "",
    metadata=None,
) -> None:
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "system",
            event_type,
            success=success,
            severity=severity,
            message=message[:200] if message else "",
            metadata=metadata or {},
        )
    except Exception:
        pass


def start_worker(*, heavy: bool = True) -> None:
    """Start the background scheduler, with per-organ kill switches.

    Gated by ``KYC_SAFE_MODE`` and ``KYC_SCHEDULERS_ENABLED``. Each organ
    can be disabled individually via ``KYC_DISABLE_<ORGAN>`` so a single
    sick subsystem cannot take the whole scheduler down. Every scheduler
    decision (start, organ register, organ skip, failure) emits both a
    boot-log entry and a ``system`` telemetry event so the organism's
    awareness layer reports the live heart rate, not env-var fiction.
    """
    global scheduler
    from services.runtime_boot import (
        is_safe_mode,
        log_boot,
        organ_scheduler_enabled,
        schedulers_enabled,
    )

    if is_safe_mode() or not schedulers_enabled():
        log_boot(
            "scheduler",
            "hard_disabled",
            f"safe_mode={is_safe_mode()} schedulers_enabled={schedulers_enabled()}",
        )
        _emit_scheduler_event(
            "scheduler_disabled",
            metadata={
                "safe_mode": is_safe_mode(),
                "schedulers_enabled": schedulers_enabled(),
            },
        )
        return
    if scheduler is not None:
        log_boot("scheduler", "already_running", f"jobs={len(scheduler.get_jobs())}")
        return

    try:
        scheduler = BackgroundScheduler(timezone="UTC")
    except Exception as exc:
        log_boot("scheduler", "create_failed", f"{type(exc).__name__}: {exc}")
        _emit_scheduler_event(
            "scheduler_create_failed",
            success=False,
            severity="error",
            message=f"{type(exc).__name__}: {exc}",
        )
        scheduler = None
        return

    def _add_job(organ: str, fn, **kw) -> bool:
        if not organ_scheduler_enabled(organ):
            log_boot("scheduler", "organ_disabled", organ)
            _emit_scheduler_event(
                "scheduler_organ_disabled", metadata={"organ": organ}
            )
            return False
        try:
            scheduler.add_job(fn, id=organ, replace_existing=True, **kw)
            log_boot("scheduler", "organ_added", organ)
            _emit_scheduler_event(
                "scheduler_organ_registered", metadata={"organ": organ}
            )
            return True
        except Exception as exc:
            log_boot(
                "scheduler",
                "organ_add_failed",
                f"{organ}: {type(exc).__name__}: {exc}",
            )
            _emit_scheduler_event(
                "scheduler_organ_failed",
                success=False,
                severity="warning",
                message=f"{type(exc).__name__}: {exc}",
                metadata={"organ": organ},
            )
            return False

    _add_job("queue", sweep_queue, trigger="interval", seconds=10)
    _add_job("sla", check_slas, trigger="interval", minutes=5)

    # Forensic-audit fix (2026-06-04, intake FB-1dfab13c120b): emit a
    # cheap periodic pulse so the awareness layer always has a recent
    # `scheduler_*` row to read. Without this the heartbeat depended on
    # the one-time `scheduler_started` row staying inside the telemetry
    # lookback window — which it doesn't survive busy production traffic.
    def _scheduler_heartbeat_pulse() -> None:
        _emit_scheduler_event(
            "scheduler_heartbeat_pulse",
            metadata={"job_count": len(scheduler.get_jobs()) if scheduler else 0},
        )

    _add_job(
        "heartbeat_pulse",
        _scheduler_heartbeat_pulse,
        trigger="interval",
        minutes=5,
    )
    if heavy:
        _add_job(
            "nightly_exports",
            nightly_exports,
            trigger="cron",
            hour=2,
            minute=0,
        )
        _add_job(
            "weekly_digest",
            weekly_digest,
            trigger="cron",
            day_of_week="fri",
            hour=9,
            minute=0,
        )
        # Forensic-audit fix (2026-06-04): reconcile was only running
        # at startup/on-demand. Silent disk replacement or manual file
        # edits stayed invisible until somebody hit the endpoint. Now
        # the engine runs a fleet reconcile every hour and refreshes
        # the cached integrity proof — operators see the live
        # heartbeat, not a stale receipt.
        _add_job(
            "forensic_reconcile",
            _scheduled_forensic_reconcile,
            trigger="interval",
            minutes=60,
        )

    if heavy:
        for organ_label, module_path in (
            ("compliance_intel", "services.compliance_intelligence.scheduler"),
            ("acquisition", "services.acquisition.scheduler"),
            ("alerts", "services.alerts.scheduler"),
        ):
            if not organ_scheduler_enabled(organ_label):
                log_boot("scheduler", "organ_disabled", organ_label)
                _emit_scheduler_event(
                    "scheduler_organ_disabled", metadata={"organ": organ_label}
                )
                continue
            try:
                from importlib import import_module

                module = import_module(module_path)
                module.register_scheduler_jobs(scheduler)
                log_boot("scheduler", "organ_module_registered", organ_label)
                _emit_scheduler_event(
                    "scheduler_organ_module_registered",
                    metadata={"organ": organ_label, "module": module_path},
                )
            except Exception as exc:
                log_boot(
                    "scheduler",
                    "organ_module_failed",
                    f"{organ_label}: {type(exc).__name__}: {exc}",
                )
                _emit_scheduler_event(
                    "scheduler_organ_module_failed",
                    success=False,
                    severity="warning",
                    message=f"{type(exc).__name__}: {exc}",
                    metadata={"organ": organ_label, "module": module_path},
                )

    try:
        scheduler.start()
        log_boot(
            "scheduler",
            "started",
            f"active jobs={len(scheduler.get_jobs())}",
        )
        _emit_scheduler_event(
            "scheduler_started",
            metadata={
                "job_count": len(scheduler.get_jobs()),
                "job_ids": [j.id for j in scheduler.get_jobs()],
            },
        )
    except Exception as exc:
        log_boot("scheduler", "start_failed", f"{type(exc).__name__}: {exc}")
        _emit_scheduler_event(
            "scheduler_start_failed",
            success=False,
            severity="error",
            message=f"{type(exc).__name__}: {exc}",
        )
        scheduler = None

def nightly_exports():
    """Export binders for projects touched in last 24h."""
    if not getattr(SETTINGS, "auto_night_export", True):
        return
    try:
        pids = list_projects()
        for pid in pids:
            if project_changed_within(pid, 24):
                export_binder(pid)
    except Exception:
        # keep going; no crash
        pass

def weekly_digest():
    """Build & send a simple weekly digest."""
    if not getattr(SETTINGS, "weekly_digest", True):
        return
    try:
        from .process import compute_status
        rows = []
        for pid in list_projects():
            st = compute_status(pid)
            rows.append({
                "pid": pid,
                "phase": st["phase"],
                "rag": st["rag"],
                "req_open": st["counts"]["required_open"],
                "overdue": st["counts"]["overdue"]
            })
        send_digest(rows)
    except Exception:
        pass

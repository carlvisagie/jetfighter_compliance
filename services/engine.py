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
    return jpath

def _mark(job: Dict[str, Any], status: str, note: str = ""):
    job["status"] = status; job["history"].append({"ts": _now(), "status": status, "note": note})

def step_create_project(p):
    meta = new_project(p["order_id"], p["email"], p.get("name",""), p.get("skus",[]))
    record_event({"event_id": f"EVT-{meta['project_id']}-ORDER","event_type":"ATTEST","why":"Order paid; project created",
                  "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                  "where":{"address":"System"},"what":[{"id": meta["project_id"], "qty":1}]})
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
        if job["kind"] == "post_payment":
            res = run_post_payment_playbook(job["payload"])
            if not res.get("ok"): raise RuntimeError(res.get("error","unknown"))
            job["result"] = res; _mark(job,"done","ok")
        else:
            _mark(job,"failed",f"unknown kind {job['kind']}")
    except Exception as e:
        job["last_error"] = f"{e}"; _mark(job,"retry","will retry")
    finally:
        jpath.write_text(json.dumps(job, indent=2))

def sweep_queue():
    for j in sorted((DATA / "jobs").glob("J-*.json")): 
        try: _process_one(j)
        except Exception: pass

def check_slas():
    # minimal SLA escalator (email optional)
    for pdir in (DATA / "projects").glob("P-*"):
        s = pdir / "communications" / "sla_intake_due.json"
        if not s.exists(): continue
        data = json.loads(s.read_text())
        if not data.get("escalated") and data.get("due_utc","") < _now():
            data["escalated"] = True; s.write_text(json.dumps(data, indent=2))
            record_event({"event_id": f"EVT-{pdir.name}-SLA-ESC","event_type":"EXCEPTION","why":"Intake SLA breach escalated",
                          "when_utc": _now(),"who":{"name":"System","role":"Automation","email":"noreply@keepyourcontracts.com"},
                          "where":{"address":"System"},"what":[{"id": pdir.name,"qty":1}]})

scheduler = None
def start_worker():
    global scheduler
    if scheduler: return
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(sweep_queue, "interval", seconds=10, id="queue")
    scheduler.add_job(check_slas, "interval", minutes=5, id="sla")
        # --- Auto-jobs (idempotent) ---
    try:
        scheduler.add_job(nightly_exports, 'cron', hour=2, minute=0, id='nightly_exports')
    except Exception:
        pass
    try:
        scheduler.add_job(weekly_digest, 'cron', day_of_week='fri', hour=9, minute=0, id='weekly_digest')
    except Exception:
        passscheduler.start()

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


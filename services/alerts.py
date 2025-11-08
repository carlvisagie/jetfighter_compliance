from datetime import datetime, timezone
from typing import List
from .config import SETTINGS, DATA
from .emails import send_email
from .process import compute_status
from pathlib import Path

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def send_step_reminder(project_id: str, to_email: str, missing_titles: List[str]):
    if not (SETTINGS.smtp_host and SETTINGS.smtp_user and SETTINGS.smtp_pass): return
    body = f"<p>Project <b>{project_id}</b> has steps due:</p><ul>" + "".join(f"<li>{t}</li>" for t in missing_titles) + "</ul>"
    send_email(to_email, f"[Reminder] Steps due for {project_id}", body)

def send_daily_digest(owner_email: str):
    if not (SETTINGS.smtp_host and SETTINGS.smtp_user and SETTINGS.smtp_pass): return
    projects = [p.name for p in (DATA / "projects").glob("P-*")]
    rows = []
    for pid in projects:
        st = compute_status(pid)
        rows.append(f"<tr><td>{pid}</td><td>{st['phase']}</td><td>{st['rag']}</td><td>{st['counts']['required_open']}</td><td>{st['counts']['overdue']}</td></tr>")
    html = "<h2>Daily Compliance Digest</h2><table border='1'><tr><th>Project</th><th>Phase</th><th>RAG</th><th>Req Open</th><th>Overdue</th></tr>" + "".join(rows) + "</table>"
    send_email(owner_email, "Daily Compliance Digest", html)

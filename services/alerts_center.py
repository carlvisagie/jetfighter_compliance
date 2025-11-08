import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from .config import DATA, SETTINGS
from .emails import send_email

ALERTS = DATA / "alerts"
ALERTS.mkdir(parents=True, exist_ok=True)
LOG = ALERTS / "alerts.jsonl"

def _ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def add_alert(kind: str, title: str, body: str = "", email_owner: bool = False) -> Dict:
    rec = {"ts": _ts(), "kind": kind, "title": title, "body": body, "read": False}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # optional owner email
    if email_owner and getattr(SETTINGS, "smtp_enabled", False) and getattr(SETTINGS, "digest_email_to", ""):
        try:
            send_email(SETTINGS.digest_email_to, f"[ALERT] {title}", f"<p>{body}</p>")
        except Exception:
            pass
    return rec

def list_unread(limit: int = 20) -> List[Dict]:
    if not LOG.exists(): return []
    out = []
    with open(LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
                if not j.get("read"):
                    out.append(j)
            except Exception:
                continue
    return out[-limit:]

def mark_all_read():
    if not LOG.exists(): return
    lines = []
    with open(LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line); j["read"] = True
                lines.append(json.dumps(j, ensure_ascii=False))
            except Exception:
                lines.append(line.strip())
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

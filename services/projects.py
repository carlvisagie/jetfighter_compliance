import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from .config import PROJECTS
from .checklist import build_checklist

def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')

def new_project(order_id: str, customer_email: str, customer_name: str, skus: List[str]) -> Dict:
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    project_id = f"P-{order_id}-{ts}"
    pdir = PROJECTS / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "project_id": project_id,
        "order_id": order_id,
        "customer": {"email": customer_email, "name": customer_name},
        "skus": skus,
        "created_at": ts,
        "status": "initiated"
    }
    (pdir/"meta.json").write_text(json.dumps(meta, indent=2))
    checklist = build_checklist(skus)
    (pdir/"checklist.json").write_text(json.dumps(checklist, indent=2))
    (pdir/"evidence/").mkdir(parents=True, exist_ok=True)
    (pdir/"communications/").mkdir(parents=True, exist_ok=True)
    return meta

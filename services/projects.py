import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from .config import PROJECTS
from .checklist import build_checklist
from .defensive_wiring import safe_write_json

def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')

def new_project(order_id: str, customer_email: str, customer_name: str, skus: List[str]) -> Dict:
    """Create new project with defensive framework."""
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    project_id = f"P-{order_id}-{ts}"
    pdir = PROJECTS / project_id
    
    # Create project directory structure
    pdir.mkdir(parents=True, exist_ok=True)
    
    meta = {
        "project_id": project_id,
        "order_id": order_id,
        "customer": {"email": customer_email, "name": customer_name},
        "skus": skus,
        "created_at": ts,
        "status": "initiated"
    }
    
    # Write meta.json with defensive framework
    safe_write_json(pdir / "meta.json", meta, component="projects", context=f"project {project_id} meta", severity="critical")
    
    # Build and write checklist with defensive framework
    checklist = build_checklist(skus)
    safe_write_json(pdir / "checklist.json", checklist, component="projects", context=f"project {project_id} checklist", severity="critical")
    
    # Create subdirectories
    (pdir/"evidence/").mkdir(parents=True, exist_ok=True)
    (pdir/"communications/").mkdir(parents=True, exist_ok=True)
    
    # SUCCESS: Emit telemetry
    try:
        from services.memory.telemetry import emit_telemetry
        emit_telemetry("projects", "project_created", metadata={"project_id": project_id, "order_id": order_id, "email": customer_email, "skus": skus})
    except Exception:
        pass
    
    return meta

import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from .config import PROJECTS
from .checklist import build_checklist

def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')

def new_project(order_id: str, customer_email: str, customer_name: str, skus: List[str]) -> Dict:
    """Create new project with defensive error telemetry."""
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    project_id = f"P-{order_id}-{ts}"
    pdir = PROJECTS / project_id
    
    try:
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
        
        # Write meta.json
        (pdir/"meta.json").write_text(json.dumps(meta, indent=2))
        
        # Build and write checklist
        checklist = build_checklist(skus)
        (pdir/"checklist.json").write_text(json.dumps(checklist, indent=2))
        
        # Create subdirectories
        (pdir/"evidence/").mkdir(parents=True, exist_ok=True)
        (pdir/"communications/").mkdir(parents=True, exist_ok=True)
        
        # SUCCESS: Emit telemetry
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "projects",
                "project_created",
                metadata={
                    "project_id": project_id,
                    "order_id": order_id,
                    "email": customer_email,
                    "skus": skus
                }
            )
        except Exception:
            pass  # Don't fail project creation if telemetry fails
        
        return meta
        
    except OSError as e:
        # FAILURE: Disk full, permissions, I/O error
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "projects",
                "project_creation_failed",
                severity="critical",
                metadata={
                    "project_id": project_id,
                    "order_id": order_id,
                    "email": customer_email,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise
    except Exception as e:
        # FAILURE: Unexpected error
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "projects",
                "project_creation_failed",
                severity="critical",
                metadata={
                    "project_id": project_id,
                    "order_id": order_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise

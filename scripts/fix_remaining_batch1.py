"""Fix all remaining 12 files to use defensive framework."""
import re
from pathlib import Path

def fix_customer_session():
    """Fix services/customer_session.py"""
    file_path = Path("services/customer_session.py")
    content = file_path.read_text(encoding="utf-8")
    
    # Add import
    if "from .defensive_wiring import" not in content:
        content = content.replace(
            "from fastapi import HTTPException",
            "from fastapi import HTTPException\nfrom .defensive_wiring import safe_write_json"
        )
    
    # Replace _save_session
    content = re.sub(
        r'def _save_session\(session_id: str, data: Dict\[str, Any\]\) -> None:.*?raise',
        '''def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    """Save session with defensive framework."""
    path = _session_dir(session_id) / "session.json"
    safe_write_json(
        path,
        data,
        component="customer_session",
        context=f"session {session_id}",
        severity="critical"
    )''',
        content,
        flags=re.DOTALL
    )
    
    # Replace _save_manifest
    content = re.sub(
        r'def _save_manifest\(\) -> None:.*?pass\s+raise',
        '''def _save_manifest() -> None:
    """Save global manifest with defensive framework."""
    safe_write_json(
        MANIFEST_FILE,
        _load_manifest(),
        component="customer_session",
        context="global manifest",
        severity="critical"
    )''',
        content,
        flags=re.DOTALL
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Fixed {file_path}")

def fix_intake_kickoff():
    """Fix services/intake/kickoff.py"""
    file_path = Path("services/intake/kickoff.py")
    content = file_path.read_text(encoding="utf-8")
    
    # Add import
    if "from ..defensive_wiring import" not in content:
        content = content.replace(
            "from typing import",
            "from ..defensive_wiring import safe_write_json\nfrom typing import"
        )
    
    # Replace intake.json write
    content = re.sub(
        r'# Write intake\.json with defensive error telemetry\s+try:.*?pass\s+raise',
        '''# Write intake.json with defensive framework
    safe_write_json(
        comm / "intake.json",
        intake_meta,
        component="intake_kickoff",
        context=f"intake {intake_id}",
        severity="critical"
    )''',
        content,
        flags=re.DOTALL
    )
    
    # Replace meta.json write
    content = re.sub(
        r'try:\s+pm = json\.loads\(meta_path\.read_text.*?pass\s+raise',
        '''try:
            pm = json.loads(meta_path.read_text(encoding="utf-8"))
            pm["canonical_intake_id"] = intake_id
            safe_write_json(
                meta_path,
                pm,
                component="intake_kickoff",
                context=f"project {project_id} meta update",
                severity="warning"
            )''',
        content,
        flags=re.DOTALL
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Fixed {file_path}")

def fix_engine():
    """Fix services/engine.py"""
    file_path = Path("services/engine.py")
    content = file_path.read_text(encoding="utf-8")
    
    # Add import
    if "from .defensive_wiring import" not in content:
        content = content.replace(
            "from .config import",
            "from .defensive_wiring import safe_write_json\nfrom .config import"
        )
    
    # Replace enqueue write
    content = re.sub(
        r'job = \{"job_id":.*?\}\s+jpath\.write_text\(json\.dumps\(job, indent=2\)\)',
        '''job = {"job_id": jpath.stem, "kind": kind, "status": "queued", "created_utc": _now(),
           "attempts": 0, "last_error": "", "payload": payload, "history": []}
    safe_write_json(jpath, job, component="job_queue", context=f"enqueue {kind}", severity="critical")''',
        content
    )
    
    # Replace _process_one write
    content = re.sub(
        r'finally:\s+jpath\.write_text\(json\.dumps\(job, indent=2\)\)',
        '''finally:
        safe_write_json(jpath, job, component="job_queue", context=f"job {job.get('job_id', 'unknown')}", severity="critical")''',
        content
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Fixed {file_path}")

def fix_process():
    """Fix services/process.py"""
    file_path = Path("services/process.py")
    content = file_path.read_text(encoding="utf-8")
    
    # Add import
    if "from .defensive_wiring import" not in content:
        content = content.replace(
            "from typing import",
            "from .defensive_wiring import safe_write_json\nfrom typing import"
        )
    
    # Replace _save
    content = re.sub(
        r'def _save\(project_id: str, obj: Dict\):\s+_wf_path\(project_id\)\.write_text\(json\.dumps\(obj, indent=2\)\)',
        '''def _save(project_id: str, obj: Dict):
    safe_write_json(
        _wf_path(project_id),
        obj,
        component="workflow",
        context=f"workflow {project_id}",
        severity="critical"
    )''',
        content
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Fixed {file_path}")

def fix_rfq():
    """Fix services/rfq.py"""
    file_path = Path("services/rfq.py")
    content = file_path.read_text(encoding="utf-8")
    
    # Add import
    if "from .defensive_wiring import" not in content:
        content = content.replace(
            "from dataclasses import",
            "from .defensive_wiring import safe_write_json\nfrom dataclasses import"
        )
    
    # Replace save_rfq write
    content = re.sub(
        r'def save_rfq\(obj: RFQ\):.*?_rfq_path\(obj\.rfq_id\)\.write_text\(json\.dumps\(d, indent=2\)\)',
        '''def save_rfq(obj: RFQ):
    d = asdict(obj)
    d["bids"] = [asdict(b) for b in (obj.bids or [])]
    safe_write_json(
        _rfq_path(obj.rfq_id),
        d,
        component="rfq",
        context=f"rfq {obj.rfq_id}",
        severity="critical"
    )''',
        content,
        flags=re.DOTALL
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Fixed {file_path}")

def fix_acquisition_memory():
    """Fix services/acquisition/memory.py"""
    file_path = Path("services/acquisition/memory.py")
    content = file_path.read_text(encoding="utf-8")
    
    # Add import
    if "from ..defensive_wiring import" not in content:
        content = content.replace(
            "from pathlib import Path",
            "from pathlib import Path\nfrom ..defensive_wiring import safe_write_json"
        )
    
    # Replace weights.json write
    content = re.sub(
        r'\(root / WEIGHTS_JSON\)\.write_text\(json\.dumps\(weights, indent=2\), encoding="utf-8"\)',
        '''safe_write_json(
                root / WEIGHTS_JSON,
                weights,
                component="acquisition",
                context="weights mirror",
                severity="warning"
            )''',
        content
    )
    
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Fixed {file_path}")

# Run all fixes
print("=== FIXING REMAINING 12 FILES ===\n")
fix_customer_session()
fix_intake_kickoff()
fix_engine()
fix_process()
fix_rfq()
fix_acquisition_memory()

print("\n=== BATCH 1 COMPLETE (6 files) ===")

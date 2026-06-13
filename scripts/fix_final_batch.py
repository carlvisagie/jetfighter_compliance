"""Fix final 4 complex files: engine, customer_session, intake/kickoff, cognition/storage."""
from pathlib import Path

# 11/14: services/engine.py - 6 writes total
print("Fixing 11/14: engine.py (6 writes)...")
file = Path("services/engine.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from .config import JOBS",
    "from .config import JOBS\nfrom .defensive_wiring import safe_write_json"
)
# Fix enqueue write
old1 = '''job = {"job_id": jpath.stem, "kind": kind, "status": "queued", "created_utc": _now(),
           "attempts": 0, "last_error": "", "payload": payload, "history": []}
    jpath.write_text(json.dumps(job, indent=2))'''
new1 = '''job = {"job_id": jpath.stem, "kind": kind, "status": "queued", "created_utc": _now(),
           "attempts": 0, "last_error": "", "payload": payload, "history": []}
    safe_write_json(jpath, job, component="job_queue", context=f"enqueue {kind}", severity="critical")'''
content = content.replace(old1, new1)
# Fix _process_one final write
old2 = '''finally:
        jpath.write_text(json.dumps(job, indent=2))'''
new2 = '''finally:
        safe_write_json(jpath, job, component="job_queue", context=f"job {job.get('job_id', 'unknown')}", severity="critical")'''
content = content.replace(old2, new2)
file.write_text(content, encoding="utf-8")
print("OK 11/14: engine.py")

# 12/14: services/customer_session.py - 2 writes
print("Fixing 12/14: customer_session.py (2 writes)...")
file = Path("services/customer_session.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from fastapi import HTTPException",
    "from fastapi import HTTPException\nfrom .defensive_wiring import safe_write_json"
)
# Fix _save_session
old3 = '''def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    """Save session with defensive error telemetry."""
    path = _session_dir(session_id) / "session.json"
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        # CRITICAL: Session write failed
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "customer_session",
                "session_write_failed",
                severity="critical",
                metadata={
                    "session_id": session_id,
                    "path": str(path),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise'''
new3 = '''def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    """Save session with defensive framework."""
    path = _session_dir(session_id) / "session.json"
    safe_write_json(path, data, component="customer_session", context=f"session {session_id}", severity="critical")'''
content = content.replace(old3, new3)
# Fix _save_manifest
old4 = '''def _save_manifest() -> None:
    try:
        MANIFEST_FILE.write_text(json.dumps(_load_manifest(), indent=2), encoding="utf-8")
    except OSError as e:
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "customer_session",
                "manifest_write_failed",
                severity="critical",
                metadata={"path": str(MANIFEST_FILE), "error": str(e)}
            )
        except Exception:
            pass
        raise'''
new4 = '''def _save_manifest() -> None:
    safe_write_json(MANIFEST_FILE, _load_manifest(), component="customer_session", context="global manifest", severity="critical")'''
content = content.replace(old4, new4)
file.write_text(content, encoding="utf-8")
print("OK 12/14: customer_session.py")

# 13/14: services/intake/kickoff.py - 2 writes
print("Fixing 13/14: intake/kickoff.py (2 writes)...")
file = Path("services/intake/kickoff.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from typing import Dict, List, Optional",
    "from typing import Dict, List, Optional\nfrom ..defensive_wiring import safe_write_json"
)
# Fix intake.json write
old5 = '''# Write intake.json with defensive error telemetry
    try:
        (comm / "intake.json").write_text(json.dumps(intake_meta, indent=2), encoding="utf-8")
    except OSError as e:
        # CRITICAL: Kickoff intake.json write failed
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                "intake_kickoff",
                "intake_json_write_failed",
                severity="critical",
                metadata={
                    "intake_id": intake_id,
                    "project_id": project_id,
                    "path": str(comm / "intake.json"),
                    "error": str(e)
                }
            )
        except Exception:
            pass
        raise'''
new5 = '''# Write intake.json with defensive framework
    safe_write_json(comm / "intake.json", intake_meta, component="intake_kickoff", context=f"intake {intake_id}", severity="critical")'''
content = content.replace(old5, new5)
# Fix meta.json write
old6 = '''try:
            pm = json.loads(meta_path.read_text(encoding="utf-8"))
            pm["canonical_intake_id"] = intake_id
            meta_path.write_text(json.dumps(pm, indent=2), encoding="utf-8")
        except OSError as e:
            # WARNING: meta.json update failed (non-critical)
            try:
                from services.memory.telemetry import emit_telemetry
                emit_telemetry(
                    "intake_kickoff",
                    "meta_update_failed",
                    severity="warning",
                    metadata={
                        "intake_id": intake_id,
                        "project_id": project_id,
                        "path": str(meta_path),
                        "error": str(e)
                    }
                )
            except Exception:
                pass
            raise'''
new6 = '''try:
            pm = json.loads(meta_path.read_text(encoding="utf-8"))
            pm["canonical_intake_id"] = intake_id
            safe_write_json(meta_path, pm, component="intake_kickoff", context=f"project {project_id} meta update", severity="warning")'''
content = content.replace(old6, new6)
file.write_text(content, encoding="utf-8")
print("OK 13/14: intake/kickoff.py")

print("\n=== BATCH 2 COMPLETE: 11-13/14 (3 files, 10 writes) ===")
print("Remaining: cognition/storage.py (9 writes) - fixed separately")

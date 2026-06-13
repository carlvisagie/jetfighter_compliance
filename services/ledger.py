import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from .config import DATA

LEDGER_DIR = DATA / "ledger"
LEDGER_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_FILE = LEDGER_DIR / "ledger.log"

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def file_sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return _sha256_bytes(f.read())

def last_hash() -> str:
    if not LEDGER_FILE.exists(): return "GENESIS"
    *_, last = LEDGER_FILE.read_text(encoding="utf-8").splitlines() or ["GENESIS"]
    try:
        return json.loads(last)["hash"]
    except Exception:
        return "GENESIS"

def append_ledger(record: dict) -> dict:
    record = dict(record)
    record["ts_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["prev_hash"] = record.get("prev_hash") or last_hash()
    payload = json.dumps({k:v for k,v in record.items() if k != "hash"}, sort_keys=True).encode()
    record["hash"] = _sha256_bytes(payload)
    try:
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            import os
            os.fsync(f.fileno())
    except OSError as e:
        import logging
        logging.error(f"Failed to append to ledger durably: {e}")
        raise
    
    # Emit telemetry so organism knows ledger event recorded
    try:
        from services.memory.telemetry import emit_telemetry
        emit_telemetry(
            "coc_ledger",
            "ledger_appended",
            metadata={
                "kind": record.get("kind", ""),
                "hash": record["hash"][:8],
                "project_id": record.get("project_id", "")
            }
        )
    except Exception:
        pass
    
    return record

def register_artifact(project_id: str, path: Path, media_type: str, owner: str, related_event: str = "") -> dict:
    sha = file_sha256(path)
    art = {
        "kind": "artifact",
        "project_id": project_id,
        "artifact_id": f"A-{project_id}-{sha[:8]}",
        "path": str(path),
        "sha256": sha,
        "media_type": media_type,
        "owner": owner,
        "related_event": related_event
    }
    ledger_record = append_ledger(art)
    
    # Write to central memory timeline so organism knows artifact registered
    try:
        from services.memory.timeline import append_timeline
        append_timeline(
            project_id=project_id,
            event_type="artifact_registered",
            detail=f"Artifact {art['artifact_id']} registered",
            metadata={
                "artifact_id": art["artifact_id"],
                "media_type": media_type,
                "sha256": sha[:16],
                "owner": owner
            }
        )
    except Exception:
        pass
    
    return ledger_record

def record_event(event: dict) -> dict:
    event = dict(event)
    event["kind"] = "event"
    ledger_record = append_ledger(event)
    
    # Write to central memory timeline so organism knows COC event recorded
    try:
        from services.memory.timeline import append_timeline
        project_id = event.get("project_id", "")
        if project_id:
            append_timeline(
                project_id=project_id,
                event_type="coc_event",
                detail=event.get("description", "COC event recorded"),
                metadata={"ledger_hash": ledger_record["hash"][:8]}
            )
    except Exception:
        pass
    
    return ledger_record

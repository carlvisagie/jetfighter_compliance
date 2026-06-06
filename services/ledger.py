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
    return append_ledger(art)

def record_event(event: dict) -> dict:
    event = dict(event)
    event["kind"] = "event"
    return append_ledger(event)

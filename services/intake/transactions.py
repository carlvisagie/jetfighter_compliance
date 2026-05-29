"""Durable transaction lifecycle log — ordered upload commit phases per intake."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .storage import ensure_canonical_intake_dir

PHASE_UPLOAD_RECEIVED = "upload_received"
PHASE_FILES_PERSISTED = "files_persisted"
PHASE_HASH_VERIFIED = "hash_verified"
PHASE_AUDIT_WRITTEN = "audit_written"
PHASE_INTAKE_COMMITTED = "intake_committed"
PHASE_INDEX_COMMITTED = "index_committed"
PHASE_INTEGRITY_FAILURE = "integrity_failure"
PHASE_CLASSIFICATION = "classification_complete"
PHASE_TELEMETRY_FAILED = "telemetry_failed"
PHASE_RECOVERED_ON_STARTUP = "recovered_on_startup"
PHASE_FORENSIC_RECOVERED = "forensic_recovered"
PHASE_COMMIT_INTERRUPTED = "commit_interrupted"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def transaction_log_path(intake_id: str) -> Path:
    return ensure_canonical_intake_dir(intake_id) / "transaction_lifecycle.jsonl"


def append_transaction_event(
    intake_id: str,
    phase: str,
    *,
    ok: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "at_utc": _utc_now(),
        "intake_id": intake_id,
        "phase": phase,
        "ok": ok,
        "metadata": metadata or {},
    }
    path = transaction_log_path(intake_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load_transaction_log(intake_id: str, *, tail: int = 200) -> list[Dict[str, Any]]:
    path = transaction_log_path(intake_id)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[Dict[str, Any]] = []
    for line in lines[-tail:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def last_transaction_phase(intake_id: str) -> Optional[str]:
    rows = load_transaction_log(intake_id, tail=50)
    if not rows:
        return None
    return str(rows[-1].get("phase") or "")


def intake_commit_complete(intake_id: str) -> bool:
    """True only when index_committed succeeded after audit."""
    phases = {str(r.get("phase")) for r in load_transaction_log(intake_id, tail=80)}
    return PHASE_INDEX_COMMITTED in phases

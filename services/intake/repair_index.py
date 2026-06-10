"""Intake index repair — sync disk intakes to operational index."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def sync_intake_index_from_disk(*, write: bool = True, limit: int = 200) -> Dict[str, Any]:
    """
    Rebuild operational index from disk intakes — repair missing index entries.
    
    Scans all canonical intake roots for intake.json files and ensures they
    are visible in the operational index, regardless of transaction phase state.
    
    Rules:
    - If intake.json exists on disk → must be in operational index
    - Preserves custody status from intake.json
    - Preserves uploaded file records
    - Does not delete data
    - Writes PHASE_INDEX_COMMITTED if missing
    
    Returns:
    - repaired_intakes: list of intake IDs that were repaired
    - already_indexed: count of intakes already in index
    - missing_intake_json: count of directories without intake.json
    - errors: list of intake IDs that failed to repair
    """
    from .storage import (
        intakes_root,
        legacy_intakes_roots,
        index_intake_ids,
        load_intake_record,
        upsert_index_row,
    )
    from .transactions import (
        PHASE_INDEX_COMMITTED,
        PHASE_INTAKE_COMMITTED,
        append_transaction_event,
        intake_commit_complete,
    )
    
    repaired: List[str] = []
    already_indexed: List[str] = []
    missing_json: List[str] = []
    errors: List[Dict[str, Any]] = []
    
    # Get current index
    index_ids = set(index_intake_ids(tail_lines=limit * 2))
    
    # Scan all intake roots
    roots = [intakes_root(), *legacy_intakes_roots()]
    
    for root in roots:
        if not root.is_dir():
            continue
            
        for intake_dir in sorted(root.iterdir()):
            if not intake_dir.is_dir():
                continue
                
            if not intake_dir.name.startswith("FB-"):
                continue
                
            intake_id = intake_dir.name
            intake_json = intake_dir / "intake.json"
            
            # Skip if no intake.json
            if not intake_json.is_file():
                missing_json.append(intake_id)
                continue
            
            # Check if already indexed with proper commit
            if intake_id in index_ids and intake_commit_complete(intake_id):
                already_indexed.append(intake_id)
                continue
            
            # Repair: load record and ensure indexed
            try:
                record = load_intake_record(intake_id, persist_recovery=False)
                
                if write:
                    # Ensure transaction phases exist
                    if not intake_commit_complete(intake_id):
                        append_transaction_event(
                            intake_id,
                            PHASE_INTAKE_COMMITTED,
                            metadata={
                                "custody_status": record.get("custody_status"),
                                "file_count": record.get("file_count"),
                                "repair": True,
                            },
                        )
                        append_transaction_event(
                            intake_id,
                            PHASE_INDEX_COMMITTED,
                            metadata={"committed": True, "repair": True},
                        )
                    
                    # Upsert index row
                    upsert_index_row(
                        {
                            "intake_id": intake_id,
                            "created_at_utc": record.get("created_at_utc"),
                            "status": record.get("review_status") or record.get("status"),
                            "company": record.get("company"),
                            "email": record.get("email"),
                            "urgent": record.get("urgent"),
                            "file_count": record.get("file_count", 0),
                            "committed": True,
                            "repaired": True,
                            "custody_status": record.get("custody_status"),
                        }
                    )
                
                repaired.append(intake_id)
                logger.info(
                    "Repaired intake index: %s custody=%s files=%s",
                    intake_id,
                    record.get("custody_status"),
                    record.get("file_count"),
                )
                
            except Exception as exc:
                logger.error("Failed to repair intake %s: %s", intake_id, exc)
                errors.append({"intake_id": intake_id, "error": str(exc)})
    
    return {
        "ok": len(errors) == 0,
        "repaired_intakes": repaired,
        "repaired_count": len(repaired),
        "already_indexed_count": len(already_indexed),
        "missing_intake_json_count": len(missing_json),
        "missing_intake_json_sample": missing_json[:10],
        "errors": errors,
        "error_count": len(errors),
        "write_mode": write,
    }

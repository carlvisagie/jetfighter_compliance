"""Communications ledger reconciliation — hash verification and gap detection."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .hashing import verify_record_hash
from .ledger import ledger_path


def reconcile_communications_ledger(*, tail_lines: int = 100000) -> Dict[str, Any]:
    """
    Verify append-only ledger integrity.
    Detects hash mismatches, duplicate IDs with divergent payloads, and parse gaps.
    """
    path = ledger_path()
    incidents: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    parse_errors = 0
    line_count = 0

    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                incidents.append(
                    {
                        "issue_code": "communication_ledger_parse_error",
                        "detail": f"Unparseable ledger line {line_count}",
                        "severity": "high",
                    }
                )
                continue
            records.append(row)

    by_id: Dict[str, Dict[str, Any]] = {}
    hash_mismatch_count = 0
    missing_id_count = 0

    for row in records:
        cid = str(row.get("communication_id") or "")
        if not cid:
            missing_id_count += 1
            incidents.append(
                {
                    "issue_code": "communication_missing_id",
                    "detail": "Ledger row missing communication_id",
                    "severity": "high",
                }
            )
            continue

        if not verify_record_hash(row):
            hash_mismatch_count += 1
            incidents.append(
                {
                    "communication_id": cid,
                    "issue_code": "communication_hash_mismatch",
                    "detail": f"Record hash mismatch for {cid}",
                    "severity": "critical",
                }
            )

        prior = by_id.get(cid)
        if prior is not None and prior != row:
            incidents.append(
                {
                    "communication_id": cid,
                    "issue_code": "communication_duplicate_id",
                    "detail": f"Duplicate communication_id {cid} with divergent payload",
                    "severity": "high",
                }
            )
        by_id[cid] = row

    if line_count > 0 and len(records) == 0:
        incidents.append(
            {
                "issue_code": "communication_ledger_empty_parse",
                "detail": "Ledger file has lines but zero parseable records",
                "severity": "critical",
            }
        )

    ok = hash_mismatch_count == 0 and parse_errors == 0 and missing_id_count == 0
    duplicate_issues = sum(1 for i in incidents if i.get("issue_code") == "communication_duplicate_id")
    if duplicate_issues:
        ok = False

    return {
        "ok": ok,
        "ledger_path": str(path.resolve()) if isinstance(path, Path) else str(path),
        "line_count": line_count,
        "record_count": len(by_id),
        "hash_mismatch_count": hash_mismatch_count,
        "parse_error_count": parse_errors,
        "missing_id_count": missing_id_count,
        "incidents": incidents,
    }

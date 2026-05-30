"""Canonical hash for communication ledger records."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

_HASH_FIELD = "record_hash"
_EXCLUDE = frozenset({_HASH_FIELD, "recorded_at_utc", "recorded_by"})


def canonical_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = {k: v for k, v in record.items() if k not in _EXCLUDE}
    return payload


def compute_record_hash(record: Dict[str, Any]) -> str:
    payload = canonical_payload(record)
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def verify_record_hash(record: Dict[str, Any]) -> bool:
    stored = str(record.get(_HASH_FIELD) or "")
    if not stored:
        return False
    return stored == compute_record_hash(record)

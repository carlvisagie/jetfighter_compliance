"""Longitudinal acquisition and onboarding history (append-only JSONL)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .intelligence_paths import (
    FORENSIC_EVENTS_JSONL,
    LONGITUDINAL_JSONL,
    ORG_PROFILES_JSONL,
    ensure_intel_dirs,
)
from .models import utc_now


def org_key_from_email(email: str) -> str:
    e = (email or "").strip().lower()
    if "@" in e:
        return e.split("@", 1)[1]
    return e or "unknown"


def org_key_from_company(company: str) -> str:
    n = re.sub(r"[^a-z0-9]+", "-", (company or "").lower()).strip("-")
    return n or "unknown-company"


def resolve_org_key(email: str = "", company: str = "", project_id: str = "") -> str:
    if email:
        return org_key_from_email(email)
    if company:
        return org_key_from_company(company)
    return project_id or "unknown"


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    ensure_intel_dirs(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_forensic_event(
    event_type: str,
    project_id: str = "",
    org_key: str = "",
    payload: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    root = ensure_intel_dirs(base)
    rec = {
        "event_type": event_type,
        "project_id": project_id,
        "org_key": org_key,
        "when_utc": utc_now(),
        "payload": payload or {},
    }
    _append_jsonl(root / FORENSIC_EVENTS_JSONL, rec)
    _append_jsonl(
        root / LONGITUDINAL_JSONL,
        {"org_key": org_key, "project_id": project_id, "event_type": event_type, "when_utc": rec["when_utc"]},
    )
    return rec


def upsert_org_profile(org_key: str, patch: Dict[str, Any], base: Optional[Path] = None) -> Dict[str, Any]:
    """Merge patch into latest org profile snapshot."""
    root = ensure_intel_dirs(base)
    path = root / ORG_PROFILES_JSONL
    existing = {}
    rows = _load_jsonl(path)
    for row in reversed(rows):
        if row.get("org_key") == org_key:
            existing = row
            break
    merged = {**existing, **patch, "org_key": org_key, "updated_utc": utc_now()}
    if "first_seen_utc" not in merged:
        merged["first_seen_utc"] = merged["updated_utc"]
    _append_jsonl(path, merged)
    return merged


def get_org_history(org_key: str, base: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    return [r for r in _load_jsonl(root / LONGITUDINAL_JSONL) if r.get("org_key") == org_key]


def get_org_profile(org_key: str, base: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    rows = _load_jsonl(root / ORG_PROFILES_JSONL)
    for row in reversed(rows):
        if row.get("org_key") == org_key:
            return row
    return None


def list_forensic_events(project_id: str = "", base: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    events = _load_jsonl(root / FORENSIC_EVENTS_JSONL)
    if project_id:
        return [e for e in events if e.get("project_id") == project_id]
    return events

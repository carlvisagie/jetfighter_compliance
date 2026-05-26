"""Append-only project evidence intelligence artifacts (not canonical brain)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

def _data_root() -> Path:
    from ..config import DATA

    return DATA


def _intel_dir(project_id: str) -> Path:
    d = _data_root() / "projects" / project_id / "evidence_intelligence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_jsonl(project_id: str, name: str, record: Dict[str, Any]) -> None:
    path = _intel_dir(project_id) / name
    rec = dict(record)
    rec.setdefault("recorded_utc", _ts())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_jsonl(project_id: str, name: str, limit: int = 500) -> List[Dict[str, Any]]:
    path = _intel_dir(project_id) / name
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def write_profile(project_id: str, profile: Dict[str, Any]) -> None:
    path = _intel_dir(project_id) / "profile.json"
    profile["updated_utc"] = _ts()
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def load_profile(project_id: str) -> Dict[str, Any]:
    path = _intel_dir(project_id) / "profile.json"
    if not path.is_file():
        return {"project_id": project_id, "document_inventory": [], "evidence_coverage": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"project_id": project_id, "document_inventory": [], "evidence_coverage": {}}


def write_gaps(project_id: str, gaps: List[Dict[str, Any]]) -> None:
    path = _intel_dir(project_id) / "gaps.json"
    path.write_text(json.dumps({"updated_utc": _ts(), "gaps": gaps}, indent=2), encoding="utf-8")


def load_gaps(project_id: str) -> List[Dict[str, Any]]:
    path = _intel_dir(project_id) / "gaps.json"
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("gaps") or []
    except Exception:
        return []


def append_review_item(project_id: str, item: Dict[str, Any]) -> None:
    append_jsonl(project_id, "review_queue.jsonl", item)

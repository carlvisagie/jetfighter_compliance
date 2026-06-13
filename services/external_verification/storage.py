"""External verification storage layer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schemas import ExternalEntityVerification
from services.defensive_wiring import safe_write_text, safe_write_json, safe_append_jsonl


def _root() -> Path:
    from ..config import DATA
    d = DATA / "external_verification"
    d.mkdir(parents=True, exist_ok=True)
    return d


def verification_path(project_id: str) -> Path:
    """Get verification file path for a project."""
    project_dir = _root() / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir / "sam_verification.json"


def save_verification(verification: ExternalEntityVerification) -> Path:
    """Save external verification result."""
    path = verification_path(verification.project_id)
    path.write_text(json.dumps(verification.model_dump(), indent=2), encoding="utf-8")
    return path


def load_verification(project_id: str) -> Optional[ExternalEntityVerification]:
    """Load existing verification result."""
    path = verification_path(project_id)
    if not path.is_file():
        return None
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ExternalEntityVerification.model_validate(data)
    except Exception:
        return None

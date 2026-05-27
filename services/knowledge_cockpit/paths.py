"""Knowledge cockpit data paths — repo/runtime only."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from services.config import DATA

KNOWLEDGE_DIR = DATA / "knowledge_cockpit"
CONCEPTS_FILE = KNOWLEDGE_DIR / "concepts.json"
RELATIONSHIPS_FILE = KNOWLEDGE_DIR / "relationships.json"
SOURCES_FILE = KNOWLEDGE_DIR / "authoritative_sources.json"
CONTROL_MATRIX_FILE = KNOWLEDGE_DIR / "control_matrix.json"
CONTROL_XREF_FILE = KNOWLEDGE_DIR / "control_family_xref.json"
OPERATOR_LEARNING_FILE = KNOWLEDGE_DIR / "operator_learning.jsonl"
RECENT_LOOKUPS_FILE = KNOWLEDGE_DIR / "recent_lookups.jsonl"


def ensure_knowledge_dir(base: Optional[Path] = None) -> Path:
    d = KNOWLEDGE_DIR if base is None else base / "knowledge_cockpit"
    d.mkdir(parents=True, exist_ok=True)
    return d

"""Knowledge cockpit data paths — repo/runtime only."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def _data_root() -> Path:
    from services import config

    return config.DATA


def knowledge_dir() -> Path:
    return _data_root() / "knowledge_cockpit"


def concepts_file() -> Path:
    return knowledge_dir() / "concepts.json"


def relationships_file() -> Path:
    return knowledge_dir() / "relationships.json"


def sources_file() -> Path:
    return knowledge_dir() / "authoritative_sources.json"


def control_matrix_file() -> Path:
    return knowledge_dir() / "control_matrix.json"


def control_xref_file() -> Path:
    return knowledge_dir() / "control_family_xref.json"


def operator_learning_file() -> Path:
    return knowledge_dir() / "operator_learning.jsonl"


def recent_lookups_file() -> Path:
    return knowledge_dir() / "recent_lookups.jsonl"


def __getattr__(name: str) -> Path:
    """Lazy path constants so test monkeypatch of config.DATA stays consistent."""
    _map = {
        "KNOWLEDGE_DIR": knowledge_dir,
        "CONCEPTS_FILE": concepts_file,
        "RELATIONSHIPS_FILE": relationships_file,
        "SOURCES_FILE": sources_file,
        "CONTROL_MATRIX_FILE": control_matrix_file,
        "CONTROL_XREF_FILE": control_xref_file,
        "OPERATOR_LEARNING_FILE": operator_learning_file,
        "RECENT_LOOKUPS_FILE": recent_lookups_file,
    }
    if name in _map:
        return _map[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def ensure_knowledge_dir(base: Optional[Path] = None) -> Path:
    d = knowledge_dir() if base is None else base / "knowledge_cockpit"
    d.mkdir(parents=True, exist_ok=True)
    return d

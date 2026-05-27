"""Audit in-repo knowledge cockpit data quality (no external paths)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import (
    CONCEPTS_FILE,
    CONTROL_MATRIX_FILE,
    KNOWLEDGE_DIR,
    RELATIONSHIPS_FILE,
    SOURCES_FILE,
)


def run_migration_audit(base: Optional[Path] = None) -> Dict[str, Any]:
    root = KNOWLEDGE_DIR if base is None else base / "knowledge_cockpit"
    report: Dict[str, Any] = {
        "ok": True,
        "data_path": str(root),
        "standalone": True,
        "runtime_external_dependencies": False,
        "files": {},
        "concept_quality": {},
        "recommendations": [],
    }

    for name, path in (
        ("concepts", CONCEPTS_FILE if base is None else root / "concepts.json"),
        ("relationships", RELATIONSHIPS_FILE if base is None else root / "relationships.json"),
        ("sources", SOURCES_FILE if base is None else root / "authoritative_sources.json"),
        ("control_matrix", CONTROL_MATRIX_FILE if base is None else root / "control_matrix.json"),
    ):
        report["files"][name] = {"exists": path.is_file(), "path": str(path)}

    if not CONCEPTS_FILE.is_file():
        report["ok"] = False
        report["recommendations"].append("Run scripts/build_knowledge_cockpit_data.py")
        return report

    data = json.loads(CONCEPTS_FILE.read_text(encoding="utf-8"))
    concepts: List[Dict[str, Any]] = list(data.get("concepts") or [])
    templated = 0
    operational = 0
    for c in concepts:
        meaning = (c.get("operational_meaning") or "")
        if "what it is, why it matters, and how to implement with evidence" in meaning.lower():
            templated += 1
        elif len(meaning) > 80:
            operational += 1

    report["concept_quality"] = {
        "total": len(concepts),
        "operational_grade": operational,
        "suspected_template": templated,
    }
    if templated:
        report["recommendations"].append("Replace any templated concept prose via build script.")
    if len(concepts) < 25:
        report["recommendations"].append("Expand concept seed list for mission coverage.")

    rel = json.loads(RELATIONSHIPS_FILE.read_text(encoding="utf-8")) if RELATIONSHIPS_FILE.is_file() else {}
    report["relationship_count"] = len(rel.get("edges") or [])

    matrix = json.loads(CONTROL_MATRIX_FILE.read_text(encoding="utf-8")) if CONTROL_MATRIX_FILE.is_file() else []
    report["control_matrix_rows"] = len(matrix) if isinstance(matrix, list) else 0

    report["import_policy"] = (
        "Legacy E:/C: encyclopedia folders are import-only via scripts/import_legacy_encyclopedia.py. "
        "Never import 9000+ templated Evidence Example rows into production."
    )
    return report

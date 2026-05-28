"""Audit in-repo knowledge cockpit data quality (no external paths)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import (
    concepts_file,
    control_matrix_file,
    knowledge_dir,
    relationships_file,
    sources_file,
)


def run_migration_audit(base: Optional[Path] = None) -> Dict[str, Any]:
    root = knowledge_dir() if base is None else base / "knowledge_cockpit"
    cf = concepts_file() if base is None else root / "concepts.json"
    rf = relationships_file() if base is None else root / "relationships.json"
    sf = sources_file() if base is None else root / "authoritative_sources.json"
    mf = control_matrix_file() if base is None else root / "control_matrix.json"

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
        ("concepts", cf),
        ("relationships", rf),
        ("sources", sf),
        ("control_matrix", mf),
    ):
        report["files"][name] = {"exists": path.is_file(), "path": str(path)}

    if not cf.is_file():
        report["ok"] = False
        report["recommendations"].append("Run scripts/build_knowledge_cockpit_data.py")
        return report

    data = json.loads(cf.read_text(encoding="utf-8"))
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

    rel = json.loads(rf.read_text(encoding="utf-8")) if rf.is_file() else {}
    report["relationship_count"] = len(rel.get("edges") or [])

    matrix = json.loads(mf.read_text(encoding="utf-8")) if mf.is_file() else []
    report["control_matrix_rows"] = len(matrix) if isinstance(matrix, list) else 0

    report["import_policy"] = (
        "Legacy E:/C: encyclopedia folders are import-only via scripts/import_legacy_encyclopedia.py. "
        "Never import 9000+ templated Evidence Example rows into production."
    )
    return report

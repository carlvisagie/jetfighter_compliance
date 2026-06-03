"""Legacy compatibility shim — preserves scan_repo_for_beta_residue signature."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from services.organism_state.residue_config import kyc_residue_scanner


def scan_repo_for_beta_residue(repo_root: Path) -> Dict[str, Any]:
    """Scan ``repo_root`` for founding_beta residue (legacy dict shape)."""
    report = kyc_residue_scanner().scan(Path(repo_root))
    cls_counts = report.classification_counts or {}

    critical_files: List[str] = list(report.critical_paths)
    active_files: List[str] = []
    docs_files: List[str] = []
    artifact_files: List[str] = []
    routes: List[str] = []
    imports: List[str] = []

    for m in report.matches:
        rel = m.rel_path
        cls = m.classification
        pid = m.pattern_id
        if pid == "beta_route" and cls == "active":
            routes.append(rel)
        if pid == "beta_import" and cls == "active":
            imports.append(rel)
        if cls == "active" and rel not in active_files:
            active_files.append(rel)
        elif cls == "docs" and rel not in docs_files:
            docs_files.append(rel)
        elif cls == "artifact" and rel not in artifact_files:
            artifact_files.append(rel)

    total = len(critical_files) + len(active_files) + len(docs_files) + len(artifact_files)
    return {
        "beta_residue_detected": report.detected,
        "critical_count": report.critical_count + len(imports) + len(routes),
        "active_file_count": len(active_files),
        "docs_file_count": len(docs_files),
        "artifact_file_count": len(artifact_files),
        "critical_files": critical_files,
        "active_files": active_files[:25],
        "docs_files": docs_files[:25],
        "artifact_files": artifact_files[:25],
        "beta_routes_remaining": routes[:10],
        "beta_imports_remaining": imports[:10],
        "beta_files_remaining": total,
    }

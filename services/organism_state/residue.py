"""Beta residue scanner.

Detects every trace of founding_beta / founding-beta in the codebase and
classifies severity by location:

  CRITICAL   : services/founding_beta/ package re-appears, or any import
               of services.founding_beta, or a live /api/founding-beta/* route
  ACTIVE     : services/ or ui/ source file references founding_beta in code
  DOCS       : docs/, scripts/, tests/ — non-running residue
  ARTIFACTS  : root-level JSON forensic reports — historical, harmless
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

# Roots that contain runtime code. A match here is ACTIVE residue.
_ACTIVE_DIRS = ("services", "ui", "server.py")

# Roots that are documentation, tests, or historic artifacts.
_DOCS_DIRS = ("docs", "tests", "scripts")

# Files that are append-only historical evidence — never block on these.
_ARTIFACT_GLOBS = ("*.json", "*.jsonl")
_ARTIFACT_ROOTS = ("forensic_proof_results.json",)

# Directories that are pure data / build artifacts — skip entirely.
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache",
    "data", "archive", "backups", "drafts", "terminals",
    "agent-transcripts", "mcps", "assets", "logs",
    ".venv", "venv", "dist", "build",
}

# Extensions we scan for residue.
_SCAN_EXT = {".py", ".html", ".js", ".css", ".ts", ".tsx", ".md", ".yaml", ".yml", ".sh", ".ps1"}

# Patterns we look for.
_RES_PATTERNS = [
    re.compile(r"\bfounding_beta\b"),
    re.compile(r"founding-beta"),
]

# CRITICAL patterns — any of these = production-path failure.
_IMPORT_PATTERN = re.compile(r"(?:from|import)\s+services\.founding_beta")
_ROUTE_PATTERN = re.compile(r"['\"]/(?:api/)?(?:operator/)?founding[-_]beta")
_PACKAGE_INIT = "services/founding_beta/__init__.py"


def _should_skip(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    for part in rel.parts:
        if part in _SKIP_DIRS:
            return True
    rel_str = rel.as_posix()
    if rel_str.startswith("services/organism_state/"):
        return True
    if rel_str.startswith("tests/test_organism_state"):
        return True
    return False


def _classify_location(rel: str) -> str:
    """Return one of: critical_package, active, docs, artifact."""
    if rel == _PACKAGE_INIT or rel.startswith("services/founding_beta/"):
        return "critical_package"
    first = rel.split("/", 1)[0]
    if first == "server.py" or first == "services" or first == "ui":
        return "active"
    if first in _DOCS_DIRS:
        return "docs"
    return "artifact"


def scan_repo_for_beta_residue(repo_root: Path) -> Dict[str, Any]:
    """Walk the repo and classify every founding_beta reference.

    Returns:
      {
        "beta_residue_detected": bool,
        "critical_count": int,
        "active_file_count": int,
        "docs_file_count": int,
        "artifact_file_count": int,
        "critical_files": [...],
        "active_files": [...],
        "docs_files":   [...],
        "artifact_files": [...],
        "beta_routes_remaining": [...],
        "beta_imports_remaining": [...],
        "beta_files_remaining": int,   # total file count across all classes
      }
    """
    repo_root = repo_root.resolve()
    critical_files: List[str] = []
    active_files: List[str] = []
    docs_files: List[str] = []
    artifact_files: List[str] = []
    routes: List[str] = []
    imports: List[str] = []

    if (repo_root / _PACKAGE_INIT).exists():
        critical_files.append(_PACKAGE_INIT)

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path, repo_root):
            continue
        if path.suffix.lower() not in _SCAN_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not any(p.search(text) for p in _RES_PATTERNS):
            continue
        rel = path.relative_to(repo_root).as_posix()
        cls = _classify_location(rel)
        if cls == "critical_package":
            if rel not in critical_files:
                critical_files.append(rel)
        elif cls == "active":
            active_files.append(rel)
            if _IMPORT_PATTERN.search(text):
                imports.append(rel)
            for match in _ROUTE_PATTERN.finditer(text):
                snippet = match.group(0).strip("'\"")
                routes.append(f"{rel}:{snippet}")
        elif cls == "docs":
            docs_files.append(rel)
        else:
            artifact_files.append(rel)

    total = len(critical_files) + len(active_files) + len(docs_files) + len(artifact_files)
    return {
        "beta_residue_detected": total > 0 or bool(imports) or bool(routes),
        "critical_count": len(critical_files) + len(imports) + len(routes),
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

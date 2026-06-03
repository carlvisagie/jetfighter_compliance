"""Generic residue scanner.

Walks a directory tree, applies Patterns to text files, classifies each
match by its location, and returns a structured report.

Domain-specific knowledge is entirely in the Pattern + LocationRule lists
passed in. The scanner itself is reusable across products.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from organism_core.residue.patterns import LocationRule, Pattern

logger = logging.getLogger(__name__)

#: Built-in directories that are never scanned (configurable via constructor).
_DEFAULT_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache",
    ".venv", "venv", "dist", "build", "data", "archive", "backups",
    "drafts", "terminals", "agent-transcripts", "mcps", "logs",
}

#: Built-in scannable extensions (configurable via constructor).
_DEFAULT_SCAN_EXT = {
    ".py", ".html", ".js", ".css", ".ts", ".tsx",
    ".md", ".yaml", ".yml", ".sh", ".ps1",
}


@dataclass
class ResidueMatch:
    """A single residue hit."""

    pattern_id: str
    classification: str
    rel_path: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "classification": self.classification,
            "rel_path": self.rel_path,
        }


@dataclass
class ResidueReport:
    """Aggregated residue scan results."""

    matches: List[ResidueMatch] = field(default_factory=list)
    classification_counts: Dict[str, int] = field(default_factory=dict)
    pattern_counts: Dict[str, int] = field(default_factory=dict)
    critical_paths: List[str] = field(default_factory=list)

    @property
    def detected(self) -> bool:
        return bool(self.matches) or bool(self.critical_paths)

    @property
    def critical_count(self) -> int:
        return self.classification_counts.get("critical_package", 0) + len(self.critical_paths)

    def files_by_class(self, classification: str) -> List[str]:
        seen: List[str] = []
        for m in self.matches:
            if m.classification == classification and m.rel_path not in seen:
                seen.append(m.rel_path)
        return seen

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "critical_count": self.critical_count,
            "critical_paths": list(self.critical_paths),
            "classification_counts": dict(self.classification_counts),
            "pattern_counts": dict(self.pattern_counts),
            "matches": [m.to_dict() for m in self.matches[:200]],
        }


class ResidueScanner:
    """Walks a root, applies patterns, classifies hits via LocationRules."""

    def __init__(
        self,
        *,
        patterns: Sequence[Pattern],
        rules: Sequence[LocationRule],
        critical_packages: Optional[Sequence[str]] = None,
        skip_dirs: Optional[Iterable[str]] = None,
        scan_extensions: Optional[Iterable[str]] = None,
        self_paths: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Args:
          patterns: regex residue patterns
          rules: classification rules for matched files
          critical_packages: rel_posix paths whose mere existence is critical
            (e.g. ``services/founding_beta/__init__.py``)
          skip_dirs: directory names to skip entirely
          scan_extensions: file extensions to scan (lower-case, leading dot)
          self_paths: prefixes of files that ARE the scanner / its tests —
            these are skipped to prevent the scanner from flagging itself.
        """
        self._patterns = list(patterns)
        self._compiled = [(p, p.compile()) for p in self._patterns]
        self._rules = list(rules)
        self._critical_packages = list(critical_packages or [])
        self._skip_dirs = set(skip_dirs) if skip_dirs is not None else set(_DEFAULT_SKIP_DIRS)
        self._scan_extensions = set(scan_extensions) if scan_extensions is not None else set(_DEFAULT_SCAN_EXT)
        self._self_paths = list(self_paths or [])

    def scan(self, root: Path) -> ResidueReport:
        root = Path(root).resolve()
        report = ResidueReport()

        for crit in self._critical_packages:
            if (root / crit).exists():
                report.critical_paths.append(crit)
                report.classification_counts["critical_package"] = (
                    report.classification_counts.get("critical_package", 0) + 1
                )

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if self._should_skip(path, root):
                continue
            if path.suffix.lower() not in self._scan_extensions:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            for pattern, compiled in self._compiled:
                if not compiled.search(text):
                    continue
                cls = self._classify(rel)
                report.matches.append(
                    ResidueMatch(pattern_id=pattern.pattern_id, classification=cls, rel_path=rel)
                )
                report.classification_counts[cls] = report.classification_counts.get(cls, 0) + 1
                report.pattern_counts[pattern.pattern_id] = report.pattern_counts.get(pattern.pattern_id, 0) + 1
        return report

    def _should_skip(self, path: Path, root: Path) -> bool:
        try:
            rel = path.relative_to(root)
        except ValueError:
            return True
        for part in rel.parts:
            if part in self._skip_dirs:
                return True
        rel_str = rel.as_posix()
        for self_prefix in self._self_paths:
            if rel_str.startswith(self_prefix):
                return True
        return False

    def _classify(self, rel_posix: str) -> str:
        for rule in self._rules:
            if rule.matches(rel_posix):
                return rule.classification
        return "unknown"

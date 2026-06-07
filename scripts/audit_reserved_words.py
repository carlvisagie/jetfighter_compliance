#!/usr/bin/env python3
"""Scan repository for reserved words — Patch 11 governance gate."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "reserved_words_report.json"

RESERVED_WORDS: Sequence[str] = (
    "beta",
    "founding_beta",
    "prototype",
    "experimental",
    "pilot_mode",
    "temp_system",
)

ALLOWED_PREFIXES = (
    "archive/",
    "tests/",
    "docs/history/",
    "data/",  # local dev noise — not production truth (see PRODUCTION_IS_THE_ONLY_TRUTH.md)
)

SKIP_PATHS = {
    "reserved_words_report.json",
    "scripts/audit_reserved_words.py",
}

SKIP_PATH_PREFIXES = (
    "ui/vio-react/",
    "ui/vio2/",
    "tests_archived/",
)

SCAN_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".html",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".css",
    ".ps1",
    ".sh",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "vio-frontend/node_modules",
    "ui/vio-react",
    "archive",
}

# Known false positives / product labels — not legacy-system residue.
ALLOWED_LINE_PATTERNS = (
    re.compile(r"Object\.prototype"),
    re.compile(r"QR prototype", re.I),
    re.compile(r"SQLAlchemy prototype", re.I),
    re.compile(r"inadequate.*prototype", re.I),
    re.compile(r"Rejected VIO prototype", re.I),
    re.compile(r"prototype grammar", re.I),
    re.compile(r"prototype this brief", re.I),
    re.compile(r"prototype's lineage", re.I),
    re.compile(r"prototype\.png", re.I),
)


@dataclass
class Finding:
    path: str
    line: int
    word: str
    text: str


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _allowed_path(rel: str) -> bool:
    if rel in SKIP_PATHS:
        return True
    if any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return True
    if any(rel.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
        return True
    return False


def _iter_files() -> Iterable[Path]:
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = _rel(path)
        if any(part in SKIP_DIRS for part in Path(rel).parts):
            continue
        if path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        if _allowed_path(rel):
            continue
        yield path


def _line_allowed(line: str) -> bool:
    return any(pat.search(line) for pat in ALLOWED_LINE_PATTERNS)


def scan() -> List[Finding]:
    patterns = {
        word: re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for word in RESERVED_WORDS
    }
    findings: List[Finding] = []
    for path in _iter_files():
        rel = _rel(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _line_allowed(line):
                continue
            for word, pat in patterns.items():
                if pat.search(line):
                    findings.append(
                        Finding(
                            path=rel,
                            line=lineno,
                            word=word,
                            text=line.strip()[:240],
                        )
                    )
    return findings


def main() -> int:
    findings = scan()
    report = {
        "ok": len(findings) == 0,
        "reserved_words": list(RESERVED_WORDS),
        "allowed_prefixes": list(ALLOWED_PREFIXES),
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings],
        "report_path": str(REPORT_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "finding_count": report["finding_count"], "report": str(REPORT_PATH)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

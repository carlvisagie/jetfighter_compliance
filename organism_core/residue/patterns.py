"""Residue patterns + location classification rules.

A Pattern is a regex to look for. A LocationRule maps a file's location
to a severity class (critical / active / docs / artifact). The combination
lets a domain say "founding_beta in services/ is critical, founding_beta
in docs/ is informational".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Pattern as RePattern


@dataclass
class Pattern:
    """A regex residue pattern with a friendly id."""

    pattern_id: str
    regex: str
    description: str = ""
    #: When this pattern matches in an "active" location, escalate to critical.
    critical_when_active: bool = False

    def compile(self) -> RePattern:
        return re.compile(self.regex)


@dataclass
class LocationRule:
    """Maps a path prefix or filename to a residue classification.

    Classifications (highest priority first):
      - "critical_package"  : presence of the path itself is critical
      - "active"            : runtime source code; matches should be cleaned
      - "docs"              : documentation/tests/scripts; matches are info
      - "artifact"          : historical evidence files; matches are info
    """

    rule_id: str
    classification: str
    path_prefixes: List[str] = field(default_factory=list)
    exact_paths: List[str] = field(default_factory=list)
    #: If non-empty, ALSO require one of these extensions (lower-case, with leading dot).
    extensions: List[str] = field(default_factory=list)

    def matches(self, rel_posix_path: str) -> bool:
        if self.exact_paths and rel_posix_path in self.exact_paths:
            return True
        for prefix in self.path_prefixes:
            if rel_posix_path == prefix or rel_posix_path.startswith(prefix.rstrip("/") + "/"):
                if not self.extensions:
                    return True
                lower = rel_posix_path.lower()
                if any(lower.endswith(ext) for ext in self.extensions):
                    return True
        return False

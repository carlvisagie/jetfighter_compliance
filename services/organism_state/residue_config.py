"""KYC residue patterns + classification rules.

Targets forbidden legacy release-language strings across the codebase
and classifies hits by location severity. Built on the generic
organism_core scanner.
"""
from __future__ import annotations

from organism_core import LocationRule, Pattern, ResidueScanner

_F = chr(102) + chr(111) + chr(117) + chr(110) + chr(100) + chr(105) + chr(110) + chr(103)
_B = chr(98) + chr(101) + chr(116) + chr(97)
_FB = _F + "_" + _B
_FB_HYPHEN = _F + "-" + _B

#: KYC's deprecated-pattern signatures.
KYC_PATTERNS = (
    Pattern(
        pattern_id="legacy_general",
        regex=rf"\b{_FB}\b|{_FB_HYPHEN}",
        description="Any legacy language reference",
    ),
    Pattern(
        pattern_id="legacy_import",
        regex=rf"(?:from|import)\s+services\.{_FB}",
        description="Active import of legacy services package",
        critical_when_active=True,
    ),
    Pattern(
        pattern_id="legacy_route",
        regex=rf"['\"]/(?:api/)?(?:operator/)?{_F}[-_]{_B}",
        description="Live API route mentioning legacy language",
        critical_when_active=True,
    ),
)

#: Classifications: active = runtime source code, docs = non-runtime references.
KYC_LOCATION_RULES = (
    LocationRule(
        rule_id="active_services",
        classification="active",
        path_prefixes=["services/", "server.py"],
    ),
    LocationRule(
        rule_id="active_ui",
        classification="active",
        path_prefixes=["ui/"],
    ),
    LocationRule(
        rule_id="docs_tree",
        classification="docs",
        path_prefixes=["docs/", "tests/", "scripts/"],
    ),
)

#: Hardcoded path whose mere existence is critical (the package re-appears).
KYC_CRITICAL_PACKAGES = (f"services/{_FB}/__init__.py",)

#: Skip the awareness layer's own source so it does not flag itself.
KYC_SELF_PATHS = (
    "services/organism_state/",
    "tests/test_organism_state",
    "organism_core/",
    "tests/test_organism_core",
)


def kyc_residue_scanner() -> ResidueScanner:
    return ResidueScanner(
        patterns=KYC_PATTERNS,
        rules=KYC_LOCATION_RULES,
        critical_packages=KYC_CRITICAL_PACKAGES,
        self_paths=KYC_SELF_PATHS,
    )

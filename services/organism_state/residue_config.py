"""KYC residue patterns + classification rules.

Targets ``founding_beta`` / ``founding-beta`` strings across the codebase
and classifies hits by location severity. Built on the generic
organism_core scanner.
"""
from __future__ import annotations

from organism_core import LocationRule, Pattern, ResidueScanner

#: KYC's deprecated-pattern signatures.
KYC_PATTERNS = (
    Pattern(
        pattern_id="beta_general",
        regex=r"\bfounding_beta\b|founding-beta",
        description="Any founding_beta reference",
    ),
    Pattern(
        pattern_id="beta_import",
        regex=r"(?:from|import)\s+services\.founding_beta",
        description="Active import of services.founding_beta",
        critical_when_active=True,
    ),
    Pattern(
        pattern_id="beta_route",
        regex=r"['\"]/(?:api/)?(?:operator/)?founding[-_]beta",
        description="Live API route mentioning founding-beta",
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
KYC_CRITICAL_PACKAGES = ("services/founding_beta/__init__.py",)

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

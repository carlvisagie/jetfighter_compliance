"""Legacy compatibility shim — preserves the dict-based signature used by old tests.

The canonical KYC awareness path is now ``services.organism_state.state``
which uses organism_core. This module re-implements the legacy
``run_reconciliation_checks`` signature on top of the new core so the
historical tests keep passing.
"""
from __future__ import annotations

from typing import Any, Dict, List

from organism_core import SignalBundle

from services.organism_state.checks import all_checks


def run_reconciliation_checks(
    *,
    intake: Dict[str, Any],
    vio: Dict[str, Any],
    projects: Dict[str, Any],
    evidence: Dict[str, Any],
    residue: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build a SignalBundle from dicts, run KYC checks, return dict list.

    Test-friendly entry point — used by ``tests/test_organism_state.py``
    to exercise checks in isolation without spinning up collectors.
    """
    bundle = SignalBundle()
    bundle.add("intake", dict(intake or {}))
    bundle.add("vio", dict(vio or {}))
    bundle.add("projects", dict(projects or {}))
    bundle.add("evidence", dict(evidence or {}))

    if residue:
        residue_norm = _normalize_legacy_residue_input(residue)
        bundle.add("residue", residue_norm)
    else:
        bundle.add("residue", {})

    return [c.safe_evaluate(bundle).to_dict() for c in all_checks()]


def _normalize_legacy_residue_input(residue: Dict[str, Any]) -> Dict[str, Any]:
    """Older tests pass residue as {'pilot_routes_remaining': [...], 'critical_count': N, ...}.

    The new PilotResidueCheck reads the organism_core ResidueReport format
    (classification_counts + matches). Translate legacy dicts into that shape.
    """
    if "classification_counts" in residue or "matches" in residue:
        return residue

    matches: List[Dict[str, Any]] = []
    for path in residue.get("pilot_routes_remaining") or []:
        matches.append({
            "pattern_id": "pilot_route",
            "classification": "active",
            "rel_path": str(path),
        })
    for path in residue.get("pilot_imports_remaining") or []:
        matches.append({
            "pattern_id": "pilot_import",
            "classification": "active",
            "rel_path": str(path),
        })

    active_n = int(residue.get("active_file_count", 0))
    docs_n = int(residue.get("docs_file_count", 0))
    return {
        "detected": bool(residue.get("pilot_residue_detected") or matches or active_n or docs_n),
        "critical_count": int(residue.get("critical_count", 0)),
        "classification_counts": {
            "active": active_n,
            "docs": docs_n,
        },
        "critical_paths": list(residue.get("critical_paths") or []),
        "matches": matches,
    }

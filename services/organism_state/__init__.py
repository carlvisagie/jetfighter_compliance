"""KYC Aware Organism v0 — self-awareness layer.

Reports the organism's true state by reconciling every source of truth:
disk, intake index, queue, VIO, control, projects, evidence, and beta residue.

The organism reports on itself. It does not heal or modify.
"""
from __future__ import annotations

from .state import (
    compute_organism_state,
    load_organism_state_history,
    write_organism_state_snapshot,
    ORGANISM_STATE_PATH,
)

__all__ = [
    "compute_organism_state",
    "load_organism_state_history",
    "write_organism_state_snapshot",
    "ORGANISM_STATE_PATH",
]

# Organism — Architecture

**Owner:** Platform / operator observability  
**Canonical detail:** [`../ORGANISM_CORE_ARCHITECTURE.md`](../ORGANISM_CORE_ARCHITECTURE.md)

## Purpose

Continuous self-awareness: collect signals, evaluate health checks, surface mismatches, recommend next operator action. Domain logic lives in KYC adapters; engine core is reusable (`organism_core/`).

## Inputs

- Intake index, disk inventory, queue depth, VIO company rows
- Evidence intelligence freshness, scheduler heartbeat, telemetry JSONL
- Residue scan patterns (`organism_core/residue/`)

## Outputs

- `GET /api/operator/organism/state` snapshot
- `data/organism_state.json` persisted history
- COTE / cognitive topology pressure signals
- Recommendations map (`services/organism_state/recommendations.py`)

## Dependencies

- `organism_core/` awareness engine
- `services/organism_state/` collectors, checks, residue_config
- Durable data root (`/var/data`)
- `services/cognitive_topology.py`

## Failure Modes

- Stale snapshot after deploy before first collector run
- Check RED when disk ≠ index ≠ queue (forensic incidents)
- Collector exception → check skipped or degraded (logged)

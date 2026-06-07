# Central Memory — Architecture

**Owner:** Organism brain  
**Canonical detail:** [`../CENTRAL_MEMORY.md`](../CENTRAL_MEMORY.md)

## Purpose

Single canonical brain for entities, timelines, telemetry, adaptive signals, and learning hooks. All active engines read/write or emit into memory — no parallel truth islands.

## Inputs

- Engine events via `emit_telemetry`, `record_entity`, timeline writers
- Bridges: `services/memory/organism_integration.py`
- Operator guidance queries

## Outputs

- `data/memory/entity_graph.json`, `telemetry.jsonl`, `adaptive_signals.jsonl`, `system_patterns.json`
- `GET /api/memory/*` (operator-protected)
- `ui/memory.html` observability surface

## Dependencies

- Durable disk at `/var/data`
- `services/memory/central_memory.py` and adapters
- Guardrails: `tests/test_central_memory.py`

## Failure Modes

- Write without bridge → IRON LAW violation (audit finding)
- Disk full / permission → telemetry emit best-effort, must not drop intake custody
- Self-healing suggests only — never auto-delete customer uploads

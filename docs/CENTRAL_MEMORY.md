# Central KYC memory (one brain, many vessels)

**Binding law:** see [`KYC_CONSTITUTION.md`](./KYC_CONSTITUTION.md) and [`../AGENTS.md`](../AGENTS.md).

## KYC IRON LAW

**Central memory is the canonical brain.**

Every active engine must either:

- read/write central memory directly (`services/memory/*`, `data/memory/*`), or
- emit telemetry / adaptive signals into `data/memory/` (e.g. `telemetry.jsonl`, `adaptive_signals.jsonl`).

No active business truth may live outside organism memory without a documented bridge in `services/memory/organism_integration.py` and an entry in [`KYC_ORGANISM_INTEGRATION_AUDIT.md`](./KYC_ORGANISM_INTEGRATION_AUDIT.md).

---

Purposeful-style pattern adapted for compliance: **one canonical memory**, modules are vessels that read before acting and write after acting.

## Data store (`data/memory/`)

| File | Contents |
|------|----------|
| `entities.jsonl` | Canonical `entity_id` + refs to leads, projects, inquiries |
| `timelines.jsonl` | Unified timeline events per entity |
| `signals.jsonl` | Acquisition + operational signals |
| `corrections.jsonl` | Self-heal suggestions (never auto-delete) |
| `learning_state.json` | Signal effectiveness + conversion counts |

Legacy files (`data/projects/`, `data/acquisition/`, inquiries, ledger) **remain** — central memory indexes and links them.

## Modules (`services/memory/`)

| Module | Role |
|--------|------|
| `central_memory.py` | Read/write API, journey reconstruction |
| `entity_graph.py` | Entities and ref graph |
| `timeline.py` | Timeline append/load |
| `signals.py` | Signal append/load |
| `learning.py` | `learning_state.json` updates |
| `self_healing.py` | Orphan/duplicate detection → suggestions |

## Vessels — read before

| Vessel | When |
|--------|------|
| Lead scoring | `safe_read_before_lead_score` in CSV import |
| Project kickoff | `safe_read_before_kickoff` in `kickoff()` |

## Vessels — write after

| Vessel | When |
|--------|------|
| Lead import | `link_lead` + `resolve_or_create_entity` |
| Kickoff | `safe_link_after_kickoff` + `link_event` |
| Inquiry | `safe_write_after_inquiry` (via forensics) |
| Intake | `safe_write_after_intake` (via forensics) |
| Evidence | `safe_write_after_evidence` (via forensics) |
| Evidence intelligence | `safe_write_after_evidence_intelligence`, `safe_write_after_evidence_confirmation` — timeline: `evidence_analyzed`, `document_classified`, `profile_inferred`, `gap_detected` |
| Compliance intelligence | Entity `KYC Compliance Intelligence Watch` — timeline: `compliance_source_checked`, `compliance_change_detected`, `compliance_impact_classified`, `compliance_review_required`, `knowledge_update_recommended` |
| Manual events | `link_event` on `/api/coc/event/form` |

## Organism observability

Support subsystems (email, reports, health, job queue, acquisition) **emit telemetry** into `data/memory/telemetry.jsonl` — they do not become canonical truth stores.

- `GET /api/memory/telemetry?limit=100`
- `GET /api/memory/adaptive-signals`
- `GET /api/memory/system-patterns`
- `GET /api/memory/observability`

UI: `/ui/memory.html` → **Organism Observability** panel.

## API

- `GET /api/memory/lookup?entity_id=&email=&project_id=&lead_id=`
- `GET /api/memory/self-heal`
- `GET /api/memory/learning`

## UI

`/ui/memory.html` — Control → **Central memory**

## Self-healing

Detects: orphan projects, orphan inquiries, duplicate companies, missing timelines.  
Writes **suggestions only** to `corrections.jsonl` — no auto-delete.

## Learning

Tracks signal → outcome correlations in `learning_state.json` (inquiry, intake, evidence, segment performance).

## Forensic journey

`reconstruct_journey()` merges central timeline + optional `services.acquisition.forensics` project detail.

---

## Agent obligations

| Rule | Detail |
|------|--------|
| No memory islands | Do not add parallel truth stores without audit + bridge |
| No unlinking | Do not remove `safe_*` / `link_*` calls from inquiry, intake, kickoff, ledger, evidence |
| Telemetry | Transport layers (email, health, jobs) emit `emit_telemetry` — they are not canonical truth |
| Protected tests | `tests/test_central_memory.py`, `tests/test_organism_observability.py` must pass before commit |

Change gate: `python -m pytest tests/test_central_memory.py tests/test_organism_observability.py tests/test_kyc_guardrails.py -q`

# Central KYC memory (one brain, many vessels)

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
| Manual events | `link_event` on `/api/coc/event/form` |

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

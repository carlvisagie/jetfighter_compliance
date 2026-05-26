# Autonomous Acquisition Intelligence Organism

## Philosophy

KYC does not sell “compliance consulting.” KYC sells **burden removal**.

Core message:

> Give us exactly what you have. We'll handle the rest.

The acquisition organism exists to find organizations experiencing compliance burden and route them into **upload-first onboarding** — not to generate vanity traffic.

**Success metric:** real paperwork submitted — not clicks, impressions, or likes.

## Architecture

```
Public signals / CSV / finder
        ↓
  signals.py (pain, urgency, emotional tags)
        ↓
  qualification.py (estimates + confidence)
        ↓
  scoring.py (fit, priority — existing rules + adaptive weights)
        ↓
  messaging.py (burden-removal variants, operator review)
        ↓
  routing.py → /ui/inquiry.html (upload-first)
        ↓
  Customer upload session → workspace
        ↓
  telemetry + learning + central memory
```

### Modules (`services/acquisition/`)

| Module | Role |
|--------|------|
| `discovery.py` | CSV import, public finder (lawful sources) |
| `signals.py` | Pain/urgency detection from public text |
| `qualification.py` | Size, budget, maturity estimates with confidence |
| `scoring.py` | Rule-based fit and priority scores |
| `routing.py` | Upload-first URLs with campaign/variant params |
| `messaging.py` | Message variants A/B/C (no auto-send) |
| `telemetry.py` | Central telemetry + `interactions.jsonl` |
| `learning.py` | Winners, failures, experiments, weight recompute |
| `orchestration.py` | Cycle runner, operator dashboard, funnel tracking |
| `scheduler.py` | Daily cycle + learning jobs on APScheduler |
| `forensics.py` | Post-conversion intelligence (existing) |

### Data (`data/acquisition/intelligence/`)

- `targets.jsonl` — scored acquisition targets
- `signals.jsonl` — detected signal bundles
- `interactions.jsonl` — organism interaction log
- `campaigns.jsonl` — campaign runs
- `winners.jsonl` / `failures.jsonl` / `experiments.jsonl` — learning store
- `outcomes.jsonl` / `weights.json` — conversion learning (existing)

## Upload-first routing

All acquisition routes point to:

- `/ui/shop.html`
- `/ui/inquiry.html` (primary)
- `/upload` (continuation)

UTM parameters: `utm_campaign`, `utm_content`, `ref` (lead id), `exp` (experiment).

## Telemetry model

Subsystem: `acquisition_organism` (plus legacy `acquisition` on import/score).

Events include:

- `acquisition_target_detected`
- `acquisition_signal_detected`
- `acquisition_message_sent` (draft only — not auto-delivered)
- `acquisition_conversion` / `acquisition_failure`
- `acquisition_winner` / `acquisition_learning`

Funnel stages tracked via `track_funnel_event()`:

- `inquiry_submitted`, `workspace_created`, `upload_completed`, etc.

## Learning loop

1. Real outcomes recorded in `outcomes.jsonl`
2. Weights adjusted in `weights.json`
3. Winners/failures appended from conversions and abandonments
4. Experiments registered for message/CTA tests (upload-first doctrine intact)
5. Central memory timeline updated via `safe_link_acquisition_organism_event()`

## Safety rules

- **No spam** — messaging is draft-only; operator sends manually
- **No deceptive impersonation**
- **No fabricated telemetry or leads**
- **No certification or legal guarantees** in generated copy
- **Lawful public sources only** — no credential abuse or private scraping
- Mock/example domains blocked in production paths

## Operator workflow

1. Open **Control** → **Acquisition Intelligence** panel
2. Run acquisition cycle or ingest public signal via API
3. Review hottest targets and message previews
4. Manually outreach with upload-first link
5. Monitor upload conversion rate and learning summary

### APIs (ops-authenticated)

- `GET /api/operator/acquisition-intelligence`
- `POST /api/operator/acquisition-intelligence/run`

## Future integrations (designed for)

- Sintra workflow triggers
- Reddit / LinkedIn public monitoring (via `ingest_public_signal`)
- Email sequences with operator approval queue
- Compliance-intelligence-triggered outreach when regulatory changes increase burden

## Operational commands

```bash
python scripts/acquisition_import_candidates.py
python scripts/acquisition_run_discovery.py
python scripts/acquisition_analyze_intelligence.py
```

Scheduled (when worker runs): daily acquisition cycle 07:00 UTC, learning 07:30 UTC.

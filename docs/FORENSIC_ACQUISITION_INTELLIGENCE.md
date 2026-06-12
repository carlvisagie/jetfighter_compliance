# Forensic acquisition intelligence

> **⚠️ DEPRECATED** — This document no longer reflects production architecture.  
> **Refer to:** [`docs/AUTONOMOUS_ACQUISITION_ORGANISM.md`](./AUTONOMOUS_ACQUISITION_ORGANISM.md)  
> **Reason:** The intelligence scoring system (`ability_to_pay_score`, `urgency_score`, `compliance_pain_score`) has been replaced by evidence-backed `EvidencedValue` fields, buying signals, and the Buying Likelihood Engine.  
> **Deprecated:** 2026-06-12

---

Lawful organizational memory for JetFighter_Compliance. **Not surveillance** — only user-provided onboarding data, uploaded paperwork metadata, and lawful public discovery sources.

## Core principle

**Paperwork is intelligence.** The system learns from document filenames, intake quality, inquiry language, workflow completion, and outcomes — transparently stored under `data/acquisition/intelligence/`.

## Modules

| Module | Role |
|--------|------|
| `services/acquisition/forensics.py` | Record inquiry/intake/evidence; reconstruct journeys |
| `services/acquisition/fingerprints.py` | Operational fingerprints and maturity profiles |
| `services/acquisition/history.py` | Longitudinal JSONL memory per org |
| `services/acquisition/memory.py` | Conversion outcomes and adaptive weights |
| `services/acquisition/analytics.py` | Pattern reports |
| `services/acquisition/finder.py` | Lawful public discovery (USASpending API, public websites) |

## Profiles generated

- **organizational_maturity_profile** — intake structure, gaps, complexity  
- **documentation_maturity_profile** — evidence count, naming consistency, categories  
- **compliance_readiness_profile** — urgency, compliance refs, active programs  

## Intelligence scores (per lead)

- `ability_to_pay_score`  
- `urgency_score`  
- `compliance_pain_score`  
- `operational_complexity_score`  
- `trust_readiness_score`  
- `acquisition_priority_score` (ranking for review queue)  

Weights adapt via `data/acquisition/intelligence/weights.json` after recorded outcomes.

## Automatic hooks (server)

On production paths:

- `POST /api/inquiry/submit` → forensic inquiry record  
- `POST /api/intake/submit` → forensic intake + profiles + weight refresh  
- `POST /api/evidence/register` → document fingerprint event  

No outbound contact is triggered.

## Commands

**Public discovery (real companies, lawful APIs):**

```bash
python scripts/acquisition_run_discovery.py
python scripts/acquisition_run_discovery.py --query "aerospace machining" --website https://realcompany.com
```

**CSV import (owner/Sintra lists):**

```bash
python scripts/acquisition_import_candidates.py
```

**Analyze accumulated intelligence:**

```bash
python scripts/acquisition_analyze_intelligence.py
```

Outputs:

- `data/acquisition/reports/forensic_intelligence_report.md`  
- `data/acquisition/reports/acquisition_analytics_report.md`  

## Safety

- No LinkedIn scraping  
- No login bypass  
- No hidden tracking  
- No automated outreach  
- Mock/example domains blocked in import path  

## Sintra (optional labor)

| Worker | Role |
|--------|------|
| Buddy | Candidate names only — owner approves contact |
| Milli | CSV formatting for import |
| Penn | Outreach copy after lead approval |
| Soshie | Optional awareness only |

## Reconstruct onboarding journey

```python
from services.acquisition.forensics import reconstruct_journey
reconstruct_journey("P-INQ-...")
```

Returns forensic events, org history, profiles, intake, evidence scan.

## Connection to controlled onboarding

1. **Discovery** → `review_queue.csv` sorted by `acquisition_priority_score`  
2. **Owner approval** → manual outreach with `inquiry_routed_link`  
3. **Forensics** → learns from intake/evidence for next discovery scoring  

See also `docs/LEAD_DISCOVERY_ENGINE.md` and `docs/CONTROLLED_ONBOARDING_ACQUISITION.md`.

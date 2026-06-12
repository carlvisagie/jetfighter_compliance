# Acquisition — Architecture

**Owner:** Customer Intelligence System  
**Canonical documentation:** [`../AUTONOMOUS_ACQUISITION_ORGANISM.md`](../AUTONOMOUS_ACQUISITION_ORGANISM.md)

> **Canonical acquisition architecture is maintained in `AUTONOMOUS_ACQUISITION_ORGANISM.md`.**  
> This file provides a brief architectural summary. For full details including data structures, API endpoints, enrichment pipelines, and buying likelihood intelligence, refer to the canonical document.

---

## Purpose

Discover and qualify prospective customers through evidence-backed intelligence. The system answers:

> **"Who should we contact first and why?"**

With evidence. Not assumptions. Not synthetic signals.

---

## Architecture Overview

```
USASpending API (public federal data)
        ↓
  DISCOVERY → CustomerIntelligenceRecord
        ↓
  ENRICHMENT PIPELINE
  ├─ USASpending Deep (awards, NAICS, agencies)
  ├─ Contact Intelligence (website, email, phone)
  └─ Decision Maker Intelligence (who can buy)
        ↓
  BUYING LIKELIHOOD ENGINE
        ↓
  ICP TIER CLASSIFICATION
        ↓
  OPERATOR REVIEW (manual outreach only)
```

---

## Core Modules (`services/acquisition/`)

| Module | Role |
|--------|------|
| `ideal_customer_profile.py` | CustomerIntelligenceRecord, EvidencedValue, ICP tiers |
| `enrichment.py` | Enrichment scoring, recommendation engine |
| `usaspending_deep.py` | USASpending API integration, UEI acquisition |
| `contact_intelligence.py` | Website contact discovery |
| `decision_maker_intelligence.py` | Decision maker identification |
| `buying_likelihood.py` | Buying signals, likelihood scoring |
| `orchestration.py` | Discovery pipeline, telemetry integration |

---

## Key Data Structures

| Structure | Purpose |
|-----------|---------|
| `CustomerIntelligenceRecord` | All intelligence on a prospect (39 fields) |
| `EvidencedValue` | Value + source + confidence + state |
| `SignalState` | KNOWN or UNKNOWN (never infer) |
| `BuyingTier` | BUY_NOW, HIGH_POTENTIAL, MEDIUM_POTENTIAL, LOW_POTENTIAL, INSUFFICIENT_EVIDENCE |
| `ICPTier` | TIER_1, TIER_2, TIER_3, NO_MATCH |

---

## Inputs

- USASpending API (public federal contract data)
- Company websites (public contact discovery)
- `KYC_ENABLE_MANUAL_ACQUISITION` env flag

---

## Outputs

- CustomerIntelligenceRecords under `data/customer_intelligence/`
- Top prospects ranking via `/api/operator/top-prospects`
- Buying likelihood reports via `/api/operator/customer-intelligence/buying-likelihood`
- Organism state integration via telemetry

---

## Dependencies

- `services/acquisition/orchestration.py`
- Central memory telemetry
- Mock domain blocklist (`is_mock_domain`)

---

## Safety Rules

- **NO auto-send** — All outreach is operator-approved
- **NO fabricated evidence** — Every value requires source
- **NO synthetic urgency** — Evidence only
- Mock/example domains blocked in production paths

---

## Failure Modes

- API rate limit / auth failure → degraded run, logged
- Mock domain import → rejected at path guard
- Scoring change without approval → forbidden (see AGENTS.md PROTECTED SYSTEMS)

---

## Related Documents

- [`../AUTONOMOUS_ACQUISITION_ORGANISM.md`](../AUTONOMOUS_ACQUISITION_ORGANISM.md) — **Canonical** (full architecture)
- [`../CONTROLLED_ONBOARDING_ACQUISITION.md`](../CONTROLLED_ONBOARDING_ACQUISITION.md) — MVP validation workflow
- [`../LAUNCH_PATH.md`](../LAUNCH_PATH.md) — Production onboarding flow

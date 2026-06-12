# Autonomous Acquisition Organism

**Production Truth Version** — Last verified: 2026-06-12  
**Deployed SHA:** `7f2248b999`  
**Source of Truth:** Production only

---

## Mission

The acquisition organism exists to answer ONE question:

> **"Who should we contact first and why?"**

With evidence. Not assumptions. Not synthetic signals. Not fabricated urgency.

The organism identifies organizations most likely to become customers based on **observable federal contract data**, enriches that intelligence from public sources, and ranks prospects by **buying likelihood** — all without sending any outreach.

**Success metric:** Evidence quality and completeness — not clicks, impressions, or vanity metrics.

---

## Rule Zero Integration

**PRODUCTION IS THE ONLY TRUTH.**

- All intelligence originates from production endpoints
- All metrics are verified against live data
- No local data directories are sources of truth
- Every statement must cite evidence with provenance

Before any acquisition decision, the organism must:

1. Query production endpoints
2. Verify `_env.environment == "production"`
3. Cite evidence with source, confidence, and timestamp

---

## Organism Architecture

```
USASpending API (public federal data)
        ↓
  DISCOVERY
  └─ Company names, UEIs, contract values
        ↓
  CUSTOMER INTELLIGENCE RECORD
  └─ EvidencedValue fields (value, source, confidence, state)
        ↓
  ENRICHMENT PIPELINE
  ├─ USASpending Deep (awards, NAICS, agencies)
  ├─ Contact Intelligence (website, email, phone)
  └─ Decision Maker Intelligence (who can buy)
        ↓
  BUYING LIKELIHOOD ENGINE
  └─ Evidence-backed scoring (12 signals, 8 categories)
        ↓
  ICP TIER CLASSIFICATION
  └─ TIER_1 / TIER_2 / TIER_3 / NO_MATCH
        ↓
  ORGANISM ANSWERS 6 QUESTIONS
  ├─ Who is most likely to become a customer?
  ├─ Why?
  ├─ Why now?
  ├─ What evidence supports that?
  ├─ What evidence is still missing?
  └─ What should happen next?
        ↓
  OPERATOR REVIEW (manual outreach only)
```

### Core Modules (`services/acquisition/`)

| Module | Role |
|--------|------|
| `ideal_customer_profile.py` | CustomerIntelligenceRecord, EvidencedValue, ICP tiers |
| `enrichment.py` | Enrichment scoring, recommendation engine |
| `usaspending_deep.py` | USASpending API integration, UEI acquisition |
| `contact_intelligence.py` | Website contact discovery |
| `decision_maker_intelligence.py` | Decision maker identification, title scoring |
| `buying_likelihood.py` | Buying signals, likelihood scoring, explainability |
| `orchestration.py` | Discovery pipeline, telemetry integration |

---

## CustomerIntelligenceRecord

The canonical data structure for all customer intelligence. Every field is an `EvidencedValue` with explicit state tracking.

```python
@dataclass
class CustomerIntelligenceRecord:
    # Identity
    company_name: EvidencedValue
    uei: EvidencedValue
    
    # Classification
    naics: EvidencedValue
    industry: EvidencedValue
    company_size: EvidencedValue
    
    # Contract Intelligence
    contract_count: EvidencedValue
    contract_value: EvidencedValue
    award_recency: EvidencedValue
    agency_mix: EvidencedValue
    
    # Compliance Exposure
    dod_exposure: EvidencedValue
    manufacturing_exposure: EvidencedValue
    aerospace_exposure: EvidencedValue
    cmmc_likelihood: EvidencedValue
    dfars_likelihood: EvidencedValue
    
    # Contactability
    contact_email: EvidencedValue
    contact_name: EvidencedValue
    contact_phone: EvidencedValue
    contact_title: EvidencedValue
    website: EvidencedValue
    
    # Decision Maker Intelligence
    decision_maker_name: EvidencedValue
    decision_maker_title: EvidencedValue
    owner_name: EvidencedValue
    president_name: EvidencedValue
    ceo_name: EvidencedValue
    # ... additional decision maker fields
    
    # Metadata
    record_id: str
    created_utc: str
    updated_utc: str
    source_lead_id: str
```

**Storage:** `data/customer_intelligence/{record_id}.json`

---

## EvidencedValue

Every intelligence field contains explicit evidence tracking:

```python
@dataclass
class EvidencedValue:
    value: Any           # The actual data
    source: str          # Where it came from (e.g., "USASpending Award Detail")
    confidence: float    # How certain we are (0.0-1.0)
    state: SignalState   # KNOWN or UNKNOWN
    observed_utc: str    # When we observed it
```

**Example:**

```json
{
  "contract_value": {
    "value": 4122952,
    "source": "USASpending Award Detail",
    "confidence": 0.98,
    "state": "KNOWN",
    "observed_utc": "2026-06-12T07:00:00Z"
  }
}
```

---

## SignalState

**CRITICAL:** Unknown must never be interpreted as absence.

```python
class SignalState(str, Enum):
    KNOWN = "KNOWN"      # We have evidence
    UNKNOWN = "UNKNOWN"  # We do not yet possess evidence
```

**Rules:**

- `KNOWN` = Evidence exists with source and confidence
- `UNKNOWN` = Evidence not yet collected (NOT "no" or "false")
- Never infer, guess, or fabricate
- Unknown fields must be enriched, not assumed

---

## ICP Tier System

Ideal Customer Profile classification based on observable evidence:

| Tier | Name | Criteria |
|------|------|----------|
| **TIER_1** | Highest Priority | Active DoD contractor + small/medium business + recent awards |
| **TIER_2** | High Priority | Government contractor in manufacturing/aerospace/defense/tech |
| **TIER_3** | Standard Priority | Any federal award recipient |
| **NO_MATCH** | Does Not Match | Insufficient evidence for any tier |

**Current Production Distribution (39 records):**

| Tier | Count |
|------|-------|
| TIER_1 | 0 |
| TIER_2 | 21 |
| TIER_3 | 18 |

---

## Discovery Pipeline

**Source:** USASpending API (public federal data)

```
POST /api/operator/acquisition-intelligence/run
  → Query USASpending autocomplete/award search
  → Extract company names, UEIs, contract data
  → Create CustomerIntelligenceRecord
  → Store with evidence provenance
```

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/operator/acquisition-intelligence` | List discovery results |
| POST | `/api/operator/acquisition-intelligence/run` | Run discovery |

---

## Enrichment Pipeline

Transform company names into actionable intelligence:

### USASpending Deep Enrichment

```
POST /api/operator/customer-intelligence/deep-enrich
  → Acquire UEI from company name
  → Fetch award profile (contract count, value, agencies)
  → Extract NAICS codes and industry indicators
  → Compute compliance exposure (CMMC/DFARS likelihood)
```

**Fields Enriched:**

- `uei`, `contract_count`, `contract_value`
- `award_recency`, `agency_mix`, `dod_exposure`
- `naics`, `manufacturing_exposure`, `aerospace_exposure`
- `cmmc_likelihood`, `dfars_likelihood`

### Enrichment Score (0-100)

Measures how much we know about a company:

| Score | Meaning |
|-------|---------|
| 0-20 | UEI only |
| 21-40 | UEI + awards |
| 41-60 | Awards + NAICS + website |
| 61-80 | Full profile + contact |
| 81-100 | Complete with decision maker |

**Current Production Average:** 50.6%

---

## Contact Intelligence

Discover contact information from public website sources:

```
POST /api/operator/customer-intelligence/contact-enrich
  → Discover company website
  → Find contact/about/leadership pages
  → Extract emails, phones (respecting robots.txt)
  → Store with source URL and confidence
```

**Fields Discovered:**

- `website`, `contact_email`, `contact_phone`
- `contact_name`, `contact_title`
- `contact_source_url`, `leadership_page_url`

**Current Production Metrics:**

| Metric | Count |
|--------|-------|
| Email Known | 1 |
| Phone Known | 3 |
| Contact Ready | 0 |

---

## Decision Maker Intelligence

Identify WHO can buy — not just that a company exists:

```
POST /api/operator/customer-intelligence/decision-maker-enrich
  → Parse leadership/about pages
  → Extract names and titles
  → Score by procurement relevance
  → Identify decision makers
```

### Procurement Relevance Scoring

| Tier | Titles | Score |
|------|--------|-------|
| TIER_1 | President, Owner, CEO, Founder | 100 |
| TIER_2 | Contracts Manager, Compliance Manager, Quality Director | 75 |
| TIER_3 | Office Manager, General Contact | 50 |

**DECISION_MAKER_READY Criteria:**

- `decision_maker_name` = KNOWN
- `decision_maker_title` = KNOWN
- `contact_email` = KNOWN
- `confidence` ≥ 0.70

**Current Production Metrics:**

| Metric | Count |
|--------|-------|
| Decision Maker Entities | 1 |
| Procurement Relevant | 1 |
| Decision Maker Ready | 1 |

---

## Buying Likelihood Intelligence

Evidence-backed scoring to determine which companies are most likely to become customers.

### 12 Buying Signals (8 Categories)

| Category | Signals | Max Points |
|----------|---------|------------|
| Financial | contract_value | 15 |
| Activity | contract_count | 10 |
| Timing | award_recency | 12 |
| Compliance | dod_exposure, cmmc_likelihood, dfars_likelihood | 35 |
| Industry | manufacturing_exposure, aerospace_exposure | 10 |
| Contactability | decision_maker_present, contact_email_present | 20 |
| Discovery | website_present | 3 |
| Quality | intelligence_completeness | 5 |

**Max Possible Score:** 110

### Buying Readiness Tiers

| Tier | Criteria |
|------|----------|
| **BUY_NOW** | Score ≥70% + contract value + DoD + contactable + recent activity |
| **HIGH_POTENTIAL** | Score ≥50% + contract value + (DoD or recent activity) |
| **MEDIUM_POTENTIAL** | Score ≥30% or contract value with 50%+ evidence |
| **LOW_POTENTIAL** | Some evidence but not compelling |
| **INSUFFICIENT_EVIDENCE** | <30% evidence coverage |

**Current Production Distribution:**

| Tier | Count |
|------|-------|
| BUY_NOW | 0 |
| HIGH_POTENTIAL | 14 |
| MEDIUM_POTENTIAL | 7 |
| LOW_POTENTIAL | 18 |
| INSUFFICIENT_EVIDENCE | 0 |

---

## Organism Questions

The organism must answer 6 key questions with evidence:

```
GET /api/operator/customer-intelligence/buying-likelihood
```

**Current Production Answers:**

| Question | Answer |
|----------|--------|
| **Q1:** Which company is most likely to become a customer? | DEFENSE & AEROSPACE MANUFACTURING LLC |
| **Q2:** Why? | DoD contract exposure, $4.1M federal contracts, manufacturing |
| **Q3:** Why now? | Very recent award activity (164 days), high CMMC/DFARS likelihood |
| **Q4:** What evidence supports that? | contract_value, contract_count, award_recency, dod_exposure, cmmc_likelihood |
| **Q5:** What evidence is missing? | (none) |
| **Q6:** What should happen next? | ENRICH_DECISION_MAKER: Identify who can buy |

---

## Safety Rules

### Absolute Prohibitions

- **NO spam** — All outreach is operator-approved only
- **NO auto-send** — `auto_send_enabled = FALSE` always
- **NO fabricated evidence** — Every value requires source
- **NO synthetic urgency** — No BURDEN_CONTEXT injection
- **NO deceptive impersonation**
- **NO scraping** — Public APIs only (USASpending, public websites)

### Evidence Rules

- Every field must have `value`, `source`, `confidence`, `state`
- `UNKNOWN` remains `UNKNOWN` — never infer or guess
- All signals must originate from public data or operator input
- Mock/example domains blocked in production paths

### Operator Workflow

1. Organism identifies HIGH_POTENTIAL prospects with evidence
2. Operator reviews evidence and recommendation
3. Operator manually decides to contact (or not)
4. No automated outreach of any kind

---

## Current Production Metrics

**Last verified:** 2026-06-12T07:39Z

```
ORGANISM STATE
==============
Deployed SHA:           7f2248b999
Total Intelligence:     39 records
Average Completeness:   50.6%

ICP DISTRIBUTION
================
TIER_1:                 0
TIER_2:                 21
TIER_3:                 18

BUYING LIKELIHOOD
=================
BUY_NOW:                0
HIGH_POTENTIAL:         14
MEDIUM_POTENTIAL:       7
LOW_POTENTIAL:          18

CONTACT INTELLIGENCE
====================
Email Known:            1
Phone Known:            3
Decision Maker Ready:   1

SAFETY
======
Auto-Send:              DISABLED
Outreach Sent:          0
Evidence Only:          YES
```

---

## API Reference

### Customer Intelligence

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/operator/customer-intelligence` | List all intelligence records |
| GET | `/api/operator/customer-intelligence/icp` | Get ICP definition |
| GET | `/api/operator/customer-intelligence/cockpit` | Cockpit view |
| GET | `/api/operator/customer-intelligence/{record_id}` | Get single record |

### Enrichment

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/operator/customer-intelligence/deep-enrich` | USASpending deep enrichment |
| POST | `/api/operator/customer-intelligence/contact-enrich` | Contact discovery |
| POST | `/api/operator/customer-intelligence/decision-maker-enrich` | Decision maker discovery |

### Buying Likelihood

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/operator/customer-intelligence/buying-signals` | Signal inventory |
| GET | `/api/operator/customer-intelligence/buying-likelihood` | Top prospects report |
| GET | `/api/operator/customer-intelligence/buying-validation` | Organism validation |

### Reports

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/operator/top-prospects` | Top prospects ranking |
| GET | `/api/operator/customer-intelligence/top-contactable` | Top contactable report |
| GET | `/api/operator/customer-intelligence/top-procurement-relevant` | Top procurement report |

---

## Known Limitations

1. **UEI acquisition** — Autocomplete often returns null; award search is primary
2. **Contact extraction** — Website parsing is naive; many sites block scraping
3. **Decision maker discovery** — Relies on structured leadership pages
4. **BUY_NOW tier** — Currently 0 companies (need decision maker + contact)
5. **Telemetry health** — Currently degraded

---

## Future Roadmap

1. **SAM.gov integration** — When API access available
2. **Enhanced contact discovery** — LinkedIn public profiles (lawful only)
3. **Semantic decision maker extraction** — Better title parsing
4. **Compliance intelligence integration** — Regulatory change triggers
5. **Learning loop** — Outcome tracking for scoring refinement

---

## Related Documents

- [`../AGENTS.md`](../AGENTS.md) — Agent rules and IRON LAW
- [`KYC_CONSTITUTION.md`](./KYC_CONSTITUTION.md) — Binding rules
- [`PRODUCTION_IS_THE_ONLY_TRUTH.md`](./PRODUCTION_IS_THE_ONLY_TRUTH.md) — Environment contract
- [`CENTRAL_MEMORY.md`](./CENTRAL_MEMORY.md) — Memory model
- [`FIRST_SALE_OPERATOR_SOP.md`](./FIRST_SALE_OPERATOR_SOP.md) — Payment workflow

---

## Verification

Run production audit:

```bash
python scripts/prod_organism_full_audit.py
python scripts/prod_buying_verify.py
```

All counts and metrics in this document are verified against production endpoints.

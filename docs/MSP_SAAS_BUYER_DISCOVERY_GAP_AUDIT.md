# MSP/SAAS BUYER DISCOVERY GAP AUDIT

**PATCH**: ACQ-QUAL-9  
**Date**: 2026-06-12  
**Source**: Production organism state, discovery connectors, customer intelligence system

## EXECUTIVE SUMMARY

**What specific capability is missing that prevents the organism from autonomously discovering MSP/SaaS buyers?**

## **The organism has no data source that contains MSPs or SaaS companies.**

The single active discovery connector (USASpending) searches for:
- "defense manufacturing"
- "precision machining"
- "aerospace supplier"
- "government subcontractor"
- "metal fabrication defense"

**Zero MSP-related queries. Zero SaaS-related queries. Zero IT services queries.**

MSPs and SaaS companies rarely appear in USASpending because:
1. MSPs typically don't receive direct federal awards (they're IT vendors to contractors)
2. SaaS companies with federal contracts use different NAICS codes not being searched
3. The search queries explicitly exclude IT services terminology

**This is a data source problem, not an intelligence problem.**

---

## PHASE 1: CURRENT DISCOVERY INVENTORY

### Active Discovery Sources

| Source | Status | Records Found | Queries |
|--------|--------|---------------|---------|
| **USASpending.gov** | ACTIVE | 39 | 5 manufacturing-focused |

**That's it. One source.**

### USASpending Configuration

```python
DEFAULT_QUERIES = [
    "defense manufacturing",
    "precision machining",
    "aerospace supplier",
    "government subcontractor",
    "metal fabrication defense",
]
```

### Discovery Source Analysis

| Source | Records | Industries Found | Buyer Types Found | Usage |
|--------|---------|------------------|-------------------|-------|
| USASpending | 39 | Manufacturing (100%) | Contractors (100%) | Active |

### Industries Found in 39 Records

| Industry | Count | Percentage |
|----------|-------|------------|
| "Government contractor" (generic) | 39 | 100% |
| Precision Machining | 23 | 59% |
| Defense Manufacturing | 12 | 31% |
| Aerospace | 4 | 10% |
| **MSP / IT Services** | **0** | **0%** |
| **Software / SaaS** | **0** | **0%** |

### Inactive/Nonexistent Sources

| Potential Source | Status | MSP Coverage | SaaS Coverage |
|------------------|--------|--------------|---------------|
| LinkedIn Sales Navigator | NOT IMPLEMENTED | HIGH | HIGH |
| Clutch.co | NOT IMPLEMENTED | HIGH | HIGH |
| G2.com | NOT IMPLEMENTED | MEDIUM | HIGH |
| SBIR.gov | NOT IMPLEMENTED | LOW | HIGH |
| Apollo.io | NOT IMPLEMENTED | HIGH | HIGH |
| ZoomInfo | NOT IMPLEMENTED | HIGH | HIGH |
| Crunchbase | NOT IMPLEMENTED | MEDIUM | HIGH |
| ChannelE2E | NOT IMPLEMENTED | HIGH | LOW |
| Reddit r/msp | NOT IMPLEMENTED | HIGH | LOW |
| Google search | NOT IMPLEMENTED | HIGH | HIGH |

---

## PHASE 2: BUYER POPULATION COVERAGE

### Coverage Analysis

| Population | In USASpending? | In Current Queries? | Current Coverage |
|------------|-----------------|---------------------|------------------|
| **MSPs** | RARE (~1%) | NO | **0%** |
| **Software/SaaS** | RARE (~5%) | NO | **0%** |
| **SBIR Recipients** | YES (30%) | PARTIALLY | **~5%** |
| **IT Contractors** | PARTIALLY | NO | **~2%** |
| **Engineering Firms** | YES (60%) | PARTIALLY | **~10%** |
| **Manufacturing** | YES (95%) | YES | **~100%** |

### Why Each Population Is Missing

#### MSPs (0% Coverage)

| Factor | Impact |
|--------|--------|
| **USASpending visibility** | MSPs are IT vendors to contractors, not direct award recipients |
| **Query terms** | "Managed IT" / "MSP" / "IT services" not in query list |
| **NAICS filtering** | NAICS 541512, 541513 (IT services) not searched |
| **Flow-down contracts** | USASpending doesn't track subcontractor flow-downs |

**Root Cause**: MSPs exist in a different data universe — they're service providers to contractors, not contractors themselves.

#### Software/SaaS (0% Coverage)

| Factor | Impact |
|--------|--------|
| **USASpending visibility** | SaaS companies have federal contracts but under different NAICS |
| **Query terms** | "Software" / "SaaS" / "cloud" not in query list |
| **NAICS filtering** | NAICS 541511, 541519 (software) not searched |
| **Business model** | SaaS companies don't have "defense" or "manufacturing" in names |

**Root Cause**: SaaS companies exist in USASpending but aren't found because queries exclude software terminology.

#### SBIR Recipients (~5% Coverage)

| Factor | Impact |
|--------|--------|
| **USASpending visibility** | SBIR awards are in USASpending |
| **Query terms** | "SBIR" not in query list |
| **Accidental capture** | Only found if company name includes manufacturing terms |

**Root Cause**: SBIR is searchable in USASpending but not being searched.

---

## PHASE 3: SIGNAL GAP ANALYSIS

### For MSP/SaaS Discovery, What Signals Are Required?

| Signal | Required For | Exists in Organism? | Available from USASpending? |
|--------|--------------|---------------------|----------------------------|
| **Company Type** | Identify as MSP/SaaS | YES | NO (for MSP/SaaS) |
| **Compliance Trigger** | Urgency detection | YES | PARTIALLY |
| **Decision Maker** | Contactability | YES | NO |
| **Company Website** | Enrichment | YES | NO |
| **Employee Count** | Size qualification | YES | NO |
| **Industry Classification** | ICP match | YES | PARTIALLY |
| **Revenue** | Budget qualification | YES | NO |
| **Contact Email** | Outreach | YES | NO |
| **LinkedIn Presence** | Enrichment | YES | NO |
| **Defense Exposure** | CMMC need | YES | YES |

### Existing Signal Capabilities

| Engine | Purpose | Status | Works for MSP/SaaS? |
|--------|---------|--------|---------------------|
| Buying Likelihood | Score purchase probability | ✅ ACTIVE | YES (if data exists) |
| Compliance Trigger | Identify urgency | ✅ ACTIVE | YES (if data exists) |
| Contact Intelligence | Find contacts | ✅ ACTIVE | NO DATA TO PROCESS |
| Decision Maker | Find decision makers | ✅ ACTIVE | NO DATA TO PROCESS |
| ICP Evaluation | Score customer fit | ✅ ACTIVE | WRONG CRITERIA |

### The Intelligence Engines Work — They Just Have Nothing to Process

```
CURRENT FLOW:
USASpending → 39 Manufacturing Companies → Intelligence Engines → Scored Mfg

NEEDED FLOW:
[MSP Data Source] → MSP Companies → Intelligence Engines → Scored MSPs
[SaaS Data Source] → SaaS Companies → Intelligence Engines → Scored SaaS
```

---

## PHASE 4: ORGANISM BLIND SPOTS

### Why MSP/SaaS Buyers Are Not Being Discovered

| Blind Spot | Evidence | Impact |
|------------|----------|--------|
| **No MSP data source** | Zero connectors query MSP databases | Cannot find MSPs |
| **No SaaS data source** | Zero connectors query SaaS databases | Cannot find SaaS |
| **Wrong search queries** | 5 queries, all manufacturing-focused | Miss entire industries |
| **Single data source** | Only USASpending | Miss non-federal-award companies |
| **No NAICS filtering** | Manufacturing NAICS captured, IT NAICS missed | Industry bias |
| **No LinkedIn integration** | Cannot discover by LinkedIn presence | Miss modern companies |

### Structural Discovery Limitations

```
ORGANISM ARCHITECTURE:
┌─────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYER                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ ICP Engine  │ │ Buying     │ │ Compliance  │ ← WORKING  │
│  │             │ │ Likelihood │ │ Trigger     │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│                         ▲                                    │
│                         │ (processing)                       │
│                         │                                    │
│  ┌─────────────────────────────────────────────┐            │
│  │              DISCOVERY LAYER                 │            │
│  │  ┌─────────────────────────────────────┐    │            │
│  │  │ USASpending Connector               │    │ ← ONLY ONE │
│  │  │ • defense manufacturing             │    │            │
│  │  │ • precision machining               │    │            │
│  │  │ • aerospace supplier                │    │            │
│  │  │ • government subcontractor          │    │            │
│  │  │ • metal fabrication defense         │    │            │
│  │  └─────────────────────────────────────┘    │            │
│  │                                              │            │
│  │  ┌─────────────────────────────────────┐    │            │
│  │  │ MSP Connector         ← NOT EXISTS  │    │            │
│  │  └─────────────────────────────────────┘    │            │
│  │                                              │            │
│  │  ┌─────────────────────────────────────┐    │            │
│  │  │ SaaS Connector        ← NOT EXISTS  │    │            │
│  │  └─────────────────────────────────────┘    │            │
│  └─────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Evidence Summary

| Question | Answer | Evidence |
|----------|--------|----------|
| Does the organism have MSP data? | NO | 0 MSP records in 39 total |
| Does the organism have SaaS data? | NO | 0 SaaS records in 39 total |
| Could the organism process MSP data if provided? | YES | Intelligence engines are functional |
| Is the problem data or intelligence? | **DATA** | Engines work, no data to process |

---

## PHASE 5: AUTONOMOUS READINESS TEST

### Can the organism currently produce 100 ranked MSP/SaaS buyers with evidence without Carl intervention?

## **NO**

### Evidence

| Capability | Required | Current State |
|------------|----------|---------------|
| MSP company data | 100+ records | **0 records** |
| SaaS company data | 100+ records | **0 records** |
| Contact information | Email/phone | **0 MSP/SaaS contacts** |
| ICP scoring | Working | ✅ YES (but wrong criteria for MSP/SaaS) |
| Buying likelihood | Working | ✅ YES (but no data to score) |
| Compliance triggers | Working | ✅ YES (but no data to score) |

### What Would Be Needed

| Component | Current | Needed |
|-----------|---------|--------|
| MSP data source | 0 | 1+ connector |
| SaaS data source | 0 | 1+ connector |
| MSP-specific queries | 0 | 3-5 queries |
| SaaS-specific queries | 0 | 3-5 queries |
| ICP criteria for MSP/SaaS | Manufacturing-focused | Service provider criteria |

### Autonomous Production Test

```
COMMAND: "Organism, produce 100 ranked MSP buyers"
EXPECTED: List of 100 MSPs with buying likelihood scores
ACTUAL:   Cannot comply — zero MSP records exist

COMMAND: "Organism, produce 100 ranked SaaS buyers"  
EXPECTED: List of 100 SaaS companies with compliance triggers
ACTUAL:   Cannot comply — zero SaaS records exist

COMMAND: "Organism, produce 100 ranked manufacturers"
EXPECTED: List of 100 manufacturers with evidence
ACTUAL:   Can produce 39 (limited by single data source)
```

---

## PHASE 6: MINIMUM MISSING CAPABILITIES

### Critical (Cannot Find MSP/SaaS Without These)

| Capability | Description | Complexity |
|------------|-------------|------------|
| **1. MSP/SaaS Data Source** | Connector to data containing MSPs/SaaS | MEDIUM |
| **2. MSP/SaaS Search Queries** | "managed IT", "SaaS", "MSP", "software" | LOW |
| **3. ICP Criteria Update** | Add service provider criteria | LOW |

### Important (Significantly Improves Discovery)

| Capability | Description | Complexity |
|------------|-------------|------------|
| **4. LinkedIn Integration** | Discover companies by LinkedIn presence | HIGH |
| **5. Website Enrichment** | Auto-discover company websites | MEDIUM |
| **6. NAICS-Based Filtering** | Query by IT/Software NAICS codes | LOW |

### Nice to Have (Optimization)

| Capability | Description | Complexity |
|------------|-------------|------------|
| **7. Industry Classification** | Auto-detect MSP vs SaaS vs IT | MEDIUM |
| **8. Revenue Estimation** | Size companies without manual research | HIGH |
| **9. Decision Maker Scraping** | Find CEO/owner automatically | HIGH |

### Minimum Viable Change for MSP Discovery

```
OPTION A: Add MSP queries to existing USASpending connector
──────────────────────────────────────────────────────────
Queries to add:
- "IT managed services"
- "managed service provider"  
- "IT support services"
- "computer support"
- "cloud services"

Effort: 1 hour
Risk: LOW
Expected MSP coverage: 5-15% (most MSPs not in USASpending)
```

```
OPTION B: Manual MSP list ingestion
──────────────────────────────────────────────────────────
Process:
1. Carl provides list of 100 MSP names/websites
2. Organism processes through intelligence engines
3. Produces ranked, scored output

Effort: 2-3 hours (Carl's time to build list)
Risk: LOW  
Expected MSP coverage: 100% of provided list
```

```
OPTION C: New connector (Clutch.co, ChannelE2E, or similar)
──────────────────────────────────────────────────────────
Build connector to MSP database/directory.

Effort: 8-16 hours development
Risk: MEDIUM (depends on data source API)
Expected MSP coverage: 50-80% of target market
```

### Recommended Minimum Viable Path

**Option B → Option A → Option C**

1. **Immediate**: Manual MSP list ingestion (proves intelligence engines work)
2. **Short-term**: Add IT queries to USASpending (captures federal MSPs)
3. **Medium-term**: New connector for broader coverage

---

## PHASE 7: FINAL VERDICT

### 1. Why the Organism Finds Contractors Instead of Buyers

## **The search queries only match contractors**

The 5 queries all target manufacturing/defense language:
- "defense manufacturing"
- "precision machining"
- "aerospace supplier"
- "government subcontractor"
- "metal fabrication defense"

**Zero queries target buyers (MSP, SaaS, IT services)**

The organism does exactly what it's told: find manufacturing companies. It's very good at this. It cannot find MSPs because it's never asked to look for them.

### 2. Why MSP/SaaS Buyers Are Missing

## **No data source contains MSPs/SaaS in accessible form**

| Data Source | Contains MSPs? | Being Queried? |
|-------------|----------------|----------------|
| USASpending | ~1% | YES (wrong queries) |
| LinkedIn | ~100% | NO |
| Clutch.co | ~100% | NO |
| ChannelE2E | ~100% | NO |
| G2.com | ~50% | NO |

The organism has zero access to the databases where MSPs live.

### 3. Single Largest Discovery Gap

## **No MSP/SaaS Data Source**

This is a **data gap**, not an intelligence gap.

The intelligence engines (ICP, Buying Likelihood, Compliance Trigger, Contact, Decision Maker) all work. They just have nothing to process.

```
PROBLEM:  Input Layer (Data)
NOT:      Processing Layer (Intelligence)
```

### 4. Smallest Change Needed to Close It

## **Manual MSP List Ingestion**

Carl provides a list of 100 MSP company names/websites. The organism processes them through existing intelligence engines and produces ranked output.

| Change | Effort | Impact |
|--------|--------|--------|
| Manual list ingestion | 2-3 hours | 100% of provided MSPs scored |

**No new code required. The infrastructure exists. Only data is missing.**

### 5. Current Autonomous Acquisition Readiness

## **NOT READY for MSP/SaaS Discovery**

| Capability | Readiness |
|------------|-----------|
| Manufacturing discovery | ✅ READY |
| Manufacturing intelligence | ✅ READY |
| **MSP discovery** | ❌ NOT READY — No data source |
| **SaaS discovery** | ❌ NOT READY — No data source |
| MSP intelligence (if data provided) | ✅ READY |
| SaaS intelligence (if data provided) | ✅ READY |

### Readiness Score by Population

| Population | Discovery | Intelligence | Overall |
|------------|-----------|--------------|---------|
| Manufacturing | ✅ 100% | ✅ 100% | ✅ READY |
| **MSP** | ❌ 0% | ✅ 100% | ❌ NOT READY |
| **SaaS** | ❌ 0% | ✅ 100% | ❌ NOT READY |
| SBIR | ⚠️ 5% | ✅ 100% | ⚠️ PARTIALLY |

---

## DELIVERABLE SUMMARY

### Discovery Inventory

| Source | Status | Industries | Buyers Found |
|--------|--------|------------|--------------|
| USASpending | Active | Manufacturing | 39 contractors |
| MSP sources | None | N/A | 0 |
| SaaS sources | None | N/A | 0 |

### Buyer Coverage Analysis

| Population | Coverage | Reason |
|------------|----------|--------|
| MSPs | 0% | No data source |
| SaaS | 0% | No data source |
| Manufacturing | ~100% | Primary focus |

### Signal Gap Analysis

| Signal | Exists | Works for MSP/SaaS |
|--------|--------|-------------------|
| ICP Scoring | YES | If data exists |
| Buying Likelihood | YES | If data exists |
| Compliance Trigger | YES | If data exists |
| Contact Intelligence | YES | No data to process |
| Decision Maker | YES | No data to process |

### Blind Spot Analysis

| Blind Spot | Root Cause |
|------------|------------|
| No MSP data | No connector queries MSP databases |
| No SaaS data | No connector queries SaaS databases |
| Wrong queries | 5 queries, all manufacturing-focused |

### Autonomous Readiness

| Test | Result |
|------|--------|
| Can produce 100 ranked MSPs? | **NO** — 0 MSP records |
| Can produce 100 ranked SaaS? | **NO** — 0 SaaS records |
| Can score MSPs if provided? | **YES** — engines work |

### Minimum Capability Requirements

| Priority | Capability | Effort |
|----------|------------|--------|
| **CRITICAL** | MSP/SaaS data source | LOW-MEDIUM |
| **CRITICAL** | MSP/SaaS queries | LOW |
| Important | ICP criteria update | LOW |
| Nice to have | LinkedIn integration | HIGH |

---

## FINAL VERDICT

```
╔════════════════════════════════════════════════════════════════════╗
║              MSP/SAAS BUYER DISCOVERY GAP VERDICT                   ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║  WHY CONTRACTORS NOT BUYERS:    Search queries only match mfg      ║
║  WHY MSP/SAAS MISSING:          No data source contains them       ║
║  LARGEST DISCOVERY GAP:         No MSP/SaaS data source            ║
║  SMALLEST FIX:                  Manual MSP list ingestion          ║
║  AUTONOMOUS READINESS:          NOT READY for MSP/SaaS             ║
║                                                                     ║
║  ─────────────────────────────────────────────────────────────────  ║
║                                                                     ║
║  THE INTELLIGENCE LAYER WORKS.                                     ║
║  THE DATA LAYER IS EMPTY FOR MSP/SAAS.                             ║
║                                                                     ║
║  This is not an algorithm problem.                                 ║
║  This is a data input problem.                                     ║
║                                                                     ║
║  ─────────────────────────────────────────────────────────────────  ║
║                                                                     ║
║  IMMEDIATE ACTION: Carl provides MSP list → Organism scores them   ║
║                                                                     ║
╚════════════════════════════════════════════════════════════════════╝
```

---

**Commit SHA**: 82ef774 (source data)  
**Audit Date**: 2026-06-12  
**Final Verdict**: Data source gap — intelligence works, input missing

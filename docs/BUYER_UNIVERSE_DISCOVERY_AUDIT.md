# BUYER UNIVERSE DISCOVERY AUDIT

**PATCH**: ACQ-QUAL-3  
**Date**: 2026-06-12  
**Source**: Production Discovery Configuration + 39 CustomerIntelligenceRecords

## EXECUTIVE SUMMARY

The organism searches for **5 query terms** in one data source. This produces a narrow, homogeneous pool where 59% of companies have "precision machining" in their name.

The total addressable market for CMMC compliance services includes tens of thousands of contractors across dozens of industries. We are searching **0.02%** of the available universe.

---

## PHASE 1: CURRENT DISCOVERY UNIVERSE

### Data Source

| Source | Type | API |
|--------|------|-----|
| USASpending | Federal contracts | Public API |

**Single source. No alternatives.**

### Search Queries (Exact)

```python
DEFAULT_QUERIES = [
    "defense manufacturing",
    "precision machining",
    "aerospace supplier",
    "government subcontractor",
    "metal fabrication defense",
]
```

**5 queries. All manufacturing/aerospace focused.**

### Company Name Patterns (n=39)

| Pattern | Count | % |
|---------|-------|---|
| "precision machining" | 23 | 59% |
| "defense" | 12 | 31% |
| "aerospace" | 4 | 10% |
| Other | 0 | 0% |

### Industries Represented

| Industry | Count | % |
|----------|-------|---|
| "Government contractor" (generic) | 39 | 100% |

**No industry differentiation. All classified the same.**

### NAICS Codes

| NAICS | Count |
|-------|-------|
| (none recorded) | 39 |

**No NAICS-based discovery or filtering.**

---

## PHASE 2: INDUSTRIES CURRENTLY ABSENT

### Not Searched — High CMMC Likelihood

| Industry | Why CMMC Relevant | Currently Searched |
|----------|-------------------|-------------------|
| **IT Services / MSPs** | Handle CUI for defense clients | NO |
| **Software Developers** | Defense software, SBIR recipients | NO |
| **Cybersecurity Firms** | Defense subcontractors | NO |
| **Cloud Providers** | FedRAMP, DoD cloud | NO |
| **Engineering Services** | Defense engineering contracts | NO |
| **Electronics Manufacturing** | Components, ITAR items | NO |
| **Research Organizations** | SBIR, STTR, defense R&D | NO |
| **Defense Subcontractors** | Flow-down requirements | Partially |
| **Logistics Providers** | DoD supply chain | NO |
| **Communications Equipment** | Military comms | NO |
| **Medical Device Manufacturers** | DHA, VA contracts | NO |
| **Construction Contractors** | DoD facilities, SCIF builders | NO |
| **Training Providers** | DoD training contracts | NO |
| **Professional Services** | Federal consultants | NO |
| **Data Analytics Firms** | Defense intelligence work | NO |

### Not Searched — High Buyer Likelihood

| Industry | Why Good Buyers | Currently Searched |
|----------|-----------------|-------------------|
| **Small MSPs (10-50 employees)** | No internal compliance staff | NO |
| **SaaS Companies with DoD clients** | Need compliance fast | NO |
| **SBIR Recipients** | New to compliance | NO |
| **First-time Prime Winners** | Compliance now mandatory | NO |
| **Companies Recently Flow-Downed** | Compliance now required | NO |
| **Companies with NIST 800-171 Gaps** | Need help NOW | NO |

---

## PHASE 3: INDUSTRY COMPLIANCE LIKELIHOOD ESTIMATES

### Manufacturing (Current Focus)

| Industry | CMMC Likelihood | DFARS Likelihood | Buying Help Likelihood | Reachability |
|----------|-----------------|------------------|----------------------|--------------|
| Precision Machining | 90% | 85% | 50% | LOW |
| Aerospace Manufacturing | 95% | 90% | 40% | LOW |
| Defense Manufacturing | 95% | 90% | 30% | LOW |
| Metal Fabrication | 80% | 75% | 60% | LOW |

**Problem**: High compliance need but LOW buying likelihood (often have internal resources) and LOW reachability (no websites, no contacts).

### IT/Technology (Not Searched)

| Industry | CMMC Likelihood | DFARS Likelihood | Buying Help Likelihood | Reachability |
|----------|-----------------|------------------|----------------------|--------------|
| IT Managed Services (MSPs) | 80% | 75% | **90%** | **HIGH** |
| Software Development | 85% | 80% | **85%** | **HIGH** |
| Cybersecurity Services | 95% | 90% | 60% | **HIGH** |
| Cloud/SaaS Providers | 90% | 85% | **80%** | **HIGH** |
| Data Analytics | 80% | 75% | **85%** | **HIGH** |

**Opportunity**: High compliance need, HIGH buying likelihood, HIGH reachability (tech companies have websites, LinkedIn, etc.)

### Professional Services (Not Searched)

| Industry | CMMC Likelihood | DFARS Likelihood | Buying Help Likelihood | Reachability |
|----------|-----------------|------------------|----------------------|--------------|
| Engineering Services | 85% | 80% | 70% | **HIGH** |
| Federal Consultants | 90% | 85% | **80%** | **HIGH** |
| Research Orgs / SBIR | 80% | 75% | **90%** | **HIGH** |
| Training Providers | 70% | 65% | **85%** | **HIGH** |

### Comparison Summary

| Current Universe | Missing Universe |
|------------------|------------------|
| CMMC Need: HIGH | CMMC Need: HIGH |
| Buying Help: LOW (30-60%) | Buying Help: HIGH (80-90%) |
| Reachability: LOW | Reachability: HIGH |

---

## PHASE 4: IDEAL BUYER UNIVERSE DEFINITION

### Not Ideal Contractor. Ideal BUYER.

The ideal buyer universe contains companies that:

```
1. NEED COMPLIANCE
   - DoD contractor (prime or sub)
   - Handles CUI
   - DFARS 252.204-7012 applies
   - CMMC required for contracts

2. WILL BUY OUTSIDE HELP
   - Small (10-200 employees)
   - No dedicated compliance staff
   - Technical staff, not compliance experts
   - Growing (adding contracts = adding burden)

3. CAN BE REACHED
   - Has website
   - Has LinkedIn presence
   - Decision maker discoverable
   - Email/phone obtainable

4. HAS URGENCY
   - Active RFP requiring CMMC
   - Prime contractor pressure
   - Upcoming audit
   - Recent contract win with compliance requirements
```

### Ideal Industry Verticals (Ranked)

| Rank | Industry | Why Ideal |
|------|----------|-----------|
| 1 | **IT Managed Services (MSPs)** | Understands tech compliance, lacks CMMC expertise, easy to reach |
| 2 | **Software/SaaS Companies** | Tech-savvy but compliance-naive, time-constrained |
| 3 | **SBIR/STTR Recipients** | New to federal, no compliance history, need guidance |
| 4 | **Small Engineering Firms** | High compliance exposure, limited staff |
| 5 | **Federal IT Consultants** | DoD work, understands process, will buy to offload |
| 6 | **Electronics Manufacturers** | ITAR + CMMC exposure, smaller players need help |
| 7 | **Data Analytics Firms** | CUI exposure, rapid growth, compliance backlog |
| 8 | **Medical Device for DoD** | DHA/VA work, compliance complexity |
| 9 | **Defense Logistics** | Supply chain requirements, flow-down pressure |
| 10 | **Small Cybersecurity Firms** | Ironic but true — cyber firms often lack compliance |

---

## PHASE 5: TOTAL ADDRESSABLE PROSPECT POOL ESTIMATE

### Current State

| Metric | Value |
|--------|-------|
| Companies in system | 39 |
| Queries used | 5 |
| Data sources | 1 |
| Industries covered | 1 (manufacturing/aerospace) |

### Market Reality (DoD Contractor Universe)

| Category | Estimated Companies | Source |
|----------|---------------------|--------|
| DoD Prime Contractors | 25,000+ | DoD OSBP |
| DoD Subcontractors | 100,000+ | Industry estimates |
| SBIR/STTR Recipients | 15,000+ | SBA data |
| FedRAMP Seeking | 5,000+ | Industry estimates |
| **Total CMMC-Relevant** | **150,000+** | Conservative |

### By Industry Vertical

| Industry | Est. Contractors | CMMC Relevant | Buyer Likely |
|----------|------------------|---------------|--------------|
| Manufacturing | 20,000 | 15,000 | 5,000 |
| IT Services / MSPs | 30,000 | 20,000 | **15,000** |
| Software/SaaS | 15,000 | 10,000 | **8,000** |
| Engineering | 12,000 | 8,000 | 5,000 |
| Professional Services | 25,000 | 15,000 | **10,000** |
| Research / SBIR | 10,000 | 8,000 | **7,000** |
| Electronics | 8,000 | 6,000 | 4,000 |
| Logistics | 10,000 | 5,000 | 3,000 |
| Other | 20,000 | 10,000 | 5,000 |
| **Total** | **150,000** | **97,000** | **62,000** |

### Coverage Calculation

| Metric | Value |
|--------|-------|
| Current prospects | 39 |
| Estimated market | 150,000+ |
| **Coverage** | **0.026%** |
| Ideal discovery target | 10,000+ |
| Gap | 9,961+ prospects |

---

## PHASE 6: DISCOVERY SCOPE VERDICT

### Current Discovery Is:

## **TOO NARROW**

### Evidence

| Problem | Evidence |
|---------|----------|
| Single data source | Only USASpending |
| Limited queries | Only 5 search terms |
| Single industry | 100% manufacturing/aerospace |
| Keyword matching | 59% have "precision machining" in name |
| No industry expansion | IT, software, MSPs completely absent |
| Homogeneous results | All prospects look identical |

### What "Appropriate" Would Look Like

| Dimension | Current | Appropriate |
|-----------|---------|-------------|
| Data sources | 1 | 3-5 (USASpending, SAM.gov, SBIR, LinkedIn, Industry lists) |
| Search queries | 5 | 50+ across industries |
| Industries | 1 | 10+ |
| Company diversity | 0% | 20%+ industry variation |
| Prospect count | 39 | 1,000+ |

---

## PHASE 7: FINAL VERDICT

### The Organism Has:

## **ALL THREE PROBLEMS**

### 1. Contractor Discovery Problem ❌

The organism finds contractors, but only in one narrow industry.

| Metric | Finding |
|--------|---------|
| Manufacturing/Aerospace | Found |
| IT Services | NOT FOUND |
| Software | NOT FOUND |
| MSPs | NOT FOUND |
| SBIR Recipients | NOT FOUND |
| Engineering | NOT FOUND |

### 2. Buyer Discovery Problem ❌

The organism does not prioritize reachability or buying likelihood.

| Metric | Finding |
|--------|---------|
| High-value contractors found | YES |
| Contactable companies found | NO (2.6%) |
| Buyer-likely companies found | NO |
| Decision makers found | NO (2.6%) |

### 3. Market Coverage Problem ❌

The organism searches 0.026% of the market.

| Metric | Finding |
|--------|---------|
| Total market | 150,000+ |
| Companies found | 39 |
| Coverage | 0.026% |
| Industries covered | 1 of 10+ |

---

## DELIVERABLE SUMMARY

### Current Universe

| Attribute | Value |
|-----------|-------|
| Source | USASpending only |
| Queries | 5 ("defense manufacturing", "precision machining", etc.) |
| Companies | 39 |
| Industries | Manufacturing/Aerospace only |
| Diversity | 0% (all same profile) |

### Missing Universes

| Universe | Est. Size | Buyer Quality |
|----------|-----------|---------------|
| IT Services / MSPs | 20,000 | **HIGHEST** |
| Software / SaaS | 10,000 | **HIGH** |
| SBIR Recipients | 8,000 | **HIGH** |
| Engineering Services | 8,000 | MEDIUM |
| Federal Consultants | 15,000 | **HIGH** |
| Electronics | 6,000 | MEDIUM |
| Research Orgs | 8,000 | HIGH |

### Estimated Prospect Counts

| Metric | Count |
|--------|-------|
| Current prospects | 39 |
| Estimated market | 150,000+ |
| High-quality buyers | 62,000+ |
| Current coverage | 0.026% |

### Highest Value Buyer Populations

| Rank | Population | Why |
|------|------------|-----|
| 1 | **MSPs / IT Services** | High reachability, high buy likelihood, understands tech |
| 2 | **Software / SaaS** | Tech-native, compliance-naive, time-constrained |
| 3 | **SBIR Recipients** | New to federal, need hand-holding |
| 4 | **Small Engineering** | High exposure, limited staff |
| 5 | **Federal Consultants** | Understand process, will outsource |

### Market Coverage Verdict

| Question | Answer |
|----------|--------|
| Discovery scope | **TOO NARROW** |
| Industry coverage | **SINGLE INDUSTRY** |
| Source diversity | **SINGLE SOURCE** |
| Query diversity | **5 SIMILAR QUERIES** |
| Overall | **SEVERE UNDER-COVERAGE** |

### Root Cause Summary

```
CONTRACTOR DISCOVERY:   NARROW (1 industry)
BUYER DISCOVERY:        ABSENT (0% buyer signals)
MARKET COVERAGE:        0.026%

COMBINED VERDICT:       ALL THREE PROBLEMS
```

---

**Commit SHA**: c3b299e (source data)  
**Audit Date**: 2026-06-12  
**Final Verdict**: Organism has **CONTRACTOR + BUYER + COVERAGE** problems

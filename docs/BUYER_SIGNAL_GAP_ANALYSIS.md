# BUYER SIGNAL GAP ANALYSIS

**PATCH**: ACQ-QUAL-2  
**Date**: 2026-06-12  
**Source**: 39 Production CustomerIntelligenceRecords  

## EXECUTIVE SUMMARY

The organism identifies **CONTRACTORS**, not **BUYERS**.

All 39 prospects have DOD exposure and manufacturing keywords. But only 1 prospect can actually be contacted. The signals that determine whether Carl approves a company (contactability, decision maker, website) are **not weighted** in the current scoring model.

**Critical Finding**: Contract value has **INVERSE** correlation with approval. The $60M companies are rejected; the $892k company is approved — because the small company can be contacted.

---

## PHASE 1: APPROVED vs REJECTED COMPARISON

### The Approved Company

| Field | Value |
|-------|-------|
| Company | ADVANCED PRECISION MACHINING, INC. |
| Contract Value | $892,000 |
| Contract Count | 21 |
| Award Recency | 2023-09-01 |
| DOD Exposure | True |
| CMMC Likelihood | 90% |
| DFARS Likelihood | 85% |
| Manufacturing Exposure | True |
| Aerospace Exposure | False |
| Website | **True** |
| Contactability | **85** |
| Decision Maker Present | **True** |
| Intelligence Completeness | **83** |

### Rejected Companies (n=28)

| Field | Average | Notes |
|-------|---------|-------|
| Contract Value | $8,766,000 | **10x higher than approved** |
| Contract Count | 5.5 | Lower volume |
| Award Recency (2024+) | 14% | Mostly stale |
| DOD Exposure | 100% | No differentiation |
| CMMC Likelihood | 28% | Low enrichment |
| DFARS Likelihood | 28% | Low enrichment |
| Manufacturing Exposure | 36% | Incomplete |
| Website | **7%** | Cannot research |
| Contactability | **4.6** | Unreachable |
| Decision Maker Present | **0%** | Cannot contact |
| Intelligence Completeness | **41.5** | Incomplete |

### Unsure Companies (n=10)

| Field | Average | Notes |
|-------|---------|-------|
| Contract Value | $20,100,000 | Very high |
| Contract Count | 207.3 | High volume |
| Award Recency (2024+) | 80% | Recent |
| CMMC Likelihood | 86% | High |
| Manufacturing Exposure | 100% | All manufacturing |
| Website | **30%** | Some present |
| Contactability | **14.5** | Low |
| Decision Maker Present | **0%** | None |
| Intelligence Completeness | **72.8** | Good |

---

## PHASE 2: SIGNAL CORRELATION WITH APPROVAL

### HIGH CORRELATION — Determines Approval

| Signal | Approved | Rejected | Unsure | Correlation |
|--------|----------|----------|--------|-------------|
| **Decision Maker Present** | YES | 0% | 0% | **HIGHEST** |
| **Contactability Score** | 85 | 4.6 | 14.5 | **HIGHEST** |
| **Website Present** | YES | 7% | 30% | **HIGH** |
| **Intelligence Completeness** | 83 | 41.5 | 72.8 | **HIGH** |

### MEDIUM CORRELATION — Contributes to Quality

| Signal | Approved | Rejected | Unsure | Correlation |
|--------|----------|----------|--------|-------------|
| Award Recency | 2023 | Mostly pre-2020 | Mostly 2024+ | MEDIUM |
| Contract Count | 21 | 5.5 | 207.3 | MEDIUM |

### LOW CORRELATION — Weak Predictors

| Signal | Approved | Rejected | Unsure | Correlation |
|--------|----------|----------|--------|-------------|
| CMMC Likelihood | 90% | 28% | 86% | LOW |
| DFARS Likelihood | 85% | 28% | — | LOW |

### NO CORRELATION — Does Not Predict Approval

| Signal | Approved | Rejected | Unsure | Correlation |
|--------|----------|----------|--------|-------------|
| **Contract Value** | $892k | $8.8M | $20.1M | **INVERSE** |
| DOD Exposure | 100% | 100% | 100% | NONE |
| Manufacturing Exposure | Yes | 36% | 100% | NONE |
| Aerospace Exposure | No | 0% | 10% | NONE |

---

## PHASE 3: FIELDS ADDING NO PREDICTIVE VALUE

### Currently Used — Zero Value

| Field | Why Useless |
|-------|-------------|
| **DOD Exposure** | All 39 companies have DOD=True. Provides no differentiation. |
| **Manufacturing Keyword** | 19 of 21 TIER_2 companies have "precision machining" in name. Keyword matching, not analysis. |
| **Defense Keyword** | 15 of 21 TIER_2 companies have "defense" in name. Same problem. |
| **Generic CMMC Likelihood** | Derived from DOD exposure. If DOD=True → CMMC=High. No independent signal. |
| **Generic DFARS Likelihood** | Same as CMMC. Derived, not discovered. |
| **Aerospace Exposure** | Most companies are False. When True, doesn't change approval. |

### The Problem

The organism's scoring model uses:
- Industry keywords → All companies match
- DOD exposure → All companies match
- CMMC likelihood → All match if DOD=True
- DFARS likelihood → All match if DOD=True

**Result**: All companies look identical. Cannot differentiate.

---

## PHASE 4: MISSING FIELDS — TOP 10 FOR APPROVAL QUALITY

| Rank | Missing Field | Impact | Why Critical |
|------|---------------|--------|--------------|
| 1 | **Decision Maker Identity** | CRITICAL | Cannot contact without knowing WHO to contact |
| 2 | **Verified Contact Method** | CRITICAL | Email/phone that works |
| 3 | **Website Presence** | HIGH | Cannot research company without website |
| 4 | **Award Recency Threshold** | HIGH | Stale awards indicate inactive contractor |
| 5 | **Active Compliance Deadline** | HIGH | Companies with deadlines have urgency |
| 6 | **Prime Contractor Status** | HIGH | Primes face more compliance pressure |
| 7 | **Active RFP/Bid Participation** | HIGH | Currently bidding = needs compliance NOW |
| 8 | **Company Size / Employee Count** | MEDIUM | Too small = can't afford. Too large = already compliant |
| 9 | **Contract Growth Trend** | MEDIUM | Growing contractors have more pressure |
| 10 | **Previous Compliance Actions** | MEDIUM | History of compliance attempts |

---

## PHASE 5: WHAT WOULD CHANGE REJECT → APPROVE

### Tier 3 Rejects (18 companies with $0 data)

| Current State | Required Evidence |
|---------------|-------------------|
| $0 contract value | Verified recent contract > $100k |
| No award recency | Award date within 3 years |
| No website | Working company website |
| 0% CMMC likelihood | Evidence of CUI handling or flow-down |
| 0 contactability | Working email or phone |
| No decision maker | Named contact with authority |

**Verdict**: These are not prospects. They are search results that matched a keyword. Would require complete re-discovery.

### Stale Award Rejects (4 companies with 2017-2019 awards)

| Company | Required Evidence |
|---------|-------------------|
| KHEM PRECISION MACHINING | New award in 2024+ OR confirmation still active contractor |
| MINUTEMEN PRECISION MACHINING | Same |
| GLOBAL AEROSPACE AND DEFENSE | Same |
| TSC PRECISION MACHINING INC | Same |

**Verdict**: These may be defunct or exited federal contracting. Require fresh verification.

### Low Value Rejects (5 companies with <$10k)

| Company | Required Evidence |
|---------|-------------------|
| A PRECISION MACHINING CORP ($3k) | Larger active contract |
| CHEROKEE DEFENSE MANUFACTURING ($5k) | Larger active contract |
| TSC PRECISION MACHINING ($5k) | Same |
| GLOBAL AEROSPACE ($7k) | Same |
| MINUTEMEN ($19k) | Same |

**Verdict**: $3k-$19k contractors unlikely to afford compliance services. Require evidence of growth.

### Unreachable High-Value Companies (UNSURE)

| Company | Value | Required Evidence |
|---------|-------|-------------------|
| YORK PRECISION MACHINING | $60.7M | Decision maker identity + contact method |
| CHOCTAW DEFENSE MANUFACTURING | $63.5M | Same |
| DEFENSE MANUFACTURING | $59.5M | Same |
| DEFENSE SUPPLY & MANUFACTURING | $4.0M | Same |
| DEFENSE & AEROSPACE MANUFACTURING | $4.1M | Same |

**Verdict**: These are excellent contractor prospects but not **buyer** prospects until contactable.

---

## PHASE 6: IDEAL BUYER DEFINITION

### Not an Ideal Contractor. An Ideal BUYER.

| Criterion | Contractor Signal | Buyer Signal |
|-----------|-------------------|--------------|
| Has DoD contracts | ✓ Required | Not sufficient |
| Faces CMMC requirements | ✓ Required | Not sufficient |
| Manufacturing industry | Nice to have | Not relevant |
| Has recent awards | ✓ Required | Not sufficient |
| **Can be contacted** | Not checked | **REQUIRED** |
| **Has decision maker** | Not checked | **REQUIRED** |
| **Has budget authority** | Not checked | **REQUIRED** |
| **Has urgency** | Not checked | **REQUIRED** |

### Ideal Buyer Profile

```
1. CAN BUY (Ability)
   - Contract value > $500k (can afford $3,500+ service)
   - Active in last 2 years (not defunct)
   - Company size 10-500 employees (sweet spot)
   - Not a government entity or nonprofit

2. LIKELY TO BUY (Intent)
   - Handles CUI or flow-down requirements
   - No in-house compliance team visible
   - Not already CMMC certified
   - Decision maker accessible

3. LIKELY TO BUY SOON (Urgency)
   - Active RFP requiring CMMC in progress
   - Award deadline within 12 months
   - Recent prime contractor notification
   - Compliance deadline communicated
   
4. CAN BE CONTACTED (Reachability)
   - Website present
   - Decision maker identified
   - Email or phone verified
   - Contactability score > 50
```

### Current vs Ideal

| What Organism Finds | What Ideal Buyer Needs |
|---------------------|------------------------|
| Has DoD exposure | Can be contacted |
| Is in manufacturing | Has decision maker |
| Has "defense" keyword | Has urgency |
| Has some contract value | Can afford service |
| Might need CMMC | Needs CMMC NOW |

---

## PHASE 7: FINAL VERDICT

### Current organism identifies:

## **CONTRACTORS** (not BUYERS)

### Evidence

| Evidence | Finding |
|----------|---------|
| DOD Exposure | All 39 are DoD contractors |
| Manufacturing | 21 of 39 are manufacturing |
| Contract Activity | All have some federal contracts |
| **Contactability** | Only 1 of 39 can be contacted |
| **Decision Maker** | Only 1 of 39 has known DM |
| **Buying Intent** | 0 of 39 have verified intent |
| **Buying Urgency** | 0 of 39 have known urgency |

### The Gap

```
CONTRACTOR IDENTIFICATION:  ████████████████████ 100%
BUYER IDENTIFICATION:       █                      2.6%
```

### Root Cause

The organism asks: "Is this a federal contractor with DOD exposure?"
It should ask: "Is this someone who will buy compliance services from us?"

These are **completely different questions**.

---

## DELIVERABLE SUMMARY

### Top Predictive Signals (What Actually Matters)

| Rank | Signal | Correlation |
|------|--------|-------------|
| 1 | Decision Maker Present | HIGHEST |
| 2 | Contactability Score | HIGHEST |
| 3 | Website Present | HIGH |
| 4 | Intelligence Completeness | HIGH |
| 5 | Award Recency | MEDIUM |

### Weakest Signals (Add No Value)

| Signal | Why Useless |
|--------|-------------|
| DOD Exposure | All companies have it |
| Manufacturing Keyword | All match |
| Defense Keyword | All match |
| Generic CMMC/DFARS Likelihood | Derived from DOD, not independent |
| Aerospace Exposure | Rare and irrelevant |

### Missing Signals (Would Transform Quality)

| Rank | Signal | Impact |
|------|--------|--------|
| 1 | Decision Maker Identity | CRITICAL |
| 2 | Verified Contact Method | CRITICAL |
| 3 | Active Compliance Deadline | HIGH |
| 4 | Prime Contractor Status | HIGH |
| 5 | Active RFP Participation | HIGH |

### Ideal Buyer Definition

**A company that:**
1. **CAN BUY** — Has budget (>$500k contracts), is active, right size
2. **LIKELY TO BUY** — Needs CMMC, no in-house team, decision maker accessible
3. **LIKELY TO BUY SOON** — Has deadline, active RFP, or prime pressure
4. **CAN BE CONTACTED** — Website, decision maker, verified email/phone

### Contractor vs Buyer Verdict

| Question | Answer |
|----------|--------|
| Does organism find contractors? | YES (39/39) |
| Does organism find buyers? | NO (1/39) |
| What's missing? | Ability to contact + urgency signals |
| Why? | Model optimizes for contractor traits, not buyer traits |

---

**Commit SHA**: f3f95bd (source data)  
**Audit Date**: 2026-06-12  
**Final Verdict**: Organism identifies **CONTRACTORS**, not **BUYERS**

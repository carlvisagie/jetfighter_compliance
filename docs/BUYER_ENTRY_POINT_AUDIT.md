# BUYER ENTRY POINT AUDIT

**PATCH**: ACQ-QUAL-4  
**Date**: 2026-06-12  
**Purpose**: Identify where first-time compliance buyers originate

## EXECUTIVE SUMMARY

The most likely source of Customer #1 is a **small MSP or IT contractor** (10-50 employees) that recently won or is bidding on their first DoD subcontract. They have technical skills but zero compliance expertise, understand they need help, and can make purchasing decisions quickly.

Manufacturing companies — the current search focus — are the **least likely** to produce early customers despite having high compliance need. They have lower tech adoption, slower purchasing cycles, and often have internal resources.

---

## PHASE 1: IDEAL FIRST-TIME BUYER CHARACTERISTICS

### First-Time Compliance Burden Indicators

| Indicator | Why It Matters | Detection Method |
|-----------|----------------|------------------|
| First DoD contract/subcontract | No existing compliance infrastructure | Contract history < 2 years |
| SBIR Phase I/II winner | New to federal, compliance is foreign | SBIR database |
| Recent flow-down notification | Compliance suddenly required | Cannot detect externally |
| No visible compliance officer | No internal team | Website/LinkedIn analysis |
| Small team (10-100) | Cannot afford FTE compliance staff | Employee count |
| Technical focus (IT/SW/Eng) | Core team is engineers, not compliance | Industry classification |

### Low Internal Compliance Maturity Indicators

| Indicator | Why It Matters | Buyer Likelihood |
|-----------|----------------|------------------|
| No NIST 800-171 self-assessment visible | Haven't started | HIGH |
| No compliance certifications claimed | No ISO 27001, SOC 2, etc. | HIGH |
| No security/compliance page on website | Not thinking about it | HIGH |
| Small LinkedIn compliance team (0-1) | No dedicated staff | HIGH |
| Technical leadership only | CEO is engineer, not former DoD | HIGH |

### Willingness to Purchase Outside Help Indicators

| Indicator | Why It Matters | Buyer Likelihood |
|-----------|----------------|------------------|
| Time-constrained leadership | Too busy building product | HIGH |
| Previous use of consultants | Pattern of outsourcing expertise | HIGH |
| VC-backed / growth stage | Money available, time isn't | HIGH |
| Approaching deadline | Can't build internal capability fast enough | HIGHEST |
| First major compliance requirement | Doesn't know where to start | HIGHEST |

---

## PHASE 2: BUYER POPULATION PROFILES

### Profile 1: MSPs / Managed IT Service Providers

```
DESCRIPTION:
Small to mid-size IT service companies managing infrastructure
for multiple clients, some of which are defense contractors.

SIZE SWEET SPOT: 10-75 employees
TYPICAL STRUCTURE: Technical CEO, small ops team, no compliance staff
COMPLIANCE TRIGGER: Client requires them to be compliant (flow-down)
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | HIGH — CUI flows through their systems |
| Internal Capability | LOW — IT skills, not compliance skills |
| Budget for Help | MEDIUM-HIGH — $5k-$20k feasible |
| Decision Speed | FAST — Owner makes decisions |
| Reachability | HIGH — All have websites, LinkedIn, email |
| Tech Adoption | HIGH — Will use online tools/platforms |

**BUYER PERSONA**: "Mike runs a 25-person MSP. His biggest client just won a Navy subcontract and told him he needs to be CMMC compliant within 6 months or lose the account. He Googles 'CMMC compliance help' tonight."

### Profile 2: Software/SaaS Companies

```
DESCRIPTION:
Software product companies selling to government or defense primes.
Typically building tools used in defense workflows.

SIZE SWEET SPOT: 15-100 employees
TYPICAL STRUCTURE: Technical founders, product-focused, no GRC team
COMPLIANCE TRIGGER: Enterprise sales to DoD or primes require CMMC
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | HIGH — Software touches CUI |
| Internal Capability | LOW — Engineers, not compliance |
| Budget for Help | HIGH — VC money or revenue |
| Decision Speed | FAST — Startup decision-making |
| Reachability | HIGHEST — All online, active on LinkedIn |
| Tech Adoption | HIGHEST — Native digital |

**BUYER PERSONA**: "Sarah's SaaS startup just got a $500k opportunity with a defense prime, but procurement says they need CMMC Level 2. She has 90 days and zero compliance experience."

### Profile 3: SBIR/STTR Recipients

```
DESCRIPTION:
Small innovative companies receiving federal R&D funding.
Often first-time federal contractors.

SIZE SWEET SPOT: 5-50 employees
TYPICAL STRUCTURE: PhD founders, research focus, minimal operations
COMPLIANCE TRIGGER: Phase II contract includes DFARS clauses
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | HIGH — Handling government-funded research |
| Internal Capability | VERY LOW — Scientists, not compliance |
| Budget for Help | MEDIUM — SBIR funds limited |
| Decision Speed | MEDIUM — May need board approval |
| Reachability | HIGH — Public SBIR database, websites |
| Tech Adoption | HIGH — Researchers comfortable with tech |

**BUYER PERSONA**: "Dr. Chen's AI startup just won a Phase II SBIR from the Air Force. The contracting officer mentioned DFARS 252.204-7012. Chen has no idea what that means."

### Profile 4: IT Contractors (Federal IT Services)

```
DESCRIPTION:
Companies providing IT services directly to federal agencies.
Help desks, system administration, network management.

SIZE SWEET SPOT: 20-200 employees
TYPICAL STRUCTURE: Operations-heavy, project managers, IT staff
COMPLIANCE TRIGGER: Contract recompete requires CMMC
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | HIGH — Direct CUI access |
| Internal Capability | LOW-MEDIUM — Some awareness, limited action |
| Budget for Help | HIGH — Contract margins support it |
| Decision Speed | MEDIUM — Multiple stakeholders |
| Reachability | HIGH — GSA Schedule holders are public |
| Tech Adoption | HIGH — IT is their business |

**BUYER PERSONA**: "James runs a 50-person federal IT contractor. His biggest contract is up for recompete next year and the new RFP requires CMMC Level 2. He hasn't started."

### Profile 5: Engineering Services Firms

```
DESCRIPTION:
Small engineering consultancies providing design, analysis,
or testing services to defense primes.

SIZE SWEET SPOT: 10-100 employees
TYPICAL STRUCTURE: PE-led, project-based, minimal admin staff
COMPLIANCE TRIGGER: Prime contractor flow-down
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | HIGH — Engineering drawings are CUI |
| Internal Capability | LOW — Engineers, not compliance |
| Budget for Help | MEDIUM-HIGH — Professional services margins |
| Decision Speed | MEDIUM — Partnership decisions |
| Reachability | MEDIUM — Professional, but less digital |
| Tech Adoption | MEDIUM — Tools-focused, not platform-native |

**BUYER PERSONA**: "Tom's 30-person mechanical engineering firm just got a call from Lockheed. They need NIST 800-171 compliance to continue as a supplier."

### Profile 6: Federal Consultants

```
DESCRIPTION:
Management and technical consultants serving federal agencies.
Often former government employees.

SIZE SWEET SPOT: 5-50 employees
TYPICAL STRUCTURE: Senior partners, junior analysts, minimal back-office
COMPLIANCE TRIGGER: Handling classified adjacent or CUI materials
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | MEDIUM-HIGH — Depends on contract type |
| Internal Capability | MEDIUM — Understand process, may DIY |
| Budget for Help | HIGH — Consulting margins |
| Decision Speed | FAST — Partner-led decisions |
| Reachability | HIGH — All on LinkedIn |
| Tech Adoption | MEDIUM — Process-oriented |

**BUYER PERSONA**: "Jennifer's boutique defense consulting firm needs CMMC for an upcoming DHS contract. She understands compliance but doesn't want to build it internally."

### Profile 7: Electronics Manufacturers

```
DESCRIPTION:
Companies making electronic components, PCBs, or assemblies
for defense applications.

SIZE SWEET SPOT: 25-150 employees
TYPICAL STRUCTURE: Factory operations, engineering, minimal IT/compliance
COMPLIANCE TRIGGER: Defense supply chain requirements, ITAR + CMMC
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | VERY HIGH — ITAR + CMMC overlap |
| Internal Capability | LOW — Manufacturing focus |
| Budget for Help | MEDIUM — Tight margins |
| Decision Speed | SLOW — Operations-driven culture |
| Reachability | LOW-MEDIUM — Less digital presence |
| Tech Adoption | LOW — Factory floor focus |

**BUYER PERSONA**: "Bill runs a PCB assembly shop. His defense work is 30% of revenue. He knows CMMC is coming but doesn't know where to start."

### Profile 8: Research Organizations

```
DESCRIPTION:
University spin-offs, research institutes, and labs
performing defense-funded R&D.

SIZE SWEET SPOT: 10-100 researchers
TYPICAL STRUCTURE: Academic culture, grants administration, minimal ops
COMPLIANCE TRIGGER: DoD funding requires DFARS compliance
```

| Attribute | Assessment |
|-----------|------------|
| Compliance Need | HIGH — Handling defense research data |
| Internal Capability | VERY LOW — Academics, not compliance |
| Budget for Help | LOW-MEDIUM — Grant constraints |
| Decision Speed | SLOW — Academic governance |
| Reachability | HIGH — Public institutions |
| Tech Adoption | MEDIUM — Researchers vary widely |

**BUYER PERSONA**: "The university spin-off just won a DoD grant. The PI has never heard of CMMC. The grants office has no idea how to help."

---

## PHASE 3: POPULATION SCORING

### Scoring Matrix

| Population | Compliance Pressure | Urgency | Reachability | Purchasing Authority | Expected Conversion |
|------------|--------------------:|--------:|-------------:|---------------------:|--------------------:|
| **MSPs** | 8/10 | 9/10 | 9/10 | 9/10 | **9/10** |
| **Software/SaaS** | 8/10 | 9/10 | 10/10 | 8/10 | **9/10** |
| **SBIR Recipients** | 7/10 | 8/10 | 8/10 | 7/10 | **8/10** |
| **IT Contractors** | 8/10 | 7/10 | 8/10 | 7/10 | **7/10** |
| **Engineering Firms** | 8/10 | 6/10 | 6/10 | 7/10 | **6/10** |
| **Federal Consultants** | 6/10 | 5/10 | 8/10 | 8/10 | **5/10** |
| **Electronics Mfg** | 9/10 | 5/10 | 5/10 | 5/10 | **4/10** |
| **Research Orgs** | 7/10 | 4/10 | 7/10 | 4/10 | **4/10** |

### Scoring Definitions

- **Compliance Pressure**: How strong is the external compliance requirement?
- **Urgency**: How soon do they need to act?
- **Reachability**: How easy is it to find and contact decision makers?
- **Purchasing Authority**: How easy is it for them to buy ($3,500-$8,000)?
- **Expected Conversion**: Combined likelihood of becoming a paying customer

---

## PHASE 4: TIERED RANKING

### Tier A — Highest Conversion Potential

| Population | Total Score | Key Advantage |
|------------|-------------|---------------|
| **MSPs / IT Services** | 44/50 | Owner-operated, fast decisions, compliance is existential |
| **Software/SaaS Companies** | 44/50 | Tech-native, deadline-driven, budget available |
| **SBIR Recipients** | 38/50 | First-time federal, need hand-holding, findable |

**Why Tier A**: These populations combine high compliance pressure with fast decision-making and easy reachability. They don't have internal resources and know it.

### Tier B — Good Potential, Slower Conversion

| Population | Total Score | Key Challenge |
|------------|-------------|---------------|
| **IT Contractors** | 37/50 | Multiple stakeholders, longer sales cycle |
| **Engineering Firms** | 33/50 | Less digital, relationship-driven purchasing |
| **Federal Consultants** | 32/50 | May DIY, understand compliance somewhat |

**Why Tier B**: Good compliance need but either harder to reach or may attempt internal solutions first.

### Tier C — High Effort, Lower Conversion

| Population | Total Score | Key Challenge |
|------------|-------------|---------------|
| **Electronics Manufacturing** | 28/50 | Hard to reach, slow decisions, tight budgets |
| **Research Organizations** | 26/50 | Academic governance, grant constraints |

**Why Tier C**: Despite high compliance need, organizational culture and purchasing processes make conversion difficult.

---

## PHASE 5: CUSTOMER #1 POPULATION

### Most Likely Source of Customer #1

## **MSP or Software/SaaS Company**

### Reasoning

| Factor | MSP/SaaS | Manufacturing (Current Focus) |
|--------|----------|------------------------------|
| Decision speed | Days to weeks | Months |
| Decision maker access | Owner/CEO direct | Multiple layers |
| Budget authority | Owner decides | Committee/approval |
| Online searchability | Very high | Low |
| Response to digital marketing | High | Low |
| Urgency tolerance | Act fast | Deliberate |
| Compliance awareness | Growing rapidly | Established patterns |

### Customer #1 Scenario

```
MOST LIKELY PATH:

1. Small MSP (15-40 employees) gets flow-down notice from client
2. Owner Googles "CMMC compliance help for MSPs"
3. Finds KeepYourContracts via SEO/content
4. Submits paperwork for assessment
5. Receives quote, makes decision in <1 week
6. Pays via PayPal
7. Project kicks off

TIME TO CLOSE: 1-3 weeks
DEAL SIZE: $3,500-$8,000
COMPLEXITY: Low
```

### Why NOT Manufacturing (Current Focus)

| Barrier | Impact |
|---------|--------|
| No online search behavior | Won't find KeepYourContracts |
| Committee purchasing | Slows decision to months |
| Relationship-driven | Need referrals, not websites |
| Lower tech adoption | Less comfortable with digital process |
| Existing consultants | May already have compliance vendor |

---

## PHASE 6: FIRST 10 CUSTOMERS POPULATION

### Expected Distribution

| Population | Expected Customers | % of First 10 |
|------------|-------------------:|---------------|
| **MSPs / IT Services** | 3-4 | 30-40% |
| **Software/SaaS** | 2-3 | 20-30% |
| **SBIR Recipients** | 2-3 | 20-30% |
| **IT Contractors** | 1-2 | 10-20% |
| **Engineering Firms** | 0-1 | 0-10% |
| Manufacturing | 0 | 0% |

### Reasoning

**MSPs (3-4)**: Highest volume of urgent, time-sensitive compliance needs. Owner-operators make fast decisions.

**Software/SaaS (2-3)**: Similar urgency, very reachable, often have enterprise sales deadlines driving compliance timelines.

**SBIR Recipients (2-3)**: Steady stream of first-time federal contractors who have no idea how to comply. Very searchable via SBIR database.

**IT Contractors (1-2)**: Larger potential deals but longer sales cycles. May get 1-2 from referrals.

**Manufacturing (0)**: Wrong channel. They buy from relationships and trade shows, not websites.

---

## PHASE 7: FINAL VERDICT — HIGHEST ROI POPULATION

### If the Organism Could Search Only ONE Population

## **Small MSPs / IT Service Providers (10-75 employees)**

### ROI Analysis

| Factor | MSP Population | Expected Value |
|--------|----------------|----------------|
| Population size | ~30,000 with DoD exposure | Large |
| Conversion rate | ~2-5% (high for B2B) | High |
| Average deal size | $3,500-$6,000 | Medium |
| Sales cycle | 1-3 weeks | Very short |
| Customer acquisition cost | Low (inbound/SEO) | Efficient |
| Lifetime value | High (recurring compliance needs) | Strong |
| Referral potential | High (MSP networks/communities) | Multiplier |

### Why MSPs Over Software/SaaS

While Software/SaaS companies score equally high, MSPs have advantages:

1. **More urgent**: Flow-down pressure is immediate (lose client vs. lose opportunity)
2. **Simpler decision**: Single owner vs. startup board
3. **Repeat pattern**: MSPs talk to each other, referrals likely
4. **Lower competition**: Less saturated than tech startup compliance market
5. **Clearer pain point**: "My client will fire me" is concrete

### Discovery Strategy Implication

```
CURRENT:
Search "precision machining" in USASpending → Manufacturing companies

OPTIMAL:
Search MSP/IT service providers with DoD client exposure
- GSA Schedule 70 holders (small IT)
- 8(a) IT services contractors  
- NAICS 541512 (Computer Systems Design)
- NAICS 541513 (Computer Facilities Management)
- NAICS 541519 (Other IT Services)
- LinkedIn: "Managed Service Provider" + "government" + "defense"
```

---

## DELIVERABLE SUMMARY

### Ranked Buyer Populations

| Tier | Population | Conversion Score | Priority |
|------|------------|------------------|----------|
| **A** | MSPs / IT Services | 44/50 | **HIGHEST** |
| **A** | Software / SaaS | 44/50 | **HIGH** |
| **A** | SBIR Recipients | 38/50 | **HIGH** |
| B | IT Contractors | 37/50 | MEDIUM |
| B | Engineering Firms | 33/50 | MEDIUM |
| B | Federal Consultants | 32/50 | MEDIUM |
| C | Electronics Mfg | 28/50 | LOW |
| C | Research Orgs | 26/50 | LOW |

### Customer #1 Population

**MSP or Software/SaaS Company** — Small (10-50 employees), owner-operated, facing immediate flow-down pressure, will find KeepYourContracts via search, decide in days.

### First 10 Customers Population

| Population | Expected Count |
|------------|----------------|
| MSPs | 3-4 |
| Software/SaaS | 2-3 |
| SBIR Recipients | 2-3 |
| IT Contractors | 1-2 |
| Manufacturing | 0 |

### Expected Conversion Quality

| Population | Conversion Rate | Sales Cycle | Effort |
|------------|-----------------|-------------|--------|
| MSPs | 2-5% | 1-3 weeks | Low |
| Software/SaaS | 2-4% | 2-4 weeks | Low |
| SBIR | 1-3% | 3-6 weeks | Medium |
| Manufacturing | <0.5% | 3-6 months | High |

### Reasoning Summary

```
Current organism searches: Manufacturing/Aerospace
Expected conversion: <0.5%, 3-6 month cycle

Optimal organism searches: MSPs/IT Services
Expected conversion: 2-5%, 1-3 week cycle

ROI DIFFERENCE: 10-20x higher with MSP focus
```

### Final Verdict

**Highest ROI Population**: Small MSPs / IT Service Providers

**Why**: Fastest decisions, highest reachability, immediate pain, owner purchasing authority, active online search behavior, strong referral networks.

**The current manufacturing focus will not produce Customer #1.** The discovery universe must shift to tech-adjacent service providers.

---

**Commit SHA**: 3709848 (source data)  
**Audit Date**: 2026-06-12  
**Final Verdict**: **MSPs** are the highest-ROI entry point for first customers

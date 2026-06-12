# Acquisition Documentation Map

**Last updated:** 2026-06-12  
**Source of truth:** Production

---

## CANONICAL

The single source of truth for acquisition architecture.

| Document | Purpose | Status |
|----------|---------|--------|
| [`AUTONOMOUS_ACQUISITION_ORGANISM.md`](./AUTONOMOUS_ACQUISITION_ORGANISM.md) | Complete acquisition architecture: CustomerIntelligenceRecord, EvidencedValue, enrichment pipelines, buying likelihood, decision maker intelligence, API reference | **CURRENT** |

**When in doubt, read the canonical document.**

---

## ACTIVE SUPPORTING DOCUMENTS

Documents that complement the canonical architecture.

| Document | Purpose | Status |
|----------|---------|--------|
| [`LAUNCH_PATH.md`](./LAUNCH_PATH.md) | Production onboarding flow (inquiry → intake → upload) | CURRENT |
| [`FIRST_SALE_OPERATOR_SOP.md`](./FIRST_SALE_OPERATOR_SOP.md) | Payment workflow (review → payment link → kickoff) | CURRENT |
| [`PRODUCTION_CONSTITUTION.md`](./PRODUCTION_CONSTITUTION.md) | Production governance (§7 covers acquisition) | CURRENT |
| [`CONTROLLED_ONBOARDING_ACQUISITION.md`](./CONTROLLED_ONBOARDING_ACQUISITION.md) | MVP validation messaging and observation | CURRENT |
| [`architecture/acquisition.md`](./architecture/acquisition.md) | Brief architectural summary | CURRENT |

---

## DEPRECATED DOCUMENTS

Documents that describe superseded architecture. **Do not build against these.**

| Document | Reason Deprecated | Replacement |
|----------|-------------------|-------------|
| [`LEAD_DISCOVERY_ENGINE.md`](./LEAD_DISCOVERY_ENGINE.md) | CSV-based lead import replaced by CustomerIntelligenceRecord | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| [`FORENSIC_ACQUISITION_INTELLIGENCE.md`](./FORENSIC_ACQUISITION_INTELLIGENCE.md) | Pain/urgency scoring replaced by EvidencedValue and buying signals | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |

**These documents are preserved for historical reference only.**

---

## LEGACY DOCUMENTS

Historical references not part of active architecture.

| Document | Notes |
|----------|-------|
| `archive/legacy/stripe/*` | Archived Stripe integration (banned payment rail) |
| Historical patch summaries | Reference only |

---

## BINDING LAW

Documents that govern all acquisition work.

| Document | Scope |
|----------|-------|
| [`../AGENTS.md`](../AGENTS.md) | Agent rules, IRON LAW, protected systems |
| [`KYC_CONSTITUTION.md`](./KYC_CONSTITUTION.md) | Article V — Acquisition and discovery |
| [`PRODUCTION_IS_THE_ONLY_TRUTH.md`](./PRODUCTION_IS_THE_ONLY_TRUTH.md) | Environment contract |

---

## Quick Reference

### Where to find...

| Topic | Document |
|-------|----------|
| CustomerIntelligenceRecord structure | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| EvidencedValue / SignalState | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| Buying Likelihood Engine | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| Decision Maker Intelligence | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| API endpoints | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| Enrichment pipelines | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| ICP tier system | `AUTONOMOUS_ACQUISITION_ORGANISM.md` |
| MVP outreach messaging | `CONTROLLED_ONBOARDING_ACQUISITION.md` |
| Payment workflow | `FIRST_SALE_OPERATOR_SOP.md` |
| Production onboarding flow | `LAUNCH_PATH.md` |

---

## Rule Zero

```
Production Truth
    ↓
AUTONOMOUS_ACQUISITION_ORGANISM.md
    ↓
Supporting Documents
    ↓
Deprecated Documents (historical only)
```

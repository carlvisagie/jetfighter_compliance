# Acquisition (controlled MVP)

**Not a CRM.** Evidence-backed customer intelligence.

## Customer Intelligence System

The acquisition system is documented in [`docs/AUTONOMOUS_ACQUISITION_ORGANISM.md`](../../docs/AUTONOMOUS_ACQUISITION_ORGANISM.md).

For the complete documentation map: [`docs/ACQUISITION_DOCUMENT_MAP.md`](../../docs/ACQUISITION_DOCUMENT_MAP.md).

### Key directories

| Path | Use |
|------|-----|
| `../customer_intelligence/` | CustomerIntelligenceRecord JSON files |
| `observation_log.md` | Human session notes for MVP validation |

### Operator access

- **Customer Intelligence:** Control → Customer Intelligence
- **Top Prospects:** `/api/operator/top-prospects`
- **Buying Likelihood:** `/api/operator/customer-intelligence/buying-likelihood`

## Legacy files (historical)

The following files are from the superseded CSV-based system and are no longer used:

| Path | Status |
|------|--------|
| `leads/` | Legacy lead storage (superseded by CustomerIntelligenceRecord) |
| `tracking.csv` | Legacy funnel tracking |
| `feedback.csv` | Legacy feedback capture |
| `intelligence/` | Legacy signals/targets |

See [`docs/LEAD_DISCOVERY_ENGINE.md`](../../docs/LEAD_DISCOVERY_ENGINE.md) (DEPRECATED) for historical reference only.

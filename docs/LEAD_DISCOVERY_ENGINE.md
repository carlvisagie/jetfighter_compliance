# Lead Discovery Engine

Production-grade **prospect intake** for JetFighter_Compliance. Finds and scores **candidate** companies from owner-approved sources—not autonomous spam outreach.

## What it does

1. Reads `data/acquisition/leads/import_candidates.csv`
2. Validates and normalizes rows
3. Assigns `lead_id` (e.g. `L-20260525-0001`)
4. Scores `fit_score` and `confidence_score` (0–100)
5. Appends to `leads.jsonl` (never overwrites existing leads)
6. Syncs `leads.csv`
7. Builds `review_queue.csv` (fit ≥ 65, status `new` or `reviewed`)
8. Writes `data/acquisition/reports/latest_discovery_report.md`
9. Sets `inquiry_routed_link` per lead for **manual** outreach after owner approval

**Run:**

```bash
python scripts/acquisition_import_candidates.py
```

**Ops UI:** `/ui/lead_discovery.html`

## What it does NOT do

- Scrape LinkedIn or bypass login walls
- Violate robots.txt
- Send email, DMs, or automated messages
- Set `approved_for_outreach` automatically
- Replace owner judgment
- Depend on Sintra (optional helper only)

## Safe / legal source rules

| Allowed | Not allowed |
|---------|-------------|
| Owner-provided CSV | LinkedIn scraping |
| Public company websites (manual research) | Login-gated bulk export |
| Public directories where terms allow | Spam lists |
| Trade association pages (where permitted) | Auto-messaging |
| Manual Sintra-generated lists **reviewed by owner** | Illegal scraping |
| Future: lawful public APIs (e.g. SAM.gov export) when wired | robots.txt violations |

## Import format

File: `data/acquisition/leads/import_candidates.csv`

```csv
company_name,website,contact_name,contact_title,contact_email,linkedin_url,industry,segment,source,source_url,location,notes
```

**segment** (required): `aerospace`, `manufacturing`, `compliance-heavy`, `audit-stressed`, `government-subcontractor`, `quality-ops-manager`

## Lead model

Stored fields: `lead_id`, `company_name`, `website`, `contact_name`, `contact_title`, `contact_email`, `linkedin_url`, `industry`, `segment`, `source`, `source_url`, `location`, `pain_signals`, `compliance_signals`, `fit_score`, `confidence_score`, `notes`, `status`, `created_utc`, `updated_utc`, `reason_summary`, `inquiry_routed_link`

**Statuses:** `new`, `reviewed`, `approved_for_outreach`, `contacted`, `responded`, `inquiry_submitted`, `intake_completed`, `rejected`, `do_not_contact`

## Scoring method

Implemented in `services/acquisition/scoring.py`.

- **Positive:** segment match, aerospace/manufacturing/defense keywords, CMMC/AS9100/ISO/ITAR/DFARS/NIST/audit/documentation, quality/compliance/ops titles, business email, website
- **Negative:** consumer/spam/enterprise-tier signals, no contact channel
- **Outputs:** `fit_score`, `confidence_score`, `pain_signals`, `compliance_signals`, `reason_summary`

## Review workflow

1. Run import script
2. Open `data/acquisition/leads/review_queue.csv`
3. Verify leads on public sources manually
4. Update `leads.csv` / JSONL status to `approved_for_outreach` **only after owner approval**
5. Send **personalized** outreach with that lead's `inquiry_routed_link`
6. Log funnel in `data/acquisition/tracking.csv` (manual)
7. When inquiry submits, `[ref:lead_id]` appears in inquiry message for correlation

## Connection to onboarding validation

| Step | Tool |
|------|------|
| Discover & score | Lead Discovery Engine (this) |
| Outreach copy & cohort rules | `docs/CONTROLLED_ONBOARDING_ACQUISITION.md`, `/ui/onboarding_validation.html` |
| Customer entry | `/ui/inquiry.html?ref=<lead_id>` |
| Intake & project | Existing KYC backend |

## Sintra (optional helpers)

| Worker | Role |
|--------|------|
| **Buddy** | Find candidate company names manually; no send without owner |
| **Milli** | Organize candidates into CSV import format |
| **Penn** | Tighten outreach copy after owner selects leads |
| **Soshie** | Optional light awareness only |

Sintra is **not** foundational infrastructure.

## Module map

| File | Role |
|------|------|
| `services/acquisition/models.py` | Lead model, segments |
| `services/acquisition/scoring.py` | Rule-based scores |
| `services/acquisition/storage.py` | JSONL/CSV, dedupe |
| `services/acquisition/discovery.py` | Import pipeline |
| `services/acquisition/export.py` | Markdown report |
| `scripts/acquisition_import_candidates.py` | CLI entry |

## Deduplication

Skips import when existing lead matches normalized `website`, `company_name`, `email`, or `linkedin_url`.

## Tests

```bash
python -m pytest tests/test_acquisition_lead_discovery.py -q
```

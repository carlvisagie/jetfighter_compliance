# Evidence Intelligence Layer (v1)

Upload-first document intelligence for KYC onboarding. Customers upload paperwork they already have; the platform extracts, classifies, suggests gaps, and asks for confirmation — without replacing central memory or expert review.

## Current state (v1)

| Area | Status |
|------|--------|
| Rule-based extraction | Shipped |
| PDF text (optional `pypdf`) | Supported when installed |
| DOCX/XLSX/OCR | Registered as `pending_analysis` |
| Central memory bridge | `evidence_analyzed`, `document_classified`, `profile_inferred`, `gap_detected` |
| Customer profile API | `GET /api/customer/evidence/profile` (token required) |
| Customer confirmation | `POST /api/customer/evidence/confirm` |
| Operator cockpit panel | `GET /api/operator/evidence-intelligence` |
| Project artifacts | `data/projects/<id>/evidence_intelligence/` (not canonical) |

## Target architecture

```
Upload → /api/evidence/register
      → save evidence + ledger + forensics
      → evidence_intelligence.process_evidence_upload (sync, non-blocking response)
      → project artifacts (jsonl/json)
      → central memory timeline + telemetry
      → customer profile / guidance / operator cockpit
```

**Iron law:** Canonical truth lives in central memory (`data/memory/`). Project `evidence_intelligence/` files are audit artifacts and operator convenience only.

## Data flow

1. **Validate** `project_id` and optional continuation/intake `token`.
2. **Store** file under `data/projects/<id>/evidence/`.
3. **Extract** text (TXT, MD, JSON, HTML, CSV, PDF if available).
4. **Classify** document type (policy, MFA, training, vendor, SSP, etc.).
5. **Extract entities** (email, domain, phone, compliance refs, technologies).
6. **Update profile** and **detect gaps** vs. document inventory.
7. **Write** append-only jsonl + `profile.json` / `gaps.json`.
8. **Emit** telemetry (`subsystem: evidence_intelligence`).
9. **Bridge** `safe_write_after_evidence_intelligence` → entity timeline.

## APIs

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/evidence/register` | Optional token | Upload + trigger analysis |
| `GET /api/customer/evidence/profile` | Token required | Customer-safe inferred profile |
| `POST /api/customer/evidence/confirm` | Token required | Confirm / reject / unsure |
| `GET /api/operator/evidence-intelligence` | Ops session | Operator panel data |

## Safety rules

- Never expose another customer's extracted data (token must match project).
- Operator routes require ops auth.
- Do not log full document text; snippets are redacted and capped.
- Secret patterns (API keys, private keys, passwords) masked as `[REDACTED]`.
- No compliance certification claims from weak evidence.
- Customer copy uses “We found” / “may have identified” / “Please confirm” — never “we know.”
- Dangerous extensions (`.exe`, `.bat`, etc.) are rejected without execution.

## Extraction confidence

| Status | Meaning |
|--------|---------|
| `inferred` | Rule-based, needs confirmation |
| `confirmed` | Customer confirmed |
| `rejected` | Customer rejected |
| `conflicting` | Multiple incompatible values |
| `unsure` | Customer unsure |

Low-confidence items (&lt; 0.55) emit `low_confidence_extraction` telemetry.

## v1 limitations

- Rule-based only — no paid LLM/OCR in production path.
- Does not prove compliance or replace expert review.
- Office formats and images may stay `pending_analysis`.
- Company names from regex can be wrong — confirmation required.
- Max 3 missing items shown to customers at once (more via friction layer).

## Future phases

- Optional OCR for images (safe dependency gate).
- Background queue for large files.
- Learning loop from confirmation/rejection rates into operator guidance.
- Stronger entity resolution with intake fields (no duplicate graphs).

## Related docs

- [CENTRAL_MEMORY.md](./CENTRAL_MEMORY.md)
- [KYC_CONSTITUTION.md](./KYC_CONSTITUTION.md)
- [LAUNCH_PATH.md](./LAUNCH_PATH.md)

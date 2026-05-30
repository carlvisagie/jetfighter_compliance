# Launch path — KeepYourContracts (current)

**Status:** Active production onboarding (inquiry-led).  
**Canonical agent docs:** [`../AGENTS.md`](../AGENTS.md), [`KYC_CONSTITUTION.md`](./KYC_CONSTITUTION.md)  
**Verify:** `powershell -File scripts/verify-render-production.ps1` and `scripts/verify-production-live.ps1`

> **Agent rule:** This is the only approved production onboarding path. Do not document or wire Stripe/Shopify/Cloudflare tunnel as launch without owner instruction.

## Customer flow

1. **Inquiry** — `https://compliance.keepyourcontracts.com/ui/inquiry.html` (or `/ui/shop.html` → program link)
2. **API** — `POST /api/inquiry/submit` → `project_id`, `intake_url`, `upload_url`, order event
3. **Intake** — Customer opens `intake_url`, completes `/ui/intake.html` (`POST /api/intake/submit`)
4. **Events** — `GET /api/events/recent` and ops event UI
5. **Onboarding** — Upload + workflow phases via returned URLs and operations console

## Production stack

| Component | Role |
|-----------|------|
| GitHub | Source (`jetfighter_compliance`) |
| Render | `kyc-backend` — FastAPI + static UI |
| JetFighter_Compliance backend | `server.py`, `services/*` |
| SMTP (optional) | Email delivery of intake links |

## Readiness (`GET /health/ready`)

- `inquiry_onboarding_active`: `true`
- `intake_secret_configured`: `true` (strong `INTAKE_TOKEN_SECRET`)
- `smtp_configured`: optional until email is required

## Controlled acquisition (MVP validation only)

Not a marketing program. See [`CONTROLLED_ONBOARDING_ACQUISITION.md`](./CONTROLLED_ONBOARDING_ACQUISITION.md). Use `ref=` on inquiry URLs for cohort tracking.

## Inactive for launch (legacy)

Stripe, Shopify, and Cloudflare Tunnel rebuild/cutover are **removed or banned** — not part of this path. PayPal is the payment path. See [`STRIPE_PURGE_AUDIT.md`](./STRIPE_PURGE_AUDIT.md).

---

## Pre-commit change gate (agents)

```bash
python -m pytest tests/test_public_ui_exposure.py tests/test_ops_route_auth.py \
  tests/test_central_memory.py tests/test_organism_observability.py \
  tests/test_operator_guidance.py tests/test_kyc_guardrails.py -q
python -m pytest tests/ -q
```

CI: `.github/workflows/kyc_guardrails.yml`

## Organism memory on launch path

| Step | Central memory |
|------|----------------|
| Inquiry | `safe_write_after_inquiry`, entity link, forensics bridge |
| Kickoff | `safe_read_before_kickoff`, `safe_link_after_kickoff`, ledger link |
| Intake | `safe_write_after_intake`, workflow timeline |
| Evidence | `safe_record_evidence` / `evidence_uploaded` |
| Evidence intelligence (v1) | Upload → rule-based extract/classify → customer profile + confirmation; see [EVIDENCE_INTELLIGENCE_LAYER.md](./EVIDENCE_INTELLIGENCE_LAYER.md) |
| Compliance intelligence (v1) | Scheduled public-source monitoring → review queue → central memory; see [COMPLIANCE_INTELLIGENCE_ENGINE.md](./COMPLIANCE_INTELLIGENCE_ENGINE.md) |
| Email (optional) | Telemetry only — `email/send_*` events |

Observability: `GET /api/memory/observability`, UI `/ui/memory.html` (operator auth required).

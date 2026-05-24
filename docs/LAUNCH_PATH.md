# Launch path — KeepYourContracts (current)

**Status:** Active production onboarding (inquiry-led).  
**Verify:** `powershell -File scripts/verify-render-production.ps1` and `scripts/verify-production-live.ps1`

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

## Inactive for launch (legacy)

Stripe webhooks, Shopify, and Cloudflare Tunnel rebuild/cutover docs are **not** part of this path. Legacy backend route `POST /webhooks/stripe` remains for automated tests only.

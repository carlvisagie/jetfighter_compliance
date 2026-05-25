# KeepYourContracts — JetFighter_Compliance

Compliance operations backend and customer UI. Production runs on **Render** (`kyc-backend`); source of truth is **GitHub** (`jetfighter_compliance`).

## Active launch path (customer onboarding)

1. **Inquiry** — Customer opens [`/ui/inquiry.html`](../ui/inquiry.html) (or arrives from [`/ui/shop.html`](../ui/shop.html) with a program subject).
2. **Submit** — `POST /api/inquiry/submit` creates the project, returns `project_id`, `intake_url`, `upload_url`, and logs an order event.
3. **Intake** — Customer completes [`/ui/intake.html`](../ui/intake.html) with the token from the inquiry response (`GET /api/intake/resolve`, `POST /api/intake/submit`).
4. **Event log** — Ops and automation use `GET /api/events/recent` and the event helper UI.
5. **Customer onboarding** — Workflow phases, upload, and status via intake + upload URLs and the operations console.

**Production entry URL:** `https://compliance.keepyourcontracts.com/ui/inquiry.html`  
**Canonical API host:** `https://jetfighter-compliance.onrender.com`

## Verify production

```powershell
powershell -File scripts/verify-render-production.ps1
```

Optional full live check (custom domain + inquiry smoke):

```powershell
powershell -File scripts/verify-production-live.ps1
```

## Required production configuration

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | `production` |
| `INTAKE_TOKEN_SECRET` | Strong secret for intake tokens |
| `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL` | HTTPS links in inquiry/intake emails |
| `OPS_API_KEY` | Blocks unauthenticated ops test routes |
| SMTP (`SMTP_*`, `SMTP_ENABLED`) | Optional — intake links in email when configured |

## Local development (not production)

`start_production.ps1` and `start_everything.ps1` run uvicorn locally and may use a **Cloudflare Tunnel** for temporary public URLs on a developer machine. **Do not** use tunnel scripts as the production launch path; deploy via Render.

## Operations UI

| Page | Path |
|------|------|
| Services / catalog | `/ui/shop.html` |
| Readiness review (customer) | `/ui/inquiry.html` |
| Intake | `/ui/intake.html?token=…` |
| Operations hub | `/ui/control.html` |
| Command / health | `/ui/command.html` |

## Health

- `GET /healthz` — liveness  
- `GET /health/ready` — readiness (`intake_secret_configured`, `smtp_configured`, `inquiry_onboarding_active`)

## Central memory (one brain, many vessels)

See [`CENTRAL_MEMORY.md`](./CENTRAL_MEMORY.md). Ops UI: `/ui/memory.html`.

## Lead Discovery Engine

See [`LEAD_DISCOVERY_ENGINE.md`](./LEAD_DISCOVERY_ENGINE.md) — CSV import, scoring, review queue. Ops UI: `/ui/lead_discovery.html`. Run: `python scripts/acquisition_import_candidates.py`.

## Controlled onboarding tests (MVP)

See [`CONTROLLED_ONBOARDING_ACQUISITION.md`](./CONTROLLED_ONBOARDING_ACQUISITION.md) — targets, outreach copy, CSV tracking, Sintra worker roles. Ops UI: `/ui/onboarding_validation.html`.

## Agent context

See [`AGENTS.md`](./AGENTS.md) and [`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md).

Historical integration notes (Stripe, Shopify, tunnel cutover) remain in archived `docs/KYC_*.md` files for reference only — they are **not** part of the current launch path.

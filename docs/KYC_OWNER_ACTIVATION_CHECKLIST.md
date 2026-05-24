# KYC Owner Activation Checklist — inquiry-led launch

> **Current path:** See [`LAUNCH_PATH.md`](./LAUNCH_PATH.md). Stripe / Shopify / Cloudflare tunnel steps in older docs are **inactive**.

**Verify with:** `scripts/verify-production-live.ps1` or `scripts/verify-render-production.ps1`

---

## A. Render environment (required)

Dashboard → **kyc-backend** → **Environment**:

| Key | Value |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `INTAKE_TOKEN_SECRET` | *(strong random — not dev default)* |
| `OPS_API_KEY` | *(random — for ops test routes)* |
| `PUBLIC_BASE_URL` | `https://compliance.keepyourcontracts.com` *(or rely on `RENDER_EXTERNAL_URL`)* |
| SMTP (`SMTP_*`, `SMTP_ENABLED`) | Optional — email intake links when ready |

**Pass:** `GET .../health/ready` shows `environment: production`, `inquiry_onboarding_active: true`, `intake_secret_configured: true`.

---

## B. Custom domain (Render)

1. Render → **kyc-backend** → **Settings** → **Custom Domains**  
2. Add `compliance.keepyourcontracts.com` (CNAME to Render)  
3. Confirm `GET https://compliance.keepyourcontracts.com/healthz` returns JSON `ok: true`

**Pass:** `/ui/inquiry.html` loads on the branded host.

---

## C. Smoke test (inquiry → intake)

1. Open `/ui/inquiry.html`, submit test inquiry (or use verify script).  
2. Confirm response includes HTTPS `intake_url` (not localhost).  
3. Open intake URL, submit intake form.  
4. Confirm `GET /api/events/recent` shows new order event and project appears in ops status.

**Pass:** End-to-end inquiry → project → intake → event log without payment webhooks.

---

## D. Ops-only tools (not customer-facing)

- Manual project: `/ui/new_client.html` or `POST /events/payment/test` with `X-Ops-Key` in production  
- Diagnostic kickoff: `/ui/webhook_test.html` (`POST /api/test-webhook`)

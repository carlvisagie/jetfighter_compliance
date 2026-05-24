# Agents — KeepYourContracts (jetfighter_compliance)

## STOP — confirm correct organism

You should be in **`jetfighter_compliance`**, not `purposeful-platform`.

- **This repo:** compliance sales, intake, ledger, chain of custody.  
- **SAGE repo:** https://github.com/carlvisagie/purposeful-platform — read `docs/AGENT_ONBOARDING.md` there if you need coaching context.

---

## Mandatory read before changes

1. This file  
2. **[`docs/PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md)** — **LOCKED** — build/test/verify only on live deployed URL  
3. [`docs/README.md`](./README.md)  
4. `server.py` — actual routes (do not assume endpoints exist because HTML references them)  
5. `render.yaml` — production env vars  

---

## Customer-facing pages

| Page | Path | Notes |
|------|------|--------|
| Services catalog | `/ui/shop.html` | Links to inquiry with program subject |
| Readiness review | `/ui/inquiry.html` | **Primary customer entry** — `POST /api/inquiry/submit` |
| Intake | `/ui/intake.html?token=…` | After inquiry creates project |
| Upload | `/upload` or `/ui/upload.html` | Evidence upload |

`/ui/index.html` is a **test stub**, not the production landing.

---

## Onboarding → fulfillment (active path)

| Step | Handler |
|------|---------|
| Customer inquiry | `POST /api/inquiry/submit` → `kickoff()` → intake/upload URLs + event |
| Intake complete | `POST /api/intake/submit` → workflow + communications |
| Ops manual project | `POST /events/payment/test` or `POST /api/test-webhook` (requires `X-Ops-Key` in production) |

**Legacy (inactive for launch):** `POST /webhooks/stripe` — retained for tests only; not required in Render env.

---

## Deploy

- **Canonical production URL:** `https://jetfighter-compliance.onrender.com`  
- **Render service:** `kyc-backend` (Docker)  
- **Health:** `GET /healthz`, `GET /health/ready`  
- **Verify:** `powershell -File scripts/verify-render-production.ps1`  
- **Env:** `ENVIRONMENT=production`, `INTAKE_TOKEN_SECRET`, `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL`, `OPS_API_KEY`, SMTP optional  
- **Branded host:** `compliance.keepyourcontracts.com` → Render custom domain (CNAME)

Dockerfile uses port `10000`; confirm Render `PORT` binding matches.

---

## Do not

- Merge compliance `organism/` memory into Sage `client_profile` without Owner bridge spec  
- Copy coaching `unifiedClientRepository` patterns here  
- Treat `keepyourcontracts` GitHub scaffold as runtime source  
- Document Stripe/Shopify/Cloudflare tunnel as the production launch path  

---

## Forward work (Owner-gated)

Document gaps in purposeful-platform `docs/INTEGRATION_STATUS.md` only when cross-organism; fix gaps in this repo with minimal diffs.

When in doubt: read `server.py`, change less, then **verify on the deployed public URL** per doctrine.

---

## Task completion (doctrine — no exceptions)

Every task must document before marking **DONE**:

1. **Commit hash** on `main`  
2. **Live URL** used for verification  
3. **Test command** and pass/fail count  

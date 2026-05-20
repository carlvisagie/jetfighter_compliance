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
| Landing / shop | `/ui/shop.html` | Real marketing page; PayPal payment links in HTML |
| Contact | `/ui/inquiry.html` | Posts to `/api/inquiry/submit` — **verify route exists** before deploy |
| Intake | `/ui/intake.html?token=…` | After payment / project creation |
| Upload | `/upload` or `/ui/upload.html` | Evidence upload |

`/ui/index.html` is a **test stub**, not the production landing — root should route to shop.

---

## Onboarding → fulfillment (direct; no Shopify)

| Path | Handler |
|------|---------|
| Contact inquiry | `POST /api/inquiry/submit` → `kickoff()` |
| Ops / manual project | `POST /events/payment/test` → `kickoff()` |
| Ops kickoff test UI | `POST /api/test-webhook` → `kickoff()` |
| Stripe Payment Links | `POST /webhooks/stripe` on `checkout.session.completed` → `kickoff()` |

---

## Deploy

- **Canonical production URL:** `https://jetfighter-compliance.onrender.com`  
- **Render service:** `kyc-backend` (Docker) — **do not use Windows + Cloudflare Tunnel for production** (dev/emergency only; see [`KYC_RENDER_PRODUCTION_CUTOVER.md`](./KYC_RENDER_PRODUCTION_CUTOVER.md))  
- **Health:** `GET /healthz` (liveness), `GET /health/ready` (readiness)  
- **Verify:** `powershell -File scripts/verify-render-production.ps1`  
- **Env:** `ENVIRONMENT=production`, `INTAKE_TOKEN_SECRET`, `STRIPE_WEBHOOK_SECRET`, `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL`, `OPS_API_KEY` (test routes), SMTP optional  
- **Branded host:** `compliance.keepyourcontracts.com` → Render **Custom Domain** (CNAME), not `cfargotunnel.com`  
- **Remove:** `SHOPIFY_*`, unused `STRIPE_SECRET` unless wired later  

Dockerfile uses port `10000`; confirm Render `PORT` binding matches.

---

## Do not

- Merge compliance `organism/` memory into Sage `client_profile` without Owner bridge spec  
- Copy coaching `unifiedClientRepository` patterns here  
- Treat `keepyourcontracts` GitHub scaffold as runtime source  

---

## Forward work (Owner-gated)

Document gaps in purposeful-platform `docs/INTEGRATION_STATUS.md` only when cross-organism; fix gaps in this repo with minimal diffs.

When in doubt: read `server.py`, change less, then **verify on the deployed public URL** per doctrine.

---

## Task completion (doctrine — no exceptions)

Every task must document before marking **DONE**:

1. **Commit hash** on `main`  
2. **Deployed URL** probed  
3. **Live verification result** (pass/fail, exit code, or HTTP evidence)  
4. **Rollback note** (revert commit / env / DNS)  
5. **No local-only dependency** (laptop, tunnel, uncommitted secrets)

**localhost, tunnels, and local PowerShell are never completion proof.** See [`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md).

# Agents — KeepYourContracts (jetfighter_compliance)

## STOP — confirm correct organism

You should be in **`jetfighter_compliance`**, not `purposeful-platform`.

- **This repo:** compliance sales, intake, ledger, chain of custody.  
- **SAGE repo:** https://github.com/carlvisagie/purposeful-platform — read `docs/AGENT_ONBOARDING.md` there if you need coaching context.

---

## Mandatory read before changes

1. This file  
2. [`docs/README.md`](./README.md)  
3. `server.py` — actual routes (do not assume endpoints exist because HTML references them)  
4. `render.yaml` — production env vars  

---

## Customer-facing pages

| Page | Path | Notes |
|------|------|--------|
| Landing / shop | `/ui/shop.html` | Real marketing page; Stripe links in HTML |
| Contact | `/ui/inquiry.html` | Posts to `/api/inquiry/submit` — **verify route exists** before deploy |
| Intake | `/ui/intake.html?token=…` | After payment / project creation |
| Upload | `/upload` or `/ui/upload.html` | Evidence upload |

`/ui/index.html` is a **test stub**, not the production landing — root should route to shop.

---

## Payment → fulfillment

| Path | Handler |
|------|---------|
| Shopify paid | `POST /webhooks/shopify/orders-paid` |
| Test / generic | `POST /events/payment/test` |
| Stripe Payment Links | Money collects in Stripe — **webhook to `kickoff()` must be verified** for auto-intake email |

---

## Deploy

- **Render service:** `kyc-backend` (Docker)  
- **Health:** `GET /healthz`  
- **Env:** `PUBLIC_BASE_URL`, `STRIPE_*`, `SHOPIFY_*`, `DATABASE_URL`, SMTP  

Dockerfile uses port `10000`; confirm Render `PORT` binding matches.

---

## Do not

- Merge compliance `organism/` memory into Sage `client_profile` without Owner bridge spec  
- Copy coaching `unifiedClientRepository` patterns here  
- Treat `keepyourcontracts` GitHub scaffold as runtime source  

---

## Forward work (Owner-gated)

Document gaps in purposeful-platform `docs/INTEGRATION_STATUS.md` only when cross-organism; fix gaps in this repo with minimal diffs.

When in doubt: read `server.py`, test locally, change less.

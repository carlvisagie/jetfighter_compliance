# KeepYourContracts Production Hardening — Result

**Date:** 2026-05-19  
**Task:** TASK 5 — Production hardening + deployment verification  
**Tests:** 9 passed (`test_webhook`, `test_stripe_webhook`, `test_upload_flow`, `test_production`)

---

## Files inspected

| Area | Files |
|------|--------|
| Config / env | `services/config.py`, `render.yaml`, `.env` (local) |
| Server | `server.py` |
| Production guards | `services/production.py` (new) |
| URL / Stripe | `services/public_url.py`, `services/stripe_hook.py` |
| Engine / email | `services/engine.py`, `services/emails.py` |
| UI ops | `ui/control.html`, `ui/new_client.html`, `ui/upload.html` |
| Tests | `tests/test_*.py` |
| Live host | HTTP probes to `jetfighter-compliance.onrender.com` |

---

## Files changed

| File | Change |
|------|--------|
| `services/production.py` | **Created** — startup warnings, readiness, ops guard, upload safety |
| `services/config.py` | `environment` field |
| `server.py` | Health ready, startup logs, ops guards, evidence validation, inquiry `upload_url` |
| `tests/test_production.py` | **Created** |
| `docs/KYC_PRODUCTION_HARDENING.md` | **Created** |
| `docs/KYC_PRODUCTION_VERIFICATION.md` | **Created** |
| `docs/KYC_PRODUCTION_RESULT.md` | **Created** |

---

## Hardening actions

1. **Startup** — log misconfiguration (dev intake secret, missing Stripe secret, dead Shopify env, localhost public URL).  
2. **`GET /health/ready`** — data writable, config flags for monitoring.  
3. **Ops routes** — `POST /events/payment/test` and `POST /api/test-webhook` blocked in production unless `X-Ops-Key` matches `OPS_API_KEY`.  
4. **Upload** — project must exist; filename sanitized; 50MB limit.  
5. **Inquiry API** — returns `upload_url` alongside `intake_url`.  

---

## Exact domain issue (unchanged)

`keepyourcontracts.com` still serves a **non-KYC Cloudflare origin**. Code normalization (`/`, `/shop.html` redirects) applies only when DNS points at Render. **Owner DNS fix still required.**

---

## Exact Stripe issue

- **Code:** `POST /webhooks/stripe` implemented and tested locally.  
- **Live Render:** probed **404** — **deploy not yet shipped** this route.  
- **After deploy:** register webhook URL + `STRIPE_WEBHOOK_SECRET` on Render.

---

## Exact upload issue (resolved in code)

Form had no handler; now posts to `/api/evidence/register` with project validation. Deploy required for production.

---

## Remaining risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Live deploy behind repo | High | Deploy now; verify `/webhooks/stripe` 200/401 not 404 |
| Custom domain | High | Render + Cloudflare DNS |
| Default intake secret on Render | High | Rotate `INTAKE_TOKEN_SECRET` |
| CORS wide open | Low | Tighten post-domain |
| `/api/projects` public | Low | Accept for ops UI |
| Export ZIP missing | Low | Separate task |
| Render disk persistence | Medium | Confirm `data/` survives redeploy |

---

## Operational confidence assessment

| Area | Confidence |
|------|------------|
| Core onboarding code | **High** (pytest green) |
| Production config discipline | **Medium** (warnings in place; Owner must set secrets) |
| Live Render parity | **Medium** (deploy gap on Stripe route) |
| Custom domain | **Low** (external DNS) |
| Overall | **Ready to deploy** — not yet **fully production-verified on live** until deploy + checklist |

---

## Next stabilization target

1. **Deploy** to Render and complete `KYC_PRODUCTION_VERIFICATION.md` checklist.  
2. **Fix** `keepyourcontracts.com` DNS → Render.  
3. **Stripe Dashboard** webhook delivery test with real Payment Link.  
4. **Optional:** `GET /api/project/{id}/export` minimal handler for control panel.

---

## Success criteria

| Criterion | Met |
|-----------|-----|
| Runtime startup deterministic | ✓ (warnings + worker + no crash on optional deps) |
| Env assumptions normalized | ✓ (documented REQUIRED/OPTIONAL/REMOVE) |
| Health routes verified | ✓ |
| Stripe path deterministic (code) | ✓ |
| Upload/evidence deterministic | ✓ |
| Exception handling hardened | ✓ (minimal) |
| Deployment safer | ✓ (ops guards + upload validation) |
| No new architecture | ✓ |

**Final step for Owner: deploy + run live checklist.**

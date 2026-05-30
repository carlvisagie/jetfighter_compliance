> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KeepYourContracts De-Shopify — Result Report

**Date:** 2026-05-19  
**Task:** Remove Shopify coupling; normalize direct inquiry → kickoff runtime  
**Tests:** `pytest tests/test_webhook.py` — **2 passed**

---

## Files inspected

| Area | Files |
|------|--------|
| App entry | `server.py` |
| Security / tokens | `services/security.py`, `services/config.py` |
| Adapters | `services/adapters/shopify.py`, `services/adapters/generic.py` |
| Deploy | `render.yaml`, `Dockerfile` |
| UI | `ui/inquiry.html`, `ui/intake.html`, `ui/intake.js`, `ui/shop.html`, `ui/control.html`, `ui/webhook_test.html`, `ui/new_client.html`, `ui/upload.html` |
| Tests | `tests/test_webhook.py` |
| Docs | `docs/AGENTS.md`, `docs/README.md` |
| Historical | `backups/server_pre_telemetry_router.py`, `ui_backup_*` |

---

## Files changed

| File | Change |
|------|--------|
| `server.py` | Removed Shopify webhook/imports; inquiry → `kickoff()`; test-webhook → `kickoff()` |
| `services/security.py` | Removed `verify_shopify_hmac` |
| `services/config.py` | Removed `shopify_webhook_secret` |
| `services/adapters/shopify.py` | **Deleted** |
| `render.yaml` | Removed `SHOPIFY_SECRET` env key |
| `tests/test_webhook.py` | Direct kickoff + inquiry tests |
| `ui/control.html` | De-Shopify copy |
| `ui/webhook_test.html` | De-Shopify title |
| `ui/inquiry.html` | Show `intake_url` on success |
| `docs/AGENTS.md` | Direct flow table |
| `docs/README.md` | Server description |
| `docs/KYC_DESHOPIFY_AUDIT.md` | **Created** |
| `docs/KYC_DIRECT_RUNTIME_FLOW.md` | **Created** |
| `docs/KYC_DESHOPIFY_RESULT.md` | **Created** |

**Not changed:** `ui/shop.html` (landing + Stripe links), RFQ/evidence routes, constitutional/Sage repos, Render blueprint sync, Just Talk.

---

## Shopify components removed

- Route: `POST /webhooks/shopify/orders-paid`
- Module: `services/adapters/shopify.py`
- Function: `verify_shopify_hmac()`
- Config: `shopify_webhook_secret` / blueprint `SHOPIFY_SECRET`
- Test: Shopify HMAC webhook test

---

## Runtime continuity verified

| Step | Status | Evidence |
|------|--------|----------|
| Inquiry submit | ✓ | `test_inquiry_submit_kickoff` — returns `project_id`, `intake_url` |
| Ops kickoff | ✓ | `test_kickoff_via_payment_test` |
| Intake API | ✓ | `POST /api/intake/submit` unchanged |
| Intake UI script | ✓ | `intake.js` referenced from `intake.html` |
| Evidence API | ✓ | `POST /api/evidence/register` unchanged |
| CoC API | ✓ | Unchanged |
| kickoff() | ✓ | Called from inquiry, payment/test, test-webhook |

---

## Exact runtime issue (pre-change)

Shopify webhook was the **only automated paid-order path** to `kickoff()`. Inquiry saved messages but did **not** create projects. Shopify is no longer used; webhook was dead weight and inquiry was disconnected from fulfillment.

---

## Exact fix applied

1. **Removed** Shopify webhook stack (route, HMAC, adapter, env).  
2. **Wired** `POST /api/inquiry/submit` → `kickoff()` after persisting inquiry.  
3. **Rewired** `POST /api/test-webhook` → `kickoff()` for ops testing.  
4. **Updated** docs and UI copy to direct-flow truth.

---

## Remaining risks

| Risk | Mitigation |
|------|------------|
| `PUBLIC_BASE_URL` unset on Render | Set in dashboard before production emails |
| Stripe checkout → no auto kickoff | Manual ops via inquiry or `new_client.html` until Stripe webhook (minimal future task) |
| Custom domain not on Render | Point `keepyourcontracts.com` CNAME to Render service |
| Upload HTML unwired | Use API or wire form in separate stabilization task |
| `.env` still has `SHOPIFY_WEBHOOK_SECRET` locally | Remove manually; not used by code |

---

## Next stabilization target

1. **Owner:** Set `PUBLIC_BASE_URL` on Render; remove Shopify env vars from dashboard.  
2. **Domain:** Attach `keepyourcontracts.com` to `kyc-backend` (see `docs/KYC_RUNTIME_RECONCILIATION.md` if present, or Render custom domain docs).  
3. **Upload:** Wire `ui/upload.html` → `POST /api/evidence/register` (minimal script).  
4. **Optional:** Stripe webhook → `kickoff()` (no new commerce system; single handler only).

---

## Success criteria

| Criterion | Met |
|-----------|-----|
| Shopify no longer required | ✓ |
| Dead Shopify coupling removed | ✓ |
| Runtime flow operational | ✓ (tests + kickoff paths) |
| Direct inquiry flow verified | ✓ |
| Deployment/env simplified | ✓ (code + render.yaml) |
| Docs updated | ✓ |
| No organism destabilization | ✓ |

**Deploy note:** Push and deploy `jetfighter_compliance` to Render for production to pick up removals and inquiry → kickoff wiring.

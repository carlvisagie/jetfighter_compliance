# KeepYourContracts Domain + Runtime Hardening — Result

**Date:** 2026-05-19  
**Task:** TASK 4 — Custom domain + direct Stripe + upload hardening  
**Tests:** `test_webhook`, `test_stripe_webhook`, `test_upload_flow` — **all passed**

---

## Files inspected

| Area | Files |
|------|--------|
| Domain probes | HTTP + `nslookup` for `keepyourcontracts.com`, `jetfighter-compliance.onrender.com` |
| Server | `server.py` |
| Stripe | `ui/shop.html`, `render.yaml`, `services/stripe_hook.py` (new) |
| Upload | `ui/upload.html`, `ui/intake.js`, `api/evidence/register` |
| URL helper | `services/public_url.py` (new) |
| Config | `services/config.py` |
| Tests | `tests/test_webhook.py`, `tests/test_stripe_webhook.py`, `tests/test_upload_flow.py` |

---

## Files changed

| File | Change |
|------|--------|
| `server.py` | Stripe webhook; `get_public_base_url`; kickoff idempotency + upload URLs; route aliases; intake resolve |
| `services/public_url.py` | **Created** |
| `services/stripe_hook.py` | **Created** — signature verify + SKU mapping |
| `services/config.py` | `stripe_webhook_secret` |
| `ui/upload.html` | Form wiring → `/api/evidence/register` |
| `ui/intake.js` | Redirect to upload after intake |
| `tests/test_stripe_webhook.py` | **Created** |
| `tests/test_upload_flow.py` | **Created** |
| `docs/AGENTS.md` | Stripe webhook + env |
| `docs/KYC_DOMAIN_RUNTIME_HARDENING.md` | **Created** |
| `docs/KYC_DIRECT_FLOW_VERIFICATION.md` | **Created** |
| `docs/KYC_DOMAIN_RUNTIME_RESULT.md` | **Created** |

**Not changed:** Render blueprint sync, Just Talk, constitutional docs, evidence/RFQ architecture.

---

## Exact domain issue

`keepyourcontracts.com` resolves to **Cloudflare** but serves a **non-KYC placeholder site**. It does **not** proxy to Render `kyc-backend`. Therefore `/ui/shop.html` returns **404** on the custom domain while **200** on `jetfighter-compliance.onrender.com`.

**Fix:** Owner attaches custom domain in Render and points Cloudflare DNS to Render (documented in `KYC_DOMAIN_RUNTIME_HARDENING.md`). **No code fix can replace DNS.**

---

## Exact Stripe issue

Stripe Payment Links collected payment but **no webhook** called `kickoff()`. Customers paid without automatic project/intake creation.

**Fix:** `POST /webhooks/stripe` handles `checkout.session.completed`, verifies signature, maps SKU from Payment Link slug or metadata, calls `kickoff()` (idempotent).

**Owner action:** Register webhook URL + set `STRIPE_WEBHOOK_SECRET` on Render.

---

## Exact upload issue

`ui/upload.html` had a form with **no submit handler**; `/api/evidence/register` existed but was unreachable from the customer UI.

**Fix:** Minimal inline script — resolve `project_id` from query or token; POST each file to `/api/evidence/register`.

---

## Exact fixes summary

| Gap | Fix |
|-----|-----|
| Wrong domain origin | Documented Render + Cloudflare steps; code routes normalized for when domain is live |
| Intake URLs used `127.0.0.1` | `get_public_base_url()` prefers `PUBLIC_BASE_URL`, else `RENDER_EXTERNAL_URL` |
| Stripe → no kickoff | `/webhooks/stripe` + `services/stripe_hook.py` |
| Upload disconnected | `upload.html` JS + `intake.js` handoff + `upload_url` in kickoff/intake responses |
| Duplicate Stripe projects | kickoff idempotency on `order_id` |

---

## Remaining risks

| Risk | Mitigation |
|------|------------|
| Custom domain still broken | Owner DNS + Render custom domain |
| Stripe webhook not registered | Stripe Dashboard setup |
| Payment Link SKU ambiguous | Set `metadata.sku` on links or rely on slug map in code |
| SMTP off | Enable for production emails |
| `test_engine.py` flake | Pre-existing queue timing; unrelated to this task |

---

## Next stabilization target

1. **Owner:** Fix `keepyourcontracts.com` → Render; set `PUBLIC_BASE_URL`; configure Stripe webhook.
2. **Deploy** `jetfighter_compliance` to Render.
3. **Optional:** Implement `GET /api/project/{id}/export` for control panel (minimal, separate task).
4. **Optional:** Add `metadata.sku` to each Stripe Payment Link in dashboard for explicit SKU mapping.

---

## Success criteria

| Criterion | Met |
|-----------|-----|
| Domain runtime truth verified | ✓ (documented; custom domain ≠ backend) |
| Domain routing normalized in code | ✓ (aliases + redirects) |
| Stripe kickoff deterministic | ✓ (webhook + tests) |
| Upload wiring operational | ✓ (UI + tests) |
| Evidence flow operational | ✓ |
| Direct onboarding deterministic | ✓ (inquiry + stripe + ops paths) |
| No organism destabilization | ✓ |

**Deploy to Render required for production Stripe + upload on live host.**

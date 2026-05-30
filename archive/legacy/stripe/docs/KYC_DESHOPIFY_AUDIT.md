> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KeepYourContracts — De-Shopify Audit

**Date:** 2026-05-19  
**Mode:** Stabilization — remove dead Shopify coupling; preserve direct runtime flow  
**Repo:** `jetfighter_compliance` (`kyc-backend` on Render)

---

## Executive summary

Shopify is **no longer part** of the KeepYourContracts organism. All **active** Shopify runtime paths were removed or rewired. Onboarding is **direct**:

**Inquiry / ops kickoff → `kickoff()` → intake token → intake → upload → evidence → workflow**

Stripe Payment Links on `ui/shop.html` remain **external checkout** (not Shopify). Stripe → `kickoff()` webhook is still **not implemented** (pre-existing gap; out of scope).

---

## Shopify components found (full inventory)

| # | Component | Location | Classification | Action taken |
|---|-----------|----------|----------------|--------------|
| 1 | `POST /webhooks/shopify/orders-paid` | `server.py` | **ACTIVE DEPENDENCY** (legacy) | **REMOVED** |
| 2 | `verify_shopify_hmac()` | `services/security.py` | **SAFE TO REMOVE** | **REMOVED** |
| 3 | `extract_paid_order()` | `services/adapters/shopify.py` | **SAFE TO REMOVE** | **FILE DELETED** |
| 4 | `shopify_webhook_secret` / `SHOPIFY_WEBHOOK_SECRET` | `services/config.py`, `.env` | **SAFE TO REMOVE** | **REMOVED from config**; remove from Render dashboard manually |
| 5 | `SHOPIFY_SECRET` | `render.yaml` | **DOCUMENTATION ONLY** (blueprint) | **REMOVED** (no blueprint sync per Owner rule) |
| 6 | `test_shopify_webhook_hmac` | `tests/test_webhook.py` | **DEAD CODE** (tests removed route) | **REPLACED** with direct kickoff tests |
| 7 | Control panel copy “signed Shopify test webhook” | `ui/control.html` | **DOCUMENTATION ONLY** | **UPDATED** |
| 8 | `ui/webhook_test.html` title | `ui/webhook_test.html` | **REQUIRES REPLACEMENT** (ops tool) | **RELABELED**; endpoint now calls `kickoff()` |
| 9 | `POST /api/test-webhook` (Shopify-shaped email only) | `server.py` | **REQUIRES REPLACEMENT** | **REWIRED** → `kickoff()` |
| 10 | AGENTS.md Shopify table row | `docs/AGENTS.md` | **DOCUMENTATION ONLY** | **UPDATED** |
| 11 | `backups/server_pre_telemetry_router.py` | `backups/` | **DEAD CODE** (historical) | **RETAINED** (no delete historical files) |
| 12 | `ui_backup_before_client_redesign_*/control.html` | backup UI | **DEAD CODE** | **RETAINED** |
| 13 | `dns_reset_and_audit.ps1` Shopify DNS note | script | **DOCUMENTATION ONLY** | **RETAINED** (ops script, not runtime) |
| 14 | `A) Autostart the tunnel...txt` | notes | **DOCUMENTATION ONLY** | **RETAINED** |
| 15 | `ui/shop.html` links to `/ui/shop.html` | UI nav | **NOT SHOPIFY** (landing page name) | **RETAINED** |
| 16 | Stripe `buy.stripe.com` links | `ui/shop.html` | **NOT SHOPIFY** | **RETAINED** (external payment) |

**Not found:** `ShopifyAPI`, `ShopifyClient`, storefront SDK, cart sync, product sync, Shopify npm/pip packages.

---

## Classification summary

| Class | Count | Notes |
|-------|-------|-------|
| ACTIVE DEPENDENCY (removed) | 1 | Shopify orders-paid webhook |
| SAFE TO REMOVE | 4 | HMAC helper, adapter, config secret, test |
| REQUIRES REPLACEMENT / REWIRED | 2 | test-webhook, inquiry → kickoff |
| DOCUMENTATION ONLY | 5 | AGENTS, render.yaml, scripts, backups |
| NOT SHOPIFY (retained) | 2 | shop.html landing, Stripe links |

---

## Removals (runtime)

| Removed | Reason |
|---------|--------|
| `POST /webhooks/shopify/orders-paid` | No longer sold via Shopify |
| `services/adapters/shopify.py` | Only used by removed webhook |
| `verify_shopify_hmac()` | Only used by removed webhook |
| `Settings.shopify_webhook_secret` | Unused after HMAC removal |
| `SHOPIFY_SECRET` in `render.yaml` | Stale env reference |

---

## Retained / rewired (operational)

| Component | Role |
|-----------|------|
| `kickoff()` | Core onboarding — **unchanged** |
| `make_intake_token()` / `parse_intake_token()` | Intake auth — **unchanged** |
| `POST /events/payment/test` | Ops/manual project creation → `kickoff()` |
| `POST /api/inquiry/submit` | **REWIRED** → saves inquiry + calls `kickoff()` |
| `POST /api/test-webhook` | **REWIRED** → `kickoff()` (ops test) |
| `POST /api/intake/submit` | Intake form — **unchanged** |
| `POST /api/evidence/register` | Evidence — **unchanged** |
| `POST /api/coc/event*` | Chain of custody — **unchanged** |
| RFQ routes | **unchanged** (separate vendor flow) |

---

## Remaining risks

1. **`PUBLIC_BASE_URL`** — if unset on Render, `kickoff()` intake links default to `http://127.0.0.1:8080`. Set in dashboard to `https://jetfighter-compliance.onrender.com` (or custom domain once DNS fixed).
2. **Stripe Payment Links** — payment still external; no automatic `kickoff()` until Stripe webhook is wired (future, minimal).
3. **`keepyourcontracts.com` DNS** — custom domain not pointed at Render (separate from de-Shopify); see prior runtime reconciliation.
4. **Upload form** — `ui/upload.html` still has no submit handler wired to `/api/evidence/register` (pre-existing).
5. **Render env cleanup** — remove `SHOPIFY_WEBHOOK_SECRET` / `SHOPIFY_SECRET` from dashboard manually (blueprint not synced).

---

## Rollback note

If rollback is required: restore `services/adapters/shopify.py` and Shopify webhook block from `backups/server_pre_telemetry_router.py` (lines 103–127). Re-add `verify_shopify_hmac` from git history. Prefer forward fix: direct inquiry → `kickoff()`.

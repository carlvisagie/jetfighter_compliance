> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# Stripe Purge Audit

**Date:** 2026-05-29  
**Policy:** Stripe is **banned** on KeepYourContracts. PayPal is the payment path.  
**Guardrail:** `tests/test_stripe_ban_guardrail.py` — fails on reintroduction.

---

## Summary

| Category | Action |
|----------|--------|
| Active code | **Removed** |
| Webhook route | **Removed** (`POST /webhooks/stripe` → 404) |
| Config / env | **Removed** (`STRIPE_WEBHOOK_SECRET`, `stripe_webhook_secret`) |
| Dependencies | **None** (never had `stripe-python` in requirements) |
| Public UI | **Clean** (`ui/shop.html` has no `buy.stripe.com`) |
| Tests | **Removed** legacy webhook tests; **added** ban guardrail |
| Historical docs | **Retained** with superseded/historical context |

---

## Deleted (MUST DELETE — completed)

| Path | Was |
|------|-----|
| `services/stripe_hook.py` | Stripe signature verify + checkout.session parser |
| `tests/test_stripe_webhook.py` | Webhook route regression tests |
| `httpsbuy.stripe.comtest_cNicMX23yau.txt` | Stray Stripe Payment Link URL file |
| `server.py` — `POST /webhooks/stripe` | Active webhook route + import |
| `services/config.py` — `stripe_webhook_secret` | `STRIPE_WEBHOOK_SECRET` setting |
| `services/memory/organism_integration.py` — `stripe_webhook` registry entry | Integration audit legacy entry |
| `services/memory/organism_observability.py` — `stripe_webhook` invisible entry | Observability dashboard entry |

---

## Modified

| Path | Change |
|------|--------|
| `tests/test_organism_integration.py` | Assert `stripe_webhook` **not** in legacy audit |
| `docs/LAUNCH_PATH.md` | Stripe route removed; points to this audit |
| `AGENTS.md` | Rule 11: do not reintroduce Stripe |
| `docs/KYC_CONSTITUTION.md` | Stripe webhook row → removed/banned |

---

## Added

| Path | Purpose |
|------|---------|
| `tests/test_stripe_ban_guardrail.py` | Scans production paths; fails on Stripe patterns; asserts 404 on `/webhooks/stripe` |
| `docs/STRIPE_PURGE_AUDIT.md` | This document |

---

## Remaining references (with justification)

### HISTORICAL DOC ONLY

Archived audit snapshots that mention Stripe setup, webhook URLs, or `STRIPE_WEBHOOK_SECRET`. **Not launch guidance.** Do not follow for new work.

- `docs/KYC_FINAL_PRODUCTION_VERDICT.md` (header: superseded)
- `docs/KYC_PRODUCTION_STEM_TO_STERN_AUDIT.md`
- `docs/KYC_PRODUCTION_VERIFICATION.md`
- `docs/KYC_PRODUCTION_HARDENING.md`
- `docs/KYC_PRODUCTION_RESULT.md`
- `docs/KYC_PRODUCTION_LOCK_CONFIRMED.md`
- `docs/KYC_P0_CLOSEOUT.md`
- `docs/KYC_OWNER_ACTIVATION_CHECKLIST.md` (header: superseded)
- `docs/KYC_OWNER_BLOCKER_CLOSEOUT_TASK18.md`
- `docs/KYC_OWNER_DASHBOARD_ACTIVATION_ASSIST.md`
- `docs/KYC_DOMAIN_RUNTIME_HARDENING.md`
- `docs/KYC_DOMAIN_RUNTIME_RESULT.md`
- `docs/KYC_DIRECT_FLOW_VERIFICATION.md`
- `docs/KYC_DIRECT_RUNTIME_FLOW.md`
- `docs/KYC_ORGANISM_INTEGRATION_AUDIT.md`
- `docs/KYC_DESHOPIFY_AUDIT.md`
- `docs/BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md`
- `docs/RENDER_PRODUCTION_CUTOVER_PLAN.md`
- `docs/RENDER_ENV_HARDENING_RESULT.md`
- `docs/LIVE_DEPLOYMENT_SYNC_VERIFICATION.md`
- `docs/PAYPAL_MIGRATION_RESULT.md` (documents migration away from Stripe)
- `docs/README.md` (notes historical `KYC_*.md` archives)

### BACKUP / DRAFT ARTIFACTS (not deployed)

Old shop HTML with `buy.stripe.com` links — **not served**:

- `backups/shop_*.html`
- `backups/shop_pre_*.html`
- `drafts/shop_v2*.html`
- `ui_backup_before_client_redesign_20260517-172621/shop.html`

**Justification:** Pre-PayPal migration snapshots. Not in `ui/`. Guardrail scans `ui/` only. May be deleted in a future cleanup; not active code.

### RUNTIME DATA (TEST RESIDUE)

- `data/memory/entities.jsonl` — test entity display name "Stripe Buyer" from old webhook test kickoff
- `data/memory/timelines.jsonl` — `stripe@example.com` in historical test events

**Justification:** Local dev telemetry residue, not payment integration. No action required for ban enforcement.

### ACTIVE PAYMENT PATH (not Stripe)

- `scripts/generate_payment_qr_assets.py` — PayPal NCP URLs (`paypal.com/ncp/payment/...`)

---

## Verification

```bash
python -m pytest tests/test_stripe_ban_guardrail.py -q
curl -s -o /dev/null -w "%{http_code}" -X POST https://compliance.keepyourcontracts.com/webhooks/stripe
# Expected: 404 after deploy
```

**Full suite (2026-05-29):** `668 passed` in 294s (`python -m pytest tests/ -q`)

---

## Reintroduction policy

Any PR that adds Stripe code, routes, env vars, dependencies, Payment Links in public UI, or non-guardrail Stripe tests **must be rejected**. Update this audit if historical docs are consolidated or backup folders are purged.

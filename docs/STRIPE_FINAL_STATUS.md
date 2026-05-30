# Stripe Final Status

**Date:** 2026-05-30  
**Policy:** Stripe is **banned**. PayPal is the production payment path.  
**Guardrail:** `tests/test_stripe_ban_guardrail.py`

---

## Active inventory (must remain zero)

| Category | Count |
|----------|------:|
| Active Stripe Code | **0** |
| Active Stripe Dependencies | **0** |
| Active Stripe Routes | **0** |
| Active Stripe Secrets | **0** |
| Active Stripe UI | **0** |

---

## Historical archive

| Category | Count |
|----------|------:|
| Historical Archived References | **396** mentions across **40** files |

All historical Stripe artifacts live under [`archive/legacy/stripe/`](../archive/legacy/stripe/) with headers:

```
DEPRECATED
NOT DEPLOYED
HISTORICAL ONLY
```

### Archive layout

| Path | Contents |
|------|----------|
| `archive/legacy/stripe/docs/` | 28 superseded KYC/audit docs + purge audit |
| `archive/legacy/stripe/html/` | 6 pre-PayPal shop HTML snapshots |
| `archive/legacy/stripe/drafts/` | 5 draft shop/telemetry files |

---

## Removed from active tree

| Action | Items |
|--------|-------|
| **Deleted** | `services/stripe_hook.py`, `tests/test_stripe_webhook.py`, stray Payment Link file |
| **Removed from backups/** | 5 `shop*.html` files (archived first) |
| **Removed from drafts/** | `shop_v2*.html`, telemetry drafts with Stripe refs |
| **Removed from ui_backup/** | `shop.html` (archived as `ui_backup_shop.html`) |
| **Moved from docs/** | 28 historical docs → archive |

Production paths (`server.py`, `services/`, `ui/`, `render.yaml`, `requirements.txt`) scan **clean**.

---

## Verification

```bash
python -m pytest tests/test_stripe_ban_guardrail.py -q
```

Success condition: repository-wide text scan for `stripe` outside `archive/legacy/stripe/` returns **zero active production references** (allowlisted ban-enforcement files only).

### Allowlisted (ban enforcement only)

- `tests/test_stripe_ban_guardrail.py` — detection patterns
- `tests/test_organism_integration.py` — legacy registry key absent
- `tests/test_kyc_guardrails.py` — CI wiring
- `.github/workflows/kyc_guardrails.yml` — CI wiring
- `docs/STRIPE_FINAL_STATUS.md` — this document
- Policy pointers in `AGENTS.md`, `docs/LAUNCH_PATH.md`, `docs/KYC_CONSTITUTION.md`, `docs/README.md` (no payment wiring)

---

## Reintroduction policy

Any PR adding Stripe code, routes, env vars, dependencies, Payment Links in public UI, or non-guardrail Stripe tests **must be rejected**.

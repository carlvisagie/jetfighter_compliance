# Render Production Env Hardening — Task 32 / Task 32B

**Date:** 2026-05-20  
**Service:** Render `kyc-backend`  
**Branded URL:** `https://compliance.keepyourcontracts.com`  
**Mode:** Docs + public URL verification only — **no code, DNS, Blueprint sync, or secrets in git**

---

## Executive status — FINAL (Task 32B)

| Item | Status |
|------|--------|
| **Owner applied vars in Render Dashboard** | **PASS** |
| **Redeploy after env change** | **PASS** (live reflects new env) |
| **Production readiness on branded host** | **PASS** |
| **Branded production URL operational** | **PASS** |

**Verdict:** Render production env hardening **complete**. KYC runs as **`ENVIRONMENT=production`** on `https://compliance.keepyourcontracts.com` with branded `PUBLIC_BASE_URL`, rotated intake secret, and ops guard active.

---

## Configured environment variables (names only — no values)

| Variable | Status |
|----------|--------|
| `ENVIRONMENT` | **`production`** (verified live) |
| `PUBLIC_BASE_URL` | **`https://compliance.keepyourcontracts.com`** (verified live) |
| `INTAKE_TOKEN_SECRET` | **Configured** (`intake_secret_configured: true`) |
| `OPS_API_KEY` | **Configured** (`POST /events/payment/test` without key → **403**) |

Secret values are stored only in Render Dashboard — **not** in git, docs, or chat.

---

## Final live verification (Task 32B)

**Probe host:** `https://compliance.keepyourcontracts.com` — public URLs only

### `GET /healthz`

| Expected | Actual |
|----------|--------|
| `{"ok":true,"service":"kyc-backend"}` | **PASS** |

### `GET /health/ready`

| Check | Expected | Actual |
|-------|----------|--------|
| `ok` | `true` | **PASS** — `true` |
| `status` | `ready` | **PASS** — `ready` |
| `environment` | `production` | **PASS** — `production` |
| `intake_secret_configured` | `true` | **PASS** — `true` |
| `public_base_url` | `https://compliance.keepyourcontracts.com` | **PASS** |
| `data_writable` | `true` | **PASS** |
| `stripe_webhook_configured` | optional | `false` (PayPal-first — acceptable) |
| `smtp_configured` | optional | `false` |

```json
{
  "ok": true,
  "status": "ready",
  "checks": {
    "data_writable": true,
    "projects_dir": true,
    "public_base_url": "https://compliance.keepyourcontracts.com",
    "stripe_webhook_configured": false,
    "intake_secret_configured": true,
    "smtp_configured": false,
    "environment": "production"
  }
}
```

### UI pages

| URL | Result |
|-----|--------|
| `https://compliance.keepyourcontracts.com/ui/shop.html` | **PASS** — HTTP 200 |
| `https://compliance.keepyourcontracts.com/ui/intake.html` | **PASS** — HTTP 200 |

### Ops guard (production)

| Test | Result |
|------|--------|
| `POST /events/payment/test` without `X-Ops-Key` | **PASS** — HTTP **403** |

### Inquiry smoke (branded links)

| Test | Result |
|------|--------|
| `POST /api/inquiry/submit` → `intake_url` host | **PASS** — uses `compliance.keepyourcontracts.com` (not localhost / onrender fallback) |

---

## Task 32B success criteria

| Criterion | Met? |
|-----------|------|
| `PUBLIC_BASE_URL` = compliance host | **Yes** |
| `INTAKE_TOKEN_SECRET` configured | **Yes** |
| `OPS_API_KEY` configured | **Yes** (403 without header) |
| `/health/ready` `ok=true`, `status=ready` | **Yes** |
| `public_base_url` on compliance host | **Yes** |
| `/ui/shop.html` 200 | **Yes** |
| Branded production URL operational | **Yes** |

---

## Historical — Task 32 baseline (before env apply)

Before Owner set Render env vars, live `/health/ready` showed `environment: development`, `intake_secret_configured: false`, `public_base_url` on `jetfighter-compliance.onrender.com`, and ops test route returned **200** without key. See git history for Task 32 initial doc commit.

---

## Owner procedure (reference)

Render → **kyc-backend** → **Environment**:

| Key | Value |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `PUBLIC_BASE_URL` | `https://compliance.keepyourcontracts.com` |
| `INTAKE_TOKEN_SECRET` | *(strong secret — Render only)* |
| `OPS_API_KEY` | *(strong secret — Render only)* |

Generate secrets locally (do not commit):

```powershell
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

---

## Rollback

| Step | Action |
|------|--------|
| 1 | Render → revert `ENVIRONMENT` or remove production secrets |
| 2 | Manual Deploy |
| 3 | Verify `/healthz` still 200 |
| 4 | **No git rollback** for env-only changes |

---

## Remaining risks (env hardening does not fix)

| Risk | Notes |
|------|--------|
| Ephemeral `data/` on Render | Evidence loss on redeploy — storage task |
| PayPal → kickoff automation | Manual until webhook task |
| `STRIPE_WEBHOOK_SECRET` unset | OK for PayPal-first |
| Apex `keepyourcontracts.com` | Separate marketing/DNS decision |

---

## Doctrine closure (Task 32B)

| # | Item | Value |
|---|------|--------|
| 1 | **Commit hash** | `3c769d6` |
| 2 | **Deployed URL** | `https://compliance.keepyourcontracts.com` |
| 3 | **Live verification** | `/healthz`, `/health/ready`, shop, intake — **PASS**; production env **PASS** |
| 4 | **Rollback** | Revert Render env vars; redeploy; no code rollback |
| 5 | **No local-only dependency** | Public HTTPS probes only; docs-only update |

**No secrets in git.**

---

## Related

| Doc | Purpose |
|-----|---------|
| [`RENDER_DOMAIN_CUTOVER_RESULT.md`](./RENDER_DOMAIN_CUTOVER_RESULT.md) | DNS cutover PASS |
| [`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md) | Live-URL verification law |
| [`scripts/verify-production-live.ps1`](../scripts/verify-production-live.ps1) | May still fail on Stripe/apex — run after policy update |

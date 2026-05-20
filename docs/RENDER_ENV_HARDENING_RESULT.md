# Render Production Env Hardening — Task 32

**Date:** 2026-05-20  
**Service:** Render `kyc-backend`  
**Branded URL:** `https://compliance.keepyourcontracts.com`  
**Mode:** Docs + public URL verification only — **no code, DNS, Blueprint sync, or secrets in git**

---

## Executive status

| Item | Status |
|------|--------|
| **Env vars documented** | **Done** (names only below) |
| **Owner applied vars in Render Dashboard** | **Pending** — agent has no Render API/dashboard access |
| **Redeploy after env change** | **Pending** |
| **Production readiness checks on live host** | **NOT MET** at baseline probe (see §5) |

**Verdict:** Task 32 **procedure complete**; **production env PASS** requires Owner to set four variables in Render, redeploy, then re-run §6 verification commands.

---

## 1. Required environment variables (from repo)

Source: `services/config.py`, `services/production.py`, `services/public_url.py`

| Variable | Required value (description only) | Read by |
|----------|-----------------------------------|---------|
| `ENVIRONMENT` | `production` | `is_production()`, readiness `environment` |
| `PUBLIC_BASE_URL` | `https://compliance.keepyourcontracts.com` | `SETTINGS.public_base_url`, `get_public_base_url()` |
| `INTAKE_TOKEN_SECRET` | Strong secret — **not** `dev-dev-dev-dev-dev` | `SETTINGS.intake_token_secret`, `services/security.py` |
| `OPS_API_KEY` | Strong secret | `require_ops_access()` on `/events/payment/test`, `/api/test-webhook` |

### Not required for Task 32 (optional / legacy)

| Variable | Notes |
|----------|--------|
| `STRIPE_WEBHOOK_SECRET` | PayPal-first; optional; readiness may show `false` |
| `SMTP_*` | Optional email |
| `RENDER_EXTERNAL_URL` | Set by Render platform — fallback if `PUBLIC_BASE_URL` unset |
| `DATABASE_URL` | Listed in `render.yaml` but **unused** by main app path |

**Do not sync `render.yaml` Blueprint** unless Owner explicitly approves.

---

## 2. Generate secrets (Owner — local only)

Run **twice** in PowerShell on your machine. **Do not** commit, paste into git/docs, or share in chat.

```powershell
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

| Run | Use for |
|-----|---------|
| First output | `INTAKE_TOKEN_SECRET` in Render |
| Second output | `OPS_API_KEY` in Render |

Store values in a password manager. Rotating `INTAKE_TOKEN_SECRET` invalidates existing intake tokens.

---

## 3. Owner — exact Render Dashboard steps

1. Open https://dashboard.render.com/
2. Service **`kyc-backend`** → **Environment**
3. Add or update (names exact, case-sensitive):

| Key | Value |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `PUBLIC_BASE_URL` | `https://compliance.keepyourcontracts.com` |
| `INTAKE_TOKEN_SECRET` | *(first generated secret — not documented here)* |
| `OPS_API_KEY` | *(second generated secret — not documented here)* |

4. **Save Changes**
5. **Manual Deploy** → Deploy latest commit (or wait for autoDeploy if env-only triggers redeploy)
6. Wait until deploy status **Live** (~2–5 min)

**Remove if present (cleanup):** `SHOPIFY_WEBHOOK_SECRET`, `SHOPIFY_SECRET` — unused.

---

## 4. Baseline verification (before Owner env apply)

**Probe:** `https://compliance.keepyourcontracts.com` — 2026-05-20 Task 32

### `/healthz`

| Expected | Actual |
|----------|--------|
| `{"ok":true,"service":"kyc-backend"}` | **PASS** |

### `/health/ready`

| Check | Expected (after Task 32) | Baseline actual |
|-------|--------------------------|-----------------|
| `environment` | `production` | **`development`** — FAIL |
| `intake_secret_configured` | `true` | **`false`** — FAIL |
| `public_base_url` | `https://compliance.keepyourcontracts.com` | **`https://jetfighter-compliance.onrender.com`** — FAIL |
| `data_writable` | `true` | **PASS** |
| `stripe_webhook_configured` | optional | `false` |

### UI

| URL | Baseline |
|-----|----------|
| `/ui/shop.html` | **200** PASS |
| `/ui/intake.html` | **200** PASS |

### Ops guard (production behavior)

| Test | Baseline (development) |
|------|-------------------------|
| `POST /events/payment/test` without `X-Ops-Key` | **200** (allowed — not production mode) |

After hardening: same request must return **403**.

---

## 5. Post-redeploy verification (Owner / agent — run after §3)

Run on **public URLs only** (not localhost):

```powershell
# Health
Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz

# Readiness — all production checks must pass
$r = Invoke-RestMethod https://compliance.keepyourcontracts.com/health/ready
$r.checks.environment          # expect: production
$r.checks.intake_secret_configured  # expect: True
$r.checks.public_base_url      # expect: https://compliance.keepyourcontracts.com

# UI
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/shop.html -UseBasicParsing
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/intake.html -UseBasicParsing

# Ops guard — must block without key
try {
  Invoke-WebRequest https://compliance.keepyourcontracts.com/events/payment/test `
    -Method POST -Body '{"order_id":"x","email":"x@y.com","name":"X","skus":["T"]}' `
    -ContentType "application/json" -UseBasicParsing
  Write-Host "FAIL: should not return 2xx"
} catch {
  if ($_.Exception.Response.StatusCode.value__ -eq 403) { Write-Host "PASS: ops guard 403" }
}
```

### Pass criteria

| # | Criterion |
|---|-----------|
| 1 | `/healthz` JSON `ok:true`, `service:kyc-backend` |
| 2 | `environment` = `production` |
| 3 | `intake_secret_configured` = `true` |
| 4 | `public_base_url` = `https://compliance.keepyourcontracts.com` |
| 5 | `/ui/shop.html` and `/ui/intake.html` → **200** |
| 6 | `POST /events/payment/test` without `X-Ops-Key` → **403** |

Record results in §7 after Owner redeploy.

---

## 6. Rollback

| Step | Action |
|------|--------|
| 1 | Render → Environment → revert `ENVIRONMENT` to `development` or remove keys |
| 2 | Remove or restore previous `INTAKE_TOKEN_SECRET` / `OPS_API_KEY` |
| 3 | Manual Deploy previous deploy or clear env and redeploy |
| 4 | Verify `/healthz` still 200 on compliance + Render URLs |
| 5 | **No git rollback** required for env-only change |

---

## 7. Post-redeploy results (fill after Owner apply)

| Check | Result |
|-------|--------|
| `environment` | _pending_ |
| `intake_secret_configured` | _pending_ |
| `public_base_url` | _pending_ |
| `/healthz` | _pending_ |
| UI 200 | _pending_ |
| Ops guard 403 | _pending_ |

**Update this section** after Owner completes §3 and re-run §5.

---

## 8. Remaining risks (env hardening does not fix)

| Risk | Notes |
|------|--------|
| Ephemeral `data/` on Render | Evidence loss on redeploy — storage task |
| PayPal → kickoff automation | Manual until webhook task |
| `STRIPE_WEBHOOK_SECRET` unset | OK for PayPal-first |
| Apex `keepyourcontracts.com` | Separate from compliance host |

---

## 9. Doctrine closure (Task 32 doc commit)

| # | Item | Value |
|---|------|--------|
| 1 | **Commit hash** | *(after push)* |
| 2 | **Deployed URL** | `https://compliance.keepyourcontracts.com` |
| 3 | **Live verification** | `/healthz` + UI **PASS**; readiness production checks **FAIL** until Owner applies §3 |
| 4 | **Rollback** | Revert Render env vars; redeploy; no code rollback |
| 5 | **No local-only dependency** | Public URL probes; secrets generated locally by Owner only |

**No secrets in this document or in git.**

---

## Related

| Doc | Purpose |
|-----|---------|
| [`RENDER_DOMAIN_CUTOVER_RESULT.md`](./RENDER_DOMAIN_CUTOVER_RESULT.md) | DNS cutover PASS |
| [`BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md`](./BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md) | P0 env blockers |
| [`scripts/verify-production-live.ps1`](../scripts/verify-production-live.ps1) | Full lock verifier (update after env PASS) |

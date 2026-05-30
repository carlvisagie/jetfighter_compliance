> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# Owner Blocker Closeout — Task 18 (Shortest Path)

**Date:** 2026-05-19  
**Status:** **OWNER ACTION REQUIRED** — agent cannot complete dashboard steps  
**Verifier:** `scripts/verify-production-live.ps1` → must exit **0**  
**Repo path:** `C:\Users\Carl\jetfighter_compliance` (or clone of `carlvisagie/jetfighter_compliance`)

---

## Current live truth (pre-closeout)

| Blocker | Live evidence |
|---------|----------------|
| Env not production | `/health/ready` → `environment: development` |
| Stripe secret | `stripe_webhook_configured: false`; unsigned POST → **503** |
| Intake secret | `intake_secret_configured: false` |
| Ops guard | `POST /events/payment/test` without key → **200** (not 403 until production + `OPS_API_KEY`) |
| Custom domain | `keepyourcontracts.com/healthz` → HTML, not KYC JSON; `/ui/shop.html` → **404** |

**Code and UI on Render URL are ready.** Only Owner dashboard + DNS work remains.

---

## Step 1 — Render environment (≈10 min)

1. [Render Dashboard](https://dashboard.render.com/) → service **`kyc-backend`** → **Environment**
2. Set (or edit) these keys — **Save Changes** after each batch:

| Key | Value |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `PUBLIC_BASE_URL` | `https://keepyourcontracts.com` |
| `INTAKE_TOKEN_SECRET` | Strong random (see generate below) |
| `STRIPE_WEBHOOK_SECRET` | From Stripe Step 2 (`whsec_…`) |
| `OPS_API_KEY` | Strong random (see generate below) |

3. **Delete** any `SHOPIFY_*` variables.
4. **Manual Deploy** → deploy latest `main` commit (`d422635` or newer).

### Generate secrets (PowerShell, run once)

```powershell
# INTAKE_TOKEN_SECRET
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))

# OPS_API_KEY
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
```

**Never use** `dev-dev-dev-dev-dev` for `INTAKE_TOKEN_SECRET`.

### Pass check (Render URL only)

```powershell
(Invoke-RestMethod https://jetfighter-compliance.onrender.com/health/ready).checks | Format-List environment, intake_secret_configured, stripe_webhook_configured
```

Expect: `production`, `True`, `True`.

---

## Step 2 — Stripe webhook (≈5 min)

1. [Stripe Dashboard](https://dashboard.stripe.com/) → **Developers** → **Webhooks** → **Add endpoint**
2. **Endpoint URL:** `https://jetfighter-compliance.onrender.com/webhooks/stripe`  
   *(After DNS works, add or switch to `https://keepyourcontracts.com/webhooks/stripe` if preferred.)*
3. **Events:** `checkout.session.completed`
4. **Reveal** signing secret (`whsec_…`) → paste into Render `STRIPE_WEBHOOK_SECRET` → **Save** → **Manual Deploy**

### Pass check

```powershell
try {
  Invoke-WebRequest https://jetfighter-compliance.onrender.com/webhooks/stripe -Method POST -Body '{}' -ContentType 'application/json' -UseBasicParsing
} catch { $_.Exception.Response.StatusCode.value__ }  # expect 401, not 503
```

---

## Step 3 — Custom domain + DNS (≈15–30 min)

### Render

1. **kyc-backend** → **Settings** → **Custom Domains**
2. Add: `keepyourcontracts.com` and `www.keepyourcontracts.com`
3. Copy Render’s DNS target (CNAME or A record instructions)

### Cloudflare (or your DNS host)

1. Point **both** hostnames to Render’s target
2. **Remove** parking / Pages / Workers / conflicting routes on `keepyourcontracts.com`
3. SSL: Full (strict) recommended once Render cert is active
4. Wait for propagation (often 5–30 min; up to 48h)

### Pass check

```powershell
Invoke-RestMethod https://keepyourcontracts.com/healthz
# expect: {"ok":true,"service":"kyc-backend"}

(Invoke-WebRequest https://keepyourcontracts.com/ui/shop.html -UseBasicParsing).StatusCode  # expect 200
```

---

## Step 4 — Run verifier (final gate)

```powershell
cd C:\Users\Carl\jetfighter_compliance
powershell -File scripts\verify-production-live.ps1
echo Exit: $LASTEXITCODE
```

**TARGET: exit code 0.**

| Check | Pass means |
|-------|------------|
| Render readiness | `ENVIRONMENT=production`, secrets configured |
| Stripe route | Unsigned POST → **401** |
| Ops guard | `payment/test` without key → **403** |
| Custom domain | `/healthz` JSON ok; `/ui/shop.html` **200** |
| Inquiry smoke | HTTPS intake URL on Render |

---

## After exit 0 (agent / Owner)

1. Re-run Task 9 / update `docs/KYC_PRODUCTION_LOCK_CONFIRMED.md` → **LOCK CONFIRMED**
2. Update `purposeful-platform/docs/STABILIZATION_STATUS_MASTER.md` → STABILIZED OPERATIONS MODE
3. Freeze downgrades per `OPERATIONAL_FREEZE_RULES.md` (CONFIG P0 lifted; expansion still blocked)

---

## Do not (during Task 18)

- Change application code, UI, or backend
- `render blueprint sync`
- Touch Just Talk / SAGE repos for KYC fixes
- Force push

---

## Reference docs

| Doc | Use |
|-----|-----|
| `KYC_OWNER_DASHBOARD_ACTIVATION_ASSIST.md` | Full step-by-step with troubleshooting |
| `KYC_OWNER_ACTIVATION_CHECKLIST.md` | Checkbox list |
| `LIVE_DEPLOYMENT_SYNC_VERIFICATION.md` | Last live probe (Task 17) |

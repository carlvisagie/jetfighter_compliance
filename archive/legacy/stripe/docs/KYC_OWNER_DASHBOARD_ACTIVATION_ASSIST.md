> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KYC Owner Dashboard Activation Assist (Task 10)

**Purpose:** Complete remaining Render + Stripe + Cloudflare steps with zero ambiguity.  
**Service:** Render web service **`kyc-backend`**  
**Repo / deploy:** `carlvisagie/jetfighter_compliance` — commit **`5492efa`** or later on `main`  
**When done:** Run verifier → exit **0** → re-run Task 9 → freeze downgrades to **STABILIZED OPERATIONS MODE**

**Do not:** change code, sync Render Blueprint, or touch Just Talk / SAGE.

---

## 1. Render Environment Setup

### Where to go

1. Open [Render Dashboard](https://dashboard.render.com/)
2. Select service **`kyc-backend`**
3. Left sidebar → **Environment**
4. For each row below: **Add Environment Variable** (or edit existing), then **Save Changes**

### Variables to set (exact keys)

| Key | Value |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `PUBLIC_BASE_URL` | `https://keepyourcontracts.com` |
| `INTAKE_TOKEN_SECRET` | *(see generate below — must NOT be `dev-dev-dev-dev-dev`)* |
| `STRIPE_WEBHOOK_SECRET` | *(paste from Stripe after Section 3 — can add in a second save)* |
| `OPS_API_KEY` | *(see generate below)* |

### Copy/paste block (fill secrets before saving)

```env
ENVIRONMENT=production
PUBLIC_BASE_URL=https://keepyourcontracts.com
INTAKE_TOKEN_SECRET=PASTE_GENERATED_SECRET_HERE
STRIPE_WEBHOOK_SECRET=PASTE_FROM_STRIPE_SIGNING_SECRET_HERE
OPS_API_KEY=PASTE_GENERATED_SECRET_HERE
```

### Generate strong secrets locally (Windows PowerShell)

Run **once** in PowerShell. Copy each output into Render (store in a password manager).

```powershell
# INTAKE_TOKEN_SECRET (32+ random bytes, base64)
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))

# OPS_API_KEY (48 random alphanumeric chars)
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
```

**Rules:**

- `INTAKE_TOKEN_SECRET` must **never** be `dev-dev-dev-dev-dev` (that is the dev default and fails live checks).
- `STRIPE_WEBHOOK_SECRET` must start with `whsec_` (Stripe signing secret from the webhook you create in Section 3).
- `OPS_API_KEY` is only for you — used as header `X-Ops-Key` on test ops routes in production.

### Remove dead variables

In the same **Environment** screen, **delete** any of these if present:

- `SHOPIFY_WEBHOOK_SECRET`
- `SHOPIFY_SECRET`
- Any other `SHOPIFY_*` key

**Optional (leave as-is if already set):** `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `DATABASE_URL` — not required for lock verification.

**Do not** run **Blueprint sync** from repo `render.yaml` during this task.

---

## 2. Render Deployment Verification

### Apply env and redeploy

1. Render Dashboard → **`kyc-backend`** → **Environment**
2. Confirm all five variables from Section 1 are saved
3. Click **Save Changes** (if not already saved)
4. Top right → **Manual Deploy** → **Deploy latest commit**
5. Wait until deploy status is **Live** (typically 2–5 minutes)

### Verify readiness (browser or PowerShell)

**URL:**  
https://jetfighter-compliance.onrender.com/health/ready

**Expected JSON (inside `checks`):**

| Field | Expected |
|-------|----------|
| `environment` | `"production"` |
| `intake_secret_configured` | `true` |
| `stripe_webhook_configured` | `true` |
| `public_base_url` | `https://keepyourcontracts.com` *(after `PUBLIC_BASE_URL` is set)* |

**Quick PowerShell check:**

```powershell
(Invoke-RestMethod "https://jetfighter-compliance.onrender.com/health/ready").checks | Format-List
```

**If any flag is still wrong:** env not saved, deploy not finished, or wrong secret pasted → fix env → **Manual Deploy** again.

**Also confirm:**

- https://jetfighter-compliance.onrender.com/healthz → JSON with `"ok": true`

---

## 3. Stripe Webhook Setup

### Dashboard path

1. [Stripe Dashboard](https://dashboard.stripe.com/) → **Developers** → **Webhooks**
2. **Add endpoint**

### Endpoint configuration

| Field | Value |
|-------|--------|
| **Endpoint URL** | `https://jetfighter-compliance.onrender.com/webhooks/stripe` |
| **Events** | Select **`checkout.session.completed`** only (or “Select events” → that one event) |

3. Click **Add endpoint**
4. On the new endpoint page → **Signing secret** → **Reveal** → copy value (`whsec_…`)

### Paste into Render

1. Render → **`kyc-backend`** → **Environment**
2. Set `STRIPE_WEBHOOK_SECRET` = pasted `whsec_…` value
3. **Save Changes** → **Manual Deploy** → **Deploy latest commit**

### Verify Stripe route (unsigned must fail with 401)

```powershell
try {
  Invoke-WebRequest "https://jetfighter-compliance.onrender.com/webhooks/stripe" -Method POST -Body "{}" -ContentType "application/json" -UseBasicParsing
  Write-Host "FAIL: should not return 2xx"
} catch {
  Write-Host "Status:" $_.Exception.Response.StatusCode.value__
}
```

| Status | Meaning |
|--------|---------|
| **401** | **PASS** — secret configured, signature check active |
| **503** | **FAIL** — `STRIPE_WEBHOOK_SECRET` missing or deploy not restarted |
| **200** | **FAIL** — misconfiguration; contact agent with status code |

### After custom domain is live (optional, recommended)

Add a **second** Stripe endpoint (or update URL) to:

`https://keepyourcontracts.com/webhooks/stripe`

Use the **new** signing secret in Render if Stripe issues a new `whsec_` for that endpoint. One active endpoint pointing at the URL customers use is enough for go-live.

---

## 4. Cloudflare + Render Custom Domain Setup

### A. Render — attach custom domains

1. Render Dashboard → **`kyc-backend`** → **Settings** → **Custom Domains**
2. **Add Custom Domain** → `keepyourcontracts.com` → follow Render instructions
3. **Add Custom Domain** → `www.keepyourcontracts.com` (recommended)
4. Note the **DNS target** Render shows (often a hostname like `jetfighter-compliance.onrender.com` or a `*.onrender.com` verify name — **use exactly what Render displays**)

### B. Cloudflare DNS

1. [Cloudflare Dashboard](https://dash.cloudflare.com/) → zone **`keepyourcontracts.com`** → **DNS** → **Records**

| Type | Name | Content / Target | Proxy |
|------|------|------------------|-------|
| **CNAME** | `@` (or `keepyourcontracts.com`) | *(Render target from step A)* | **DNS only (grey cloud)** recommended for first lock |
| **CNAME** | `www` | *(same Render target, or Render’s `www` target if different)* | **DNS only** recommended |

2. **SSL/TLS** → mode **Full (strict)** once Render certificate is issued

### C. Remove conflicting Cloudflare / parking

**You must clear anything that serves placeholder HTML instead of the KYC app.**

Check and **remove or disable**:

- **Cloudflare Pages** project bound to `keepyourcontracts.com` or `www`
- **Workers** routes on `@` or `www` serving static HTML
- **Redirect rules** / **Page Rules** sending `/` to a parking site
- Old **A/AAAA** records pointing at non-Render IPs
- Domain **parking** / “coming soon” templates

**Pass signal:**  
https://keepyourcontracts.com/healthz returns **JSON** `{"ok":true,...}` — **not** a large HTML landing page.

### D. Wait for propagation

- DNS: often 5–30 minutes; up to 48 hours in edge cases
- Render custom domain: **Verified** + certificate **Active** in Render UI

### E. Re-verify `PUBLIC_BASE_URL`

Confirm Render env still has:

`PUBLIC_BASE_URL=https://keepyourcontracts.com`

If you changed it during testing, fix and **Manual Deploy** once more.

---

## 5. Final Verification

From your machine:

```powershell
cd C:\Users\Carl\jetfighter_compliance
powershell -File scripts\verify-production-live.ps1
echo Exit: $LASTEXITCODE
```

### Success criteria

| Result | Meaning |
|--------|---------|
| **Exit code `0`** | All check groups passed — eligible for production lock |
| **Exit code `1`** | One or more groups failed — use Section 6 |

### What the verifier checks (summary)

| Check | Pass |
|-------|------|
| `/health/ready` | `environment` = `production` |
| Secrets | `intake_secret_configured` + `stripe_webhook_configured` = true |
| Stripe | Unsigned `POST /webhooks/stripe` → **401** |
| Ops guard | `POST /events/payment/test` without key → **403** |
| Custom domain | `https://keepyourcontracts.com/healthz` → JSON `ok: true` |
| Custom UI | `https://keepyourcontracts.com/ui/shop.html` → **200** |
| Inquiry smoke | Render inquiry → HTTPS intake URL (no localhost) |

---

## 6. Failure Diagnosis

Use the **first matching** row. Fix → **Manual Deploy** (if env changed) → re-run Section 5.

| Symptom | Classification | Fix |
|---------|----------------|-----|
| `/health/ready` still shows `"development"` | **Env not applied** | Set `ENVIRONMENT=production`, Save, Manual Deploy |
| `intake_secret_configured: false` | **Env not applied** | Set `INTAKE_TOKEN_SECRET` to new random value (not `dev-dev-dev-dev-dev`), redeploy |
| `stripe_webhook_configured: false` | **Env not applied** | Paste `whsec_…` into `STRIPE_WEBHOOK_SECRET`, redeploy |
| Stripe POST returns **503** | **Stripe secret missing** or **deploy not restarted** | Set secret + Manual Deploy |
| Stripe POST returns **200** | **Misconfiguration** | Stop; do not go live — report status to agent |
| `payment/test` returns **200** without header | **ENVIRONMENT not production** or **OPS_API_KEY unset** | Set both + redeploy |
| `keepyourcontracts.com/healthz` is HTML or empty | **Cloudflare still serving placeholder** | Remove Pages/Workers/parking; fix DNS to Render |
| `keepyourcontracts.com/ui/shop.html` → **404** | **Render custom domain not attached** or DNS wrong | Complete Section 4; wait for Render “Verified” |
| Render URL works but custom domain fails | **DNS not propagated** | Wait; confirm CNAME targets; grey-cloud DNS only |
| All env flags true but custom domain fails | **DNS / Cloudflare conflict** | Audit Section 4C; only one origin (Render) |
| Verifier passes Render checks only | **Custom domain incomplete** | Finish Section 4 before claiming lock |

---

## Rollback checklist

Use only if activation breaks production or you need to revert quickly.

| Step | Action |
|------|--------|
| 1 | Render → **`kyc-backend`** → **Environment** → set `ENVIRONMENT` = `development` → Save |
| 2 | **Manual Deploy** → wait for Live |
| 3 | Confirm ops/test routes behave as pre-lock (not for public marketing) |
| 4 | Stripe → **Webhooks** → **disable** or delete the new endpoint (stops live payment → kickoff) |
| 5 | Cloudflare → restore previous DNS only if you documented old records |
| 6 | Optional: remove custom domains in Render **Settings** → **Custom Domains** |
| 7 | Document what was rolled back and why before retrying activation |

**Note:** Rolling back `ENVIRONMENT` opens test routes — use only temporarily. Do not leave `development` on a public URL long term.

---

## 7. Owner Copy/Paste Checklist

Print or tick in order:

```
[ ] 1. Render → kyc-backend → Environment → set ENVIRONMENT=production
[ ] 2. Set PUBLIC_BASE_URL=https://keepyourcontracts.com
[ ] 3. Generate + set INTAKE_TOKEN_SECRET (not dev-dev-dev-dev-dev)
[ ] 4. Generate + set OPS_API_KEY
[ ] 5. Delete all SHOPIFY_* env vars
[ ] 6. Save Environment → Manual Deploy → Live
[ ] 7. Open /health/ready → production + both secrets true
[ ] 8. Stripe → Webhooks → Add endpoint → /webhooks/stripe → checkout.session.completed
[ ] 9. Copy whsec_ → STRIPE_WEBHOOK_SECRET on Render → Save → Manual Deploy
[ ] 10. Unsigned POST /webhooks/stripe → 401
[ ] 11. Render → Custom Domains → keepyourcontracts.com + www
[ ] 12. Cloudflare DNS CNAME → Render target; remove Pages/Workers/parking
[ ] 13. keepyourcontracts.com/healthz → JSON {"ok":true}
[ ] 14. keepyourcontracts.com/ui/shop.html → 200
[ ] 15. cd jetfighter_compliance → verify-production-live.ps1 → Exit 0
```

---

## 8. Next Step After Success

When:

```powershell
powershell -File scripts\verify-production-live.ps1
# Exit: 0
```

Then:

1. Tell the agent: **“Verifier passed — run Task 9 lock verification.”**
2. Agent will:
   - Re-run live lock verification (Task 9)
   - Update `purposeful-platform/docs/OPERATIONAL_FREEZE_RULES.md` → downgrade to **STABILIZED OPERATIONS MODE** (freeze protections remain; expansion rules still apply)
   - Update `purposeful-platform/docs/STABILIZATION_STATUS_MASTER.md`
   - Update `jetfighter_compliance/docs/KYC_PRODUCTION_LOCK_CONFIRMED.md` with **LOCK CONFIRMED** verdict

**Approved operational lane after lock:** maintenance, monitoring, and Owner-approved Phase 2 expansion only — no blueprint sync, no new canonical repos, no architecture redesign without explicit Owner approval.

---

## Reference URLs

| Resource | URL |
|----------|-----|
| Render readiness | https://jetfighter-compliance.onrender.com/health/ready |
| Render healthz | https://jetfighter-compliance.onrender.com/healthz |
| Custom healthz (target) | https://keepyourcontracts.com/healthz |
| Shop (target) | https://keepyourcontracts.com/ui/shop.html |
| Inquiry (target) | https://keepyourcontracts.com/ui/inquiry.html |
| Stripe webhook (initial) | https://jetfighter-compliance.onrender.com/webhooks/stripe |

**Related doc:** `docs/KYC_OWNER_ACTIVATION_CHECKLIST.md` (short summary) — this file is the **authoritative step-by-step** for Task 10.

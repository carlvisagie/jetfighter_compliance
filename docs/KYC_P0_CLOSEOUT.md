# KYC P0 Closeout — Live Deployment Activation

**Date:** 2026-05-19  
**Deploy commit:** `5492efa` on `carlvisagie/jetfighter_compliance` `main`  
**Render service:** `kyc-backend` → `https://jetfighter-compliance.onrender.com`  
**Probe time (UTC):** ~09:34

---

## 1. Deployment source of truth

| Item | Verified value |
|------|----------------|
| **GitHub repo** | `carlvisagie/jetfighter_compliance` |
| **Branch** | `main` |
| **Previous live commit** | `f54fa65` (docs only — **no stabilization code**) |
| **Activated commit** | `5492efa` — pushed 2026-05-19, Render autoDeploy |
| **Why live was old** | Stabilization work existed **only locally**; never pushed to `origin/main` |

**Conclusion:** Live host was correct service; **wrong revision**. Fixed by push + autoDeploy (~2 min to `/health/ready` 200).

---

## 2. Deployment activation — verified live routes

**Host:** `https://jetfighter-compliance.onrender.com`

| Route | Status | Live evidence |
|-------|--------|---------------|
| `GET /healthz` | **PASS** | `{"ok":true,"service":"kyc-backend"}` |
| `GET /health/ready` | **PASS** | `status: ready`, `data_writable: true` |
| `GET /ui/shop.html` | **PASS** | 200 |
| `GET /ui/inquiry.html` | **PASS** | 200 |
| `GET /upload` | **PASS** | 200 |
| `POST /api/inquiry/submit` | **PASS** | 200 + `project_id` + HTTPS `intake_url` |
| `POST /webhooks/stripe` | **ROUTE LIVE** | **503** `STRIPE_WEBHOOK_SECRET not configured` (expected until env set) |
| `POST /api/evidence/register` | **PASS** | 200 + artifact registered on disk |
| `POST /events/payment/test` | **PASS** | 200; `intake_url` uses Render HTTPS (not localhost) |

**Live inquiry → evidence probe (2026-05-19):**

1. `POST /api/inquiry/submit` → `P-INQ-20260519T093458Z-…`  
2. `POST /api/evidence/register` → `{"ok":true,"artifact":{…}}`

---

## 3. Environment activation

### Live readiness report (`/health/ready`)

```json
{
  "public_base_url": "https://jetfighter-compliance.onrender.com",
  "stripe_webhook_configured": false,
  "intake_secret_configured": false,
  "smtp_configured": false,
  "environment": "development"
}
```

`PUBLIC_BASE_URL` behavior: **OK on Render URL** via `RENDER_EXTERNAL_URL` (intake links correct without manual `PUBLIC_BASE_URL`).

### Owner must set on Render (`kyc-backend` → Environment)

| Variable | Status | Action |
|----------|--------|--------|
| `ENVIRONMENT` | **Not set** (shows `development`) | Set `production` |
| `INTAKE_TOKEN_SECRET` | **Default/dev** | Set strong random secret |
| `STRIPE_WEBHOOK_SECRET` | **Missing** | From Stripe Dashboard webhook |
| `OPS_API_KEY` | **Unknown** | Set random secret for ops test routes |
| `PUBLIC_BASE_URL` | **Optional** | `https://keepyourcontracts.com` after DNS fix |
| `SMTP_*` | **Off** | Enable for production emails |
| `SHOPIFY_*` | **Remove if present** | Dead |

Agent cannot set Render dashboard secrets; **dashboard action required**.

---

## 4. Stripe live activation

| Step | Status |
|------|--------|
| Route on live host | **YES** — 503 without secret (not 404) |
| Webhook in Stripe Dashboard | **OWNER** — register `https://jetfighter-compliance.onrender.com/webhooks/stripe` |
| Event type | `checkout.session.completed` |
| Live payment → kickoff | **BLOCKED** until `STRIPE_WEBHOOK_SECRET` set + test payment |

After secret set: expect **401** on unsigned POST, **200** on valid Stripe delivery.

---

## 5. Custom domain activation

| Domain | `/healthz` | Backend? |
|--------|------------|----------|
| `keepyourcontracts.com` | 200 **HTML** (empty) | **NO** — still wrong origin |
| `www.keepyourcontracts.com` | 200 **HTML** | **NO** |
| `jetfighter-compliance.onrender.com` | 200 **JSON** | **YES** |

**P0 DNS item remains open.** Render custom domain + Cloudflare CNAME to Render required (see `KYC_DOMAIN_RUNTIME_HARDENING.md`).

---

## 6. Full live flow verification

### Inquiry path (Render URL) — **VERIFIED LIVE**

```
/ui/shop.html → /ui/inquiry.html → POST /api/inquiry/submit
  → kickoff() → intake_url (HTTPS)
  → POST /api/evidence/register → artifact OK
```

Upload UI wiring deployed; evidence API verified with curl.

### Stripe path — **NOT VERIFIED END-TO-END**

Blocked on `STRIPE_WEBHOOK_SECRET` + Dashboard registration. Code path live (503 guard).

---

## 7. P0 closure status

| P0 item | Status |
|---------|--------|
| Deploy hardened build | **CLOSED** (`5492efa` live) |
| `/health/ready` live | **CLOSED** |
| `/api/inquiry/submit` live | **CLOSED** |
| `/webhooks/stripe` route live | **CLOSED** (env for signature pending) |
| Correct public intake URLs on Render host | **CLOSED** |
| `keepyourcontracts.com` → backend | **OPEN** (DNS) |
| Stripe payment → kickoff live | **OPEN** (env + Dashboard) |
| Production env hardening (`ENVIRONMENT`, secrets) | **OPEN** (dashboard) |

**Freeze rules:** May downgrade from **“deploy blocked”** to **“env + DNS completion”** — not full expansion unlock until custom domain + Stripe secret verified.

---

## 8. Rollback

| Action | How |
|--------|-----|
| Render deploy rollback | Dashboard → `kyc-backend` → Deploys → Rollback to `f54fa65` |
| Git revert | `git revert 5492efa` + push (triggers redeploy) |

---

## 9. Operational readiness verdict

| Surface | Verdict |
|---------|---------|
| **Render URL (`jetfighter-compliance.onrender.com`)** | **Production-ready for inquiry-led onboarding** (verified live) |
| **Stripe auto-onboarding** | **Not ready** until webhook secret + Dashboard |
| **Custom domain** | **Not ready** |
| **Overall P0** | **Substantially closed** — 3 Owner dashboard tasks remain |

---

## 10. Immediate Owner checklist (≤15 min)

1. Render → `kyc-backend` → Environment → set `ENVIRONMENT`, `INTAKE_TOKEN_SECRET`, `STRIPE_WEBHOOK_SECRET`, `OPS_API_KEY`.  
2. Stripe → Webhooks → add endpoint → copy secret to Render.  
3. Test inquiry on `https://jetfighter-compliance.onrender.com/ui/inquiry.html`.  
4. Render → Custom Domains → add `keepyourcontracts.com` → fix Cloudflare DNS.  
5. Re-probe `https://keepyourcontracts.com/healthz` → must be JSON.

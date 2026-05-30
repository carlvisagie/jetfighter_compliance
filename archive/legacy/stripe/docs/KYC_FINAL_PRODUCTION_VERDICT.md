> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KYC Final Production Verdict — Task 8

> **Superseded for launch decisions:** Use [`LAUNCH_PATH.md`](./LAUNCH_PATH.md) and [`README.md`](./README.md). This file is a historical probe snapshot; Stripe/Shopify/Cloudflare are not the active onboarding path.

**Probe date:** 2026-05-19 (UTC ~09:38)  
**Render host:** `https://jetfighter-compliance.onrender.com`  
**Custom domain:** `https://keepyourcontracts.com`  
**Deploy commit:** `5492efa` (`jetfighter_compliance` `main`)

---

## Executive verdict

| Layer | Status |
|-------|--------|
| **Hardened runtime on Render URL** | **OPERATIONAL** — inquiry → kickoff → evidence verified live |
| **Production configuration (env)** | **NOT ACTIVE** — readiness flags still show defaults |
| **Stripe live onboarding** | **NOT ACTIVE** — webhook secret missing; route returns 503 |
| **Custom domain** | **NOT ACTIVE** — does not hit KYC backend |
| **Full “production locked” state** | **NOT ACHIEVED** — Owner dashboard actions required |

**Task 8 success criteria:** **NOT MET** at time of probe (blockers unchanged since Task 7 closeout).

---

## 1. Live env activation verification

**Source:** `GET https://jetfighter-compliance.onrender.com/health/ready`

```json
{
  "ok": true,
  "status": "ready",
  "checks": {
    "data_writable": true,
    "projects_dir": true,
    "public_base_url": "https://jetfighter-compliance.onrender.com",
    "stripe_webhook_configured": false,
    "intake_secret_configured": false,
    "smtp_configured": false,
    "environment": "development"
  }
}
```

| Variable | Expected | Live | Verdict |
|----------|----------|------|---------|
| `ENVIRONMENT` | `production` | `development` | **FAIL** |
| `INTAKE_TOKEN_SECRET` | Strong secret | `intake_secret_configured: false` | **FAIL** |
| `STRIPE_WEBHOOK_SECRET` | Set | `stripe_webhook_configured: false` | **FAIL** |
| `OPS_API_KEY` | Set in prod | `POST /events/payment/test` → **200** without header | **FAIL** (guard not active) |
| `PUBLIC_BASE_URL` | Optional on Render | `RENDER_EXTERNAL_URL` used — HTTPS links OK | **PASS** |

**Agent note:** No `RENDER_API_KEY` in environment — Render dashboard changes must be applied by Owner.

---

## 2. Live Stripe activation verification

| Probe | Result |
|-------|--------|
| `POST /webhooks/stripe` (unsigned) | **503** `STRIPE_WEBHOOK_SECRET not configured` |
| Signature verification | **Cannot test** — secret not on host |
| kickoff from Stripe | **Cannot test** — Dashboard webhook not confirmed |

**Verdict:** Route exists (not 404) but **Stripe path NOT live**.

**Owner actions:**

1. Stripe Dashboard → Developers → Webhooks → Add endpoint:  
   `https://jetfighter-compliance.onrender.com/webhooks/stripe`  
   (after DNS: `https://keepyourcontracts.com/webhooks/stripe`)
2. Event: `checkout.session.completed`
3. Copy signing secret → Render `STRIPE_WEBHOOK_SECRET`
4. Re-probe: unsigned POST must return **401**, not 503

---

## 3. Live domain activation verification

| URL | Result | Backend? |
|-----|--------|----------|
| `keepyourcontracts.com/healthz` | 200, **empty HTML** | **NO** |
| `www.keepyourcontracts.com/healthz` | 200, **empty HTML** | **NO** |
| `keepyourcontracts.com/ui/shop.html` | **404** | **NO** |
| `keepyourcontracts.com/ui/inquiry.html` | **404** | **NO** |

**Verdict:** Custom domain **NOT** routed to `kyc-backend`.

**Pass condition:** `GET https://keepyourcontracts.com/healthz` → `{"ok":true,...}` (JSON).

---

## 4. Full live production flow (Render URL only)

**Verified live 2026-05-19:**

| Step | Result |
|------|--------|
| `POST /api/inquiry/submit` | 200, `project_id`, `intake_url`, `upload_url` |
| No localhost in links | **PASS** |
| `POST /api/evidence/register` | 200, artifact on disk |

**Not verified:** Same flow on `keepyourcontracts.com` (domain not on backend).  
**Not verified:** Stripe → webhook → kickoff (secret missing).

---

## 5. Freeze status

| Mode | Eligible? |
|------|-----------|
| P0 deploy block | **Lifted** (commit `5492efa` live) |
| **STABILIZED OPERATIONS MODE** | **NO** — env + Stripe + DNS open |
| Expansion / Phase 2 | **NO** |

See updated `purposeful-platform/docs/OPERATIONAL_FREEZE_RULES.md`.

---

## 6. Operational confidence

| Surface | Confidence |
|---------|------------|
| Render URL customer onboarding | **High** |
| Production security posture | **Low** (default intake secret, open test routes) |
| Stripe revenue → intake automation | **None** until webhook secret |
| Branded domain | **None** until DNS |

---

## 7. Remaining risks (verified)

| ID | Risk | Severity |
|----|------|----------|
| R1 | Default `INTAKE_TOKEN_SECRET` on live | **HIGH** |
| R2 | No Stripe webhook secret | **HIGH** |
| R3 | Custom domain wrong origin | **HIGH** |
| R4 | `ENVIRONMENT` not `production` — ops routes open | **MEDIUM** |

---

## 8. Recommended next lane (after Owner activation)

1. Run `scripts/verify-production-live.ps1` — must exit 0.  
2. One real Stripe Payment Link test → confirm project in `/api/projects`.  
3. Test inquiry on `https://keepyourcontracts.com/ui/inquiry.html`.  
4. Update `STABILIZATION_STATUS_MASTER.md` → **STABILIZED OPERATIONS MODE**.  
5. **Then** consider SAGE Phase 1 (Stadium) per `OPERATING_ALIGNMENT.md` — Owner-gated.

---

## 9. Owner activation checklist (copy-paste)

### Render → `kyc-backend` → Environment

```
ENVIRONMENT=production
INTAKE_TOKEN_SECRET=<generate 32+ random bytes>
STRIPE_WEBHOOK_SECRET=<from Stripe Dashboard>
OPS_API_KEY=<generate random>
PUBLIC_BASE_URL=https://keepyourcontracts.com   # after DNS live
```

Remove: `SHOPIFY_WEBHOOK_SECRET`, `SHOPIFY_SECRET` if present.

Save → Manual Deploy if required.

### Verify

```powershell
cd jetfighter_compliance
powershell -File scripts/verify-production-live.ps1
```

**Production locked** when script reports **ALL CHECKS PASSED**.

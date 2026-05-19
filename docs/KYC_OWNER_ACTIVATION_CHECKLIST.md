# KYC Owner Activation Checklist — Final P0

**Use after:** commit `5492efa` deployed to Render `kyc-backend`  
**Verify with:** `scripts/verify-production-live.ps1`

---

## A. Render environment (required)

Dashboard → **kyc-backend** → **Environment**:

| Key | Value |
|-----|--------|
| `ENVIRONMENT` | `production` |
| `INTAKE_TOKEN_SECRET` | *(strong random — not dev default)* |
| `STRIPE_WEBHOOK_SECRET` | *(from Stripe, below)* |
| `OPS_API_KEY` | *(random — for ops test routes)* |
| `PUBLIC_BASE_URL` | `https://keepyourcontracts.com` *(after DNS section C)* |

**Delete if present:** `SHOPIFY_WEBHOOK_SECRET`, `SHOPIFY_SECRET`

**Pass:** `GET .../health/ready` shows `environment: production`, `stripe_webhook_configured: true`, `intake_secret_configured: true`.

---

## B. Stripe Dashboard

1. Developers → Webhooks → **Add endpoint**  
2. URL: `https://jetfighter-compliance.onrender.com/webhooks/stripe`  
   - After DNS: prefer `https://keepyourcontracts.com/webhooks/stripe`  
3. Events: `checkout.session.completed`  
4. Copy **Signing secret** → Render `STRIPE_WEBHOOK_SECRET`

**Pass:** Unsigned `POST /webhooks/stripe` returns **401** (not 503).  
**Pass:** Test payment creates project (Stripe delivery log 200).

---

## C. Custom domain (Render + Cloudflare)

1. Render → **kyc-backend** → **Settings** → **Custom Domains** → Add `keepyourcontracts.com` and `www.keepyourcontracts.com`  
2. Cloudflare DNS → CNAME to Render target (remove parking/Pages/Workers on `@` and `www`)  
3. SSL: Full (strict)

**Pass:** `https://keepyourcontracts.com/healthz` → JSON `{"ok":true,...}`  
**Pass:** `https://keepyourcontracts.com/ui/shop.html` → 200

---

## D. Smoke test

1. Open `https://keepyourcontracts.com/ui/inquiry.html` (or Render URL until DNS done)  
2. Submit inquiry → receive intake link (HTTPS, not localhost)  
3. Complete intake → upload test file  
4. Optional: Stripe Payment Link → confirm webhook + new `P-…` project

---

## E. Run verifier

```powershell
powershell -File scripts/verify-production-live.ps1
```

Exit code **0** = eligible for **STABILIZED OPERATIONS MODE**.

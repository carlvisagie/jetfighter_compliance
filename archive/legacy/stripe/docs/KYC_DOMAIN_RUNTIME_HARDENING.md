> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KeepYourContracts — Domain + Runtime Hardening

**Date:** 2026-05-19  
**Mode:** Stabilization — custom domain truth, Stripe kickoff, upload wiring  
**Live backend:** `https://jetfighter-compliance.onrender.com` (Render `kyc-backend`, Docker)

---

## Verified domain topology

| Host | DNS target | Serves KYC FastAPI? | Evidence |
|------|------------|---------------------|----------|
| `jetfighter-compliance.onrender.com` | `gcp-us-west1-1.origin.onrender.com` (Render) | **Yes** | `GET /healthz` → `application/json` `{"ok":true}` |
| `keepyourcontracts.com` | Cloudflare `104.21.28.220`, `172.67.147.184` | **No** | `GET /healthz` → empty `text/html`; not JSON |
| `www.keepyourcontracts.com` | Same Cloudflare anycast | **No** | `/ui/shop.html` → **404** |

**Conclusion:** `keepyourcontracts.com` is **not** routed to the Render `kyc-backend` service. It hits a **different Cloudflare origin** (placeholder / parked HTML titled `keepyourcontracts.com`). The compliance app is healthy only on the **Render hostname** until DNS/custom domain is fixed in dashboard.

---

## Route probe matrix (2026-05-19)

| Path | Render URL | keepyourcontracts.com |
|------|------------|------------------------|
| `/healthz` | 200 JSON `{"ok":true}` | 200 **HTML** (wrong app) |
| `/ui/shop.html` | 200 (real shop) | **404** |
| `/shop.html` | 302 → `/ui/shop.html` | 200 **placeholder** (wrong app) |
| `/` | 302 → `/ui/shop.html` | 200 **placeholder** |
| `/ui/inquiry.html` | 200 | **404** |

**Path mismatch on custom domain is not a FastAPI mount bug** — the domain never reaches FastAPI.

---

## DNS findings

```
keepyourcontracts.com     → 104.21.28.220, 172.67.147.184 (Cloudflare proxy)
jetfighter-compliance.onrender.com → gcp-us-west1-1.origin.onrender.com → 216.24.57.x
```

No CNAME from `keepyourcontracts.com` → `*.onrender.com` observed.

---

## Cloudflare findings

- Domain is **proxied through Cloudflare** (CF-Ray headers on responses).
- Current origin serves **non-KYC HTML** (generic `no-js` template), not `server.py` static mount.
- Likely causes: **Pages**, **Workers**, **forwarding URL**, or **A record to wrong host** — **DASHBOARD_VERIFY** in Cloudflare DNS + Rules.

---

## Render findings

| Item | Value |
|------|--------|
| Service | `kyc-backend` |
| Health | `/healthz` |
| Runtime | Docker, uvicorn port 10000 |
| Custom domain | **Not verified attached** to `keepyourcontracts.com` in this audit (HTTP proves not live) |

Render auto-sets `RENDER_EXTERNAL_URL` → code now uses this when `PUBLIC_BASE_URL` is localhost default.

---

## Route normalization (code — deployment-safe)

Applied in `server.py` for when domain points at Render:

| Route | Behavior |
|-------|----------|
| `GET /` | 302 → `/ui/shop.html` |
| `GET /shop.html` | 302 → `/ui/shop.html` |
| `GET /inquiry.html` | 302 → `/ui/inquiry.html` |
| `GET /upload` | `upload.html` |
| `GET /ui/upload.html` | explicit alias |
| Static | `/ui/*` → `ui/` |

---

## Stripe continuity

| Item | Status |
|------|--------|
| Payment Links in `ui/shop.html` | `buy.stripe.com/…` (3 products) |
| Webhook | **`POST /webhooks/stripe`** |
| Event | `checkout.session.completed` |
| Verify | HMAC `Stripe-Signature` + `STRIPE_WEBHOOK_SECRET` |
| Action | `kickoff()` (idempotent on session id) |
| SKU map | Payment Link slug → SKU in `services/stripe_hook.py` |

**Owner setup (Stripe Dashboard):**

1. Developers → Webhooks → Add endpoint: `https://jetfighter-compliance.onrender.com/webhooks/stripe` (or custom domain once live).
2. Event: `checkout.session.completed`.
3. Copy signing secret → Render env `STRIPE_WEBHOOK_SECRET`.
4. Optional: add `metadata.sku` on each Payment Link for explicit SKU.

---

## Upload / evidence normalization

| Item | Status |
|------|--------|
| API | `POST /api/evidence/register?project_id=…&media_type=…&owner=…` + multipart `file` |
| UI | `ui/upload.html` wired — reads `?project_id=` or `?token=` (via `/api/intake/resolve`) |
| Intake handoff | `intake.js` offers redirect to `upload_url` after submit |
| Kickoff email | Includes intake + upload URLs |

---

## Minimal deployment-safe domain fix (Owner)

**Not a code change** — Render + Cloudflare alignment:

1. **Render** → `kyc-backend` → Settings → Custom Domains → Add `keepyourcontracts.com` and `www.keepyourcontracts.com`.
2. **Cloudflare DNS** → CNAME `@` and `www` to Render-provided target (or disable conflicting Page/Worker).
3. **Remove** conflicting A records / parking / redirect rules.
4. Set **`PUBLIC_BASE_URL=https://keepyourcontracts.com`** on Render (after SSL active).
5. Re-probe: `/healthz` must return **JSON**, `/ui/shop.html` must return **KeepYourContracts** shop title.

---

## Rollback

- Revert DNS to previous Cloudflare target if custom domain breaks other services.
- Stripe webhook can be disabled in Stripe Dashboard without code rollback.
- Upload script is additive; removing `<script>` block restores prior static-only page.

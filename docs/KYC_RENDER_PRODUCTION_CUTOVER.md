# KYC Render Production Cutover (Task 24)

**Date:** 2026-05-19  
**Canonical production backend:** `https://jetfighter-compliance.onrender.com`  
**Render service:** `kyc-backend` (Docker, `render.yaml`)

---

## Executive summary

KeepYourContracts production runs on **Render**, the same operational model as Just Talk (hosted service, not a Windows laptop + tunnel). **Cloudflare Tunnel and local `cloudflared` are dev/emergency only** — not required for customer traffic.

| Runtime | Role |
|---------|------|
| **Render** (`jetfighter-compliance.onrender.com`) | **Canonical production** |
| Local uvicorn + tunnel | Dev, debugging, emergency only |
| `compliance.keepyourcontracts.com` | **Branded DNS** → should CNAME to Render (not tunnel) |

---

## 1. Render production surface (verified)

Run:

```powershell
powershell -File scripts/verify-render-production.ps1
```

**Required endpoints (all on Render host):**

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness |
| `GET /health/ready` | Readiness + `public_base_url` |
| `GET /ui/shop.html` | Service catalog |
| `GET /ui/inquiry.html` | Readiness review / inquiry |
| `GET /ui/intake.html` | Client intake |
| `GET /ui/upload.html` | Evidence upload UI |
| `GET /upload` | Upload alias |
| `POST /api/inquiry/submit` | Inquiry → kickoff |
| `GET /api/intake/resolve` | Token resolve |
| `POST /api/intake/submit` | Intake form |
| `POST /api/evidence/register` | Evidence upload |

---

## 2. Production vs local (policy)

### Production (always)

- Deploy from `carlvisagie/jetfighter_compliance` → `main` → Render auto-deploy  
- Set env on Render Dashboard (`ENVIRONMENT`, `PUBLIC_BASE_URL`, secrets)  
- Use Render URL for smoke tests until custom domain is live  

### Local / tunnel (never for production customers)

| Tool | Allowed use |
|------|-------------|
| `uvicorn` on Windows | Local dev only |
| `cloudflared` / `.cloudflared/*.yml` | Temporary dev preview only |
| `start_everything.ps1`, `run_tunnel.ps1` | **Not** production path |

**Do not** point `compliance.keepyourcontracts.com` or `keepyourcontracts.com` at a tunnel hostname for production.

---

## 3. DNS — `compliance.keepyourcontracts.com` → Render

### Goal

Branded host serves the **same** FastAPI app as Render (static `/ui`, APIs, health).

### Step A — Add custom domain in Render

1. [Render Dashboard](https://dashboard.render.com/) → service **`kyc-backend`**
2. **Settings** → **Custom Domains**
3. Add:
   - `compliance.keepyourcontracts.com`
   - (optional) `www.keepyourcontracts.com` if used for marketing root
4. Copy Render’s target (typically a **CNAME** to `*.onrender.com` or A records Render provides)

### Step B — Cloudflare DNS (recommended)

1. Cloudflare → zone **`keepyourcontracts.com`**
2. **DNS** → **Add record**
3. Example (verify exact target in Render UI):

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `compliance` | `<your-service>.onrender.com` | DNS only or Proxied (see note) |

4. **Remove** any CNAME pointing `compliance` → `*.cfargotunnel.com` (tunnel)
5. **Remove** parking / Pages rules that override `compliance` or apex

**Proxy note:** Orange-cloud (proxied) is OK if SSL mode is **Full (strict)** and Render validates the custom hostname. If cert errors occur, try DNS-only (grey cloud) first.

### Step C — Environment on Render

Set:

```env
PUBLIC_BASE_URL=https://compliance.keepyourcontracts.com
```

(or `https://keepyourcontracts.com` if apex is the primary customer URL)

Save → **Manual Deploy** → re-run verifier.

### Step D — Verify

```powershell
powershell -File scripts/verify-render-production.ps1
# Optional branded check:
Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz
```

Expect JSON: `{"ok":true,"service":"kyc-backend"}`.

---

## 4. Cloudflare Tunnel — not for production

| Item | Action |
|------|--------|
| `bin/cloudflared.exe` | Keep for local dev if needed; do not document as prod |
| `.cloudflared/config-*.yml` | **Do not commit**; gitignore if present locally |
| Tunnel autostart scripts | Label **dev only** in runbooks |

Production traffic path:

```text
Customer → DNS (compliance.keepyourcontracts.com) → Render kyc-backend
```

Not:

```text
Customer → DNS → Cloudflare Tunnel → Windows PC  ❌
```

---

## 5. Related verifiers

| Script | When |
|--------|------|
| `scripts/verify-render-production.ps1` | **Task 24** — Render canonical surface (no tunnel) |
| `scripts/verify-production-live.ps1` | Full lock (env, Stripe, apex domain) |

---

## 6. Documentation updates (Task 24)

| Doc | Change |
|-----|--------|
| `docs/README.md` | Production runtime = Render |
| `docs/AGENTS.md` | Canonical URL + tunnel policy |
| `generate_qr.py` | Default public URL → Render (until DNS cutover) |

---

## 7. Verification run (2026-05-19)

```powershell
powershell -File scripts/verify-render-production.ps1
# exit 0
```

| Check | Result |
|-------|--------|
| `GET /healthz` | PASS |
| `GET /ui/shop.html`, `intake.html`, `inquiry.html`, `upload.html` | PASS (shared CSS) |
| `GET /upload` | PASS |
| `GET /api/intake/resolve` | PASS (401 bad token) |
| `POST /api/inquiry/submit` | PASS (HTTPS intake_url on Render host) |
| `POST /api/evidence/register` | PASS (422 validation) |
| `/health/ready` | `public_base_url` = Render URL; `ENVIRONMENT` still `development` (owner: set `production` on Render) |

---

## 8. Success criteria

| Criterion | Status |
|-----------|--------|
| Render serves health, UI, inquiry, upload APIs | **PASS** (verifier exit 0) |
| Docs state Render = production | **Done** |
| DNS instructions for compliance subdomain | **Done** |
| Tunnel not required for production | **Documented** |
| No secrets committed | **Done** |
| Pushed to `origin/main` | Pending |

---

## 9. Alignment with Just Talk

| Pattern | Just Talk | KeepYourContracts (KYC) |
|---------|-----------|-------------------------|
| Production host | Render / managed URL | `jetfighter-compliance.onrender.com` |
| Local tunnel for prod | No | **No** (after Task 24) |
| Health probe | `/health` or similar | `/healthz` |
| Static UI | Hosted on service | `/ui/*` on same service |

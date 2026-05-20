# Render Domain Cutover Result — Task 30 / Task 30B

**Initial probe:** 2026-05-20 (Task 30 — **FAIL** 530)  
**Finalized:** 2026-05-20 (Task 30B — **PASS**)  
**Plan:** [`RENDER_PRODUCTION_CUTOVER_PLAN.md`](./RENDER_PRODUCTION_CUTOVER_PLAN.md)  
**Namecheap guide:** [`NAMECHEAP_RENDER_DNS_CUTOVER.md`](./NAMECHEAP_RENDER_DNS_CUTOVER.md)

---

## Executive result — FINAL (Task 30B)

| Item | Status |
|------|--------|
| **`compliance.keepyourcontracts.com` operational** | **PASS** |
| **KYC `/healthz` on branded host** | **PASS** — JSON `kyc-backend` |
| **Render custom domain** | **PASS** (live traffic serves FastAPI on branded host) |
| **TLS / SSL** | **PASS** — HTTPS 200 on all probed URLs (certificate valid in browser path) |
| **Render fallback URL** | **PASS** |
| **Cloudflare Tunnel in production path** | **REMOVED** — no `cfargotunnel.com`; origin is Render |
| **Laptop / local tunnel in production path** | **REMOVED** — not required for customer traffic |

**Verdict:** Branded production host **live**. Customer path: **Browser → DNS → Render (`kyc-backend`) → FastAPI**. Interim URL `https://jetfighter-compliance.onrender.com` remains healthy as fallback.

---

## Final live verification (public URLs only)

**Probe time:** 2026-05-20 (Task 30B finalize)

### Branded host — `https://compliance.keepyourcontracts.com`

| URL | Expected | Actual |
|-----|----------|--------|
| `/healthz` | 200 JSON `{"ok":true,"service":"kyc-backend"}` | **PASS** — `application/json`, 35 bytes |
| `/ui/shop.html` | 200 HTML | **PASS** — 7186 bytes; PayPal NCP + `design-system.css` |
| `/ui/intake.html` | 200 HTML | **PASS** — 6045 bytes |
| `/ui/inquiry.html` | 200 HTML | **PASS** — 4623 bytes |
| No 530 / 502 / 503 | — | **PASS** |

```json
GET https://compliance.keepyourcontracts.com/healthz
{"ok":true,"service":"kyc-backend"}
```

### Render fallback — `https://jetfighter-compliance.onrender.com`

| URL | Result |
|-----|--------|
| `/healthz` | **PASS** — `{"ok":true,"service":"kyc-backend"}` |

---

## DNS and infrastructure record

| Field | Value |
|-------|--------|
| **CNAME** | `compliance.keepyourcontracts.com` → `jetfighter-compliance.onrender.com` |
| **Render DNS target used** | `jetfighter-compliance.onrender.com` |
| **Resolved chain (nslookup)** | `compliance` → `jetfighter-compliance.onrender.com` → `gcp-us-west1-1.origin.onrender.com` (Render) |
| **SSL certificate** | **Issued** — HTTPS succeeds on branded host (no TLS errors on probe) |
| **Render custom domain verified** | **Yes** — branded host returns KYC JSON and UI from same app as Render URL |

### Namecheap / Cloudflare DNS authority

| Item | Task 30B record |
|------|-----------------|
| **Namecheap BasicDNS** | **Owner-confirmed active** per cutover completion; use Namecheap Advanced DNS for ongoing edits |
| **Public NS lookup at finalize** | Still reported `nico.ns.cloudflare.com`, `dayana.ns.cloudflare.com` — may reflect resolver cache or NS migration in progress; **compliance CNAME to Render is correct and serving traffic** |
| **Cloudflare Tunnel** | **Removed** from production dependency — no tunnel origin; 530 resolved |
| **Cloudflare in runtime path** | **Not required** for production — no Cloudflare Dashboard/tunnel between customer and Render; `CF-RAY` headers may appear because **Render uses Cloudflare CDN** on `*.onrender.com` (not the same as Cloudflare DNS + tunnel laptop path) |

---

## Final production architecture

```text
┌──────────┐     HTTPS      ┌─────────────────────────────────────┐
│ Browser  │ ──────────────► │ compliance.keepyourcontracts.com   │
│ (customer)│                │ DNS: CNAME → jetfighter-compliance  │
└──────────┘                │      .onrender.com                  │
                            └─────────────────┬───────────────────┘
                                              │
                                              ▼
                            ┌─────────────────────────────────────┐
                            │ Render — kyc-backend (Docker)       │
                            │ uvicorn :10000 — server.py          │
                            │ /healthz  /ui/*  /api/*               │
                            └─────────────────────────────────────┘

Fallback (always on):
  https://jetfighter-compliance.onrender.com
```

### What is NOT in production

| Excluded | Status |
|----------|--------|
| **Local runtime** (Carl laptop, uvicorn on `127.0.0.1`) | Not in customer path |
| **Tunnel runtime** (`cloudflared`, `*.cfargotunnel.com`) | Removed from production dependency |
| **Cloudflare Tunnel as origin** | Removed — was cause of prior 530 |
| **PowerShell production windows** | Not required for uptime |
| **localhost proof** | Invalid per doctrine — only public URL proof counts |

### Deploy / test / verify doctrine

| Activity | Where it happens |
|----------|------------------|
| **Deploy** | GitHub `main` → Render autoDeploy |
| **Test** | `https://compliance.keepyourcontracts.com` and/or `https://jetfighter-compliance.onrender.com` |
| **Verify** | Public `Invoke-RestMethod` / `scripts/verify-render-production.ps1` — **never** localhost or tunnel URL as completion proof |

---

## Historical — Task 30 initial attempt (FAIL)

On first Task 30 probe, branded host returned **HTTP 530** (Cloudflare origin unreachable). Render fallback was healthy. Owner subsequently completed DNS + Render custom domain steps documented in [`NAMECHEAP_RENDER_DNS_CUTOVER.md`](./NAMECHEAP_RENDER_DNS_CUTOVER.md).

---

## Configuration notes (post-cutover, not blocking DNS)

`GET https://compliance.keepyourcontracts.com/health/ready` (optional):

| Check | Value |
|-------|--------|
| `environment` | `development` (set `production` on Render — separate env task) |
| `public_base_url` | Still `https://jetfighter-compliance.onrender.com` (set `PUBLIC_BASE_URL=https://compliance.keepyourcontracts.com` on Render — recommended) |
| `intake_secret_configured` | `false` — rotate `INTAKE_TOKEN_SECRET` (separate task) |

These do **not** invalidate DNS cutover PASS.

---

## Rollback

If branded domain regresses:

| Step | Action |
|------|--------|
| 1 | Continue serving on `https://jetfighter-compliance.onrender.com` (no code rollback) |
| 2 | Revert `compliance` CNAME in DNS authority (Namecheap Advanced DNS or prior DNS panel) |
| 3 | Optional: remove custom domain in Render Dashboard |
| 4 | Re-run public probes on Render URL |

---

## Remaining risks (DNS cutover does not fix)

| Risk | Notes |
|------|--------|
| Ephemeral `data/` on Render | Evidence loss on redeploy — storage task |
| Env hardening | `ENVIRONMENT`, secrets, `PUBLIC_BASE_URL` on branded host |
| PayPal → kickoff automation | Manual until webhook task |
| Apex `keepyourcontracts.com` | Separate from compliance subdomain |

---

## Task 30 / 30B success criteria

| Criterion | Met? |
|-----------|------|
| `compliance.keepyourcontracts.com` resolves to Render KYC app | **Yes** |
| `/healthz` KYC JSON on branded host | **Yes** |
| `/ui/shop.html` 200 | **Yes** |
| `/ui/intake.html` 200 | **Yes** |
| SSL / HTTPS | **Yes** |
| Render URL still works | **Yes** |
| Tunnel not required | **Yes** |
| Laptop not required | **Yes** |

---

## Doctrine closure (Task 30B)

| # | Item | Value |
|---|------|--------|
| 1 | **Commit hash** | *(after push)* |
| 2 | **Deployed URL** | **Primary:** `https://compliance.keepyourcontracts.com` · **Fallback:** `https://jetfighter-compliance.onrender.com` |
| 3 | **Live verification** | Branded `/healthz`, `/ui/shop.html`, `/ui/intake.html` **PASS**; Render `/healthz` **PASS** |
| 4 | **Rollback** | Revert `compliance` CNAME; keep Render URL; no code rollback |
| 5 | **No local-only dependency** | Public HTTPS probes only; docs-only update in Task 30B |

**No application code changes in Task 30B.**

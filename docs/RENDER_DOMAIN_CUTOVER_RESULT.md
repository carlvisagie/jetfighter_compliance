# Render Domain Cutover Result — Task 30

**Date:** 2026-05-20  
**Scope:** DNS + Render custom domain only (no code, tunnel, Blueprint, or storage changes)  
**Plan:** [`RENDER_PRODUCTION_CUTOVER_PLAN.md`](./RENDER_PRODUCTION_CUTOVER_PLAN.md)

---

## Executive result

| Item | Status |
|------|--------|
| **Branded domain cutover** | **NOT COMPLETE** |
| **`compliance.keepyourcontracts.com` → KYC on Render** | **FAIL** — HTTP **530** on all probes |
| **Render fallback URL** | **PASS** |
| **Agent could execute dashboard steps** | **No** — Render + Cloudflare require Owner credentials |

**Verdict:** Task 30 **live verification failed** for the branded host. Production traffic must continue on `https://jetfighter-compliance.onrender.com` until Owner completes §Owner actions below.

---

## What the agent verified (public URL only)

Probe time: **2026-05-20** (UTC, from agent environment)

### Branded host — `https://compliance.keepyourcontracts.com`

| URL | Expected | Actual |
|-----|----------|--------|
| `/healthz` | 200 JSON `{"ok":true,"service":"kyc-backend"}` | **530** |
| `/ui/shop.html` | 200 HTML | **530** |
| `/ui/inquiry.html` | 200 HTML | **530** |
| `/ui/intake.html` | 200 HTML | **530** |
| `/ui/upload.html` | 200 HTML | **530** |

**530 interpretation:** Cloudflare edge receives the request but **cannot reach a valid origin** (tunnel removed, wrong CNAME, missing Render custom domain, or SSL/origin mismatch). **Not** the KYC FastAPI app.

Sample response: `Server: cloudflare`, `CF-RAY` present, status **530**, empty body — origin unreachable from Cloudflare.

### Render fallback — `https://jetfighter-compliance.onrender.com`

| URL | Result |
|-----|--------|
| `/healthz` | **200** `Content-Type: application/json` → `{"ok":true,"service":"kyc-backend"}` |

Rollback URL remains healthy.

### DNS (public resolver)

```
compliance.keepyourcontracts.com → 104.21.28.220, 172.67.147.184 (Cloudflare anycast)
```

- Traffic hits **Cloudflare proxy**, not Render directly.
- Public CNAME to `*.onrender.com` **not visible** (typical when proxied or origin misconfigured).
- **Render DNS target used:** **UNKNOWN** — not set in this session (dashboard not accessible to agent).

### Cloudflare DNS record used

| Field | Value |
|-------|--------|
| Name | `compliance` |
| Type | **Should be** `CNAME` |
| Target | **`<COPY FROM RENDER DASHBOARD>`** — not applied yet |
| Proxy | **Should start grey cloud (DNS only)** per plan — current state appears **proxied** (CF anycast) |

### Render custom domain (dashboard)

| Field | Value |
|-------|--------|
| Service | `kyc-backend` |
| Domain to add | `compliance.keepyourcontracts.com` |
| Verification in Render | **Not confirmed** by agent |
| Certificate issued | **Not confirmed** |

---

## Owner actions required (blocking)

Complete in order. **Do not guess the CNAME target.**

### Step 1 — Render Dashboard

1. Open https://dashboard.render.com/ → service **`kyc-backend`**
2. **Settings** → **Custom Domains** → **Add Custom Domain**
3. Enter: `compliance.keepyourcontracts.com`
4. **Copy exactly** the DNS record Render displays (name + type + target)
5. Wait until Render shows domain **Verified** and certificate **Issued**

Record here after completion:

```text
Render CNAME target (paste from dashboard): ___________________________.onrender.com
Render verification status: ___________________________
```

### Step 2 — Cloudflare Dashboard

Zone: `keepyourcontracts.com`

| Action | Detail |
|--------|--------|
| **DELETE** | Any `compliance` → `*.cfargotunnel.com` |
| **DELETE** | Stale tunnel / wrong origin records for `compliance` |
| **REVIEW** | Workers, Pages, Rules overriding `compliance.*` |
| **CREATE/UPDATE** | `CNAME` `compliance` → **exact Render target from Step 1** |
| **PROXY** | **DNS only (grey cloud)** for first pass |

### Step 3 — Re-verify (public URLs)

After Render shows verified + DNS propagated (5–60 min):

```powershell
Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/shop.html -UseBasicParsing
Invoke-RestMethod https://jetfighter-compliance.onrender.com/healthz
```

**Pass:** `/healthz` returns JSON with `"service":"kyc-backend"`; UI pages **200**; no **530**.

### Step 4 — Optional env (not Task 30 code)

On Render → Environment (Owner, separate task):

```text
PUBLIC_BASE_URL=https://compliance.keepyourcontracts.com
```

Manual deploy after change. Not required for DNS cutover proof.

---

## Proxy status recommendation

| Phase | Cloudflare proxy |
|-------|------------------|
| **First pass (now)** | Grey cloud — DNS only |
| **After green `/healthz` JSON** | Orange cloud optional with SSL **Full (strict)** |

If 530 persists with orange cloud, revert to grey and re-test.

---

## Rollback (if branded domain fails)

| Step | Action |
|------|--------|
| 1 | **Keep** `https://jetfighter-compliance.onrender.com` — already healthy |
| 2 | Cloudflare: remove or revert `compliance` CNAME to previous value |
| 3 | Render: remove custom domain if needed |
| 4 | No git/code rollback |
| 5 | Point customers to Render URL until DNS fixed |

---

## Remaining risks (after cutover succeeds)

| Risk | Notes |
|------|--------|
| Ephemeral `data/` on Render | Evidence loss on redeploy — **not fixed** by DNS (see audit P0-1) |
| `ENVIRONMENT=development` on live | Env hardening separate task |
| PayPal manual kickoff | No webhook wired — separate task |
| Apex `keepyourcontracts.com` | Still wrong origin — not in Task 30 scope |
| Untracked `paypal_hook.py` / `storage.py` | Deferred per Task 29 |

---

## Task 30 success criteria scorecard

| Criterion | Met? |
|-----------|------|
| `compliance.keepyourcontracts.com` resolves to Render app | **No** (530) |
| `/healthz` returns KYC JSON on branded host | **No** |
| UI pages 200 on branded host | **No** |
| Local tunnel irrelevant | **Yes** (not used in probe path) |
| Render URL still works | **Yes** |

**Re-run Task 30 verification** after Owner completes dashboard steps; update this doc with pass/fail table and paste Render CNAME target.

---

## Doctrine closure (Task 30 — doc commit)

| # | Item | Value |
|---|------|--------|
| 1 | Commit hash | *(filled after doc push)* |
| 2 | Deployed URL | `https://jetfighter-compliance.onrender.com` (fallback **PASS**); branded **FAIL** |
| 3 | Live verification | Branded **530**; Render `/healthz` **PASS** |
| 4 | Rollback | DNS revert only; see §Rollback |
| 5 | No local-only dependency | Public HTTP probes only |

**No code/runtime changes** in Task 30.

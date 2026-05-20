# Render Production Cutover — Execution Plan (Task 28)

**Date:** 2026-05-20  
**Mode:** Plan only — **no code, DNS, Render dashboard, or tunnel changes in Task 28**  
**Doctrine:** [`PRODUCTION_ENGINEERING_DOCTRINE.md`](./PRODUCTION_ENGINEERING_DOCTRINE.md)  
**Evidence base:** [`BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md`](./BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md), live probes 2026-05-20

---

## 1. Executive summary

| State | Host | Role |
|-------|------|------|
| **Current canonical (working)** | `https://jetfighter-compliance.onrender.com` | Render `kyc-backend` — only host that serves KYC today |
| **Target branded production** | `https://compliance.keepyourcontracts.com` | Customer-facing URL after DNS + Render custom domain |
| **Not production** | localhost, `cloudflared`, Carl laptop, PowerShell launchers | Dev / emergency only |

**Next execution task** can follow this document step-by-step without guessing. Cutover is **primarily dashboard + DNS**; Render URL stays live as fallback throughout.

**Out of scope for this cutover plan (separate tasks):** S3/R2 persistent storage, PayPal webhook code, `engine.py` scheduler fix, stale doc purge, Render Blueprint sync.

---

## 2. Current state (inspected 2026-05-20)

### 2.1 Render production service

| Item | Value | Source |
|------|--------|--------|
| **Service name** | `kyc-backend` | `render.yaml` |
| **Type** | Web service, Docker | `render.yaml` |
| **Plan** | `starter` | `render.yaml` |
| **Repo** | `carlvisagie/jetfighter_compliance` | docs / git remote |
| **Branch** | `main` (assumed; confirm in Render Dashboard → Settings) | `autoDeploy: true` in `render.yaml` |
| **Start command** | `uvicorn server:app --host 0.0.0.0 --port 10000` | `Dockerfile` CMD |
| **Health check path** | `GET /healthz` | `render.yaml` `healthCheckPath` |
| **Port** | `10000` (`PORT` env set in Dockerfile) | `Dockerfile` |
| **Blueprint sync** | **Not performed** per stabilization rules | Owner rule; dashboard may ≠ `render.yaml` |

**Live health (Render URL):**

```http
GET https://jetfighter-compliance.onrender.com/healthz
→ 200 application/json {"ok":true,"service":"kyc-backend"}
```

**Live readiness:**

```json
GET https://jetfighter-compliance.onrender.com/health/ready
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

**Gap:** `render.yaml` sets `ENVIRONMENT=production` but **live dashboard shows `development`** — treat **dashboard** as runtime truth until synced.

### 2.2 Static UI routes (Render URL — verified)

| Route | Status | Notes |
|-------|--------|-------|
| `GET /` | 302 → `/ui/shop.html` | `server.py` |
| `GET /ui/shop.html` | 200 | PayPal NCP links ×5, QR assets present |
| `GET /ui/inquiry.html` | 200 | Shared CSS |
| `GET /ui/intake.html` | 200 | Shared CSS |
| `GET /ui/upload.html` | 200 | Wired to `POST /api/evidence/register` |
| `GET /upload` | 200 | Alias to upload UI |
| `GET /ui/*` | Static mount | `ui/` directory in image |

### 2.3 API routes (production-critical)

| Route | Method | Behavior (current code) |
|-------|--------|-------------------------|
| `/api/inquiry/submit` | POST | Saves inquiry → `kickoff()` → intake URL |
| `/api/intake/resolve` | GET | Token validation (401 bad token) |
| `/api/intake/submit` | POST | Intake form → project communications |
| `/api/evidence/register` | POST | Multipart upload → `data/projects/{id}/evidence/` **local container disk** |
| `/events/payment/test` | POST | Ops kickoff — **open without key** when `ENVIRONMENT≠production` |
| `/webhooks/stripe` | POST | 503 if `STRIPE_WEBHOOK_SECRET` unset |
| `/healthz`, `/health/ready` | GET | Liveness / readiness |

**Upload/evidence today:** Files written under ephemeral `data/` on the container. Survives process restart on **same** instance; **not** guaranteed across redeploy (see audit P0-1). Cutover does not fix storage — flag for Task 29+.

### 2.4 Environment variables

| Variable | In `render.yaml`? | Live (2026-05-20) | Required for cutover |
|----------|-------------------|-------------------|----------------------|
| `ENVIRONMENT` | `production` (blueprint) | **`development`** | **Yes** → must be `production` on dashboard |
| `PUBLIC_BASE_URL` | No | Falls back to `RENDER_EXTERNAL_URL` | **Yes** → `https://compliance.keepyourcontracts.com` after DNS |
| `INTAKE_TOKEN_SECRET` | No | Default (not configured) | **Yes** — strong secret |
| `OPS_API_KEY` | No | Unset | **Yes** — blocks test routes in prod |
| `STRIPE_WEBHOOK_SECRET` | sync false | Unset | **No** for PayPal-first cutover (optional legacy) |
| `STRIPE_SECRET` | sync false | Unused in code | **No** |
| `DATABASE_URL` | sync false | Unused main path | **No** |
| `SMTP_*` | partial | Unset | Optional |
| `RENDER_EXTERNAL_URL` | Render-injected | Active | Auto |

**Do not sync Blueprint** unless Owner explicitly approves (stabilization rule). Set vars in **Render Dashboard → kyc-backend → Environment**.

---

## 3. Current domain state

### 3.1 Live probe matrix (2026-05-20)

| Host | `/healthz` | `/ui/shop.html` | Serves KYC? |
|------|------------|-----------------|-------------|
| `jetfighter-compliance.onrender.com` | 200 JSON `ok:true` | 200 PayPal+QR | **YES** |
| `compliance.keepyourcontracts.com` | **530** | (not reached) | **NO** — broken |
| `keepyourcontracts.com` | 200 empty HTML | **404** | **NO** — wrong origin |
| `www.keepyourcontracts.com` | 200 empty HTML | (not probed; expect same as apex) | **NO** — wrong origin |

### 3.2 DNS resolution (nslookup 2026-05-20)

| Name | Resolves to | Interpretation |
|------|-------------|----------------|
| `compliance.keepyourcontracts.com` | `104.21.28.220`, `172.67.147.184` (Cloudflare) | **Proxied CF** — not Render; origin misconfigured → **530** |
| `keepyourcontracts.com` | Same Cloudflare anycast | **Proxied CF** — different origin (placeholder HTML) |
| `www.keepyourcontracts.com` | Same Cloudflare anycast | Same as apex |
| `jetfighter-compliance.onrender.com` | `gcp-us-west1-1.origin.onrender.com` → `216.24.57.x` | **Render** (via Render CDN chain) |

### 3.3 Cloudflare / tunnel dependency (inferred)

| Finding | Detail |
|---------|--------|
| All branded names hit **Cloudflare proxy** | CF-Ray behavior; not direct to Render |
| `compliance` **530** | Typical: DNS points to removed tunnel, wrong origin host, or SSL/origin mismatch |
| `keepyourcontracts.com` empty HTML | **Not** FastAPI — likely Pages, parked site, or forwarding rule |
| **Tunnel not required for fix** | Point `compliance` CNAME to Render custom-domain target; remove `*.cfargotunnel.com` if present |
| **Dashboard verify required** | DNS records, Rules, Workers, Page Rules — Owner eyes in Cloudflare |

### 3.4 Domain classification

| Domain | Classification today | Target classification |
|--------|----------------------|------------------------|
| `jetfighter-compliance.onrender.com` | **Canonical interim production** | Keep live forever as rollback URL |
| `compliance.keepyourcontracts.com` | **Broken** (530) | **Canonical branded production** |
| `keepyourcontracts.com` | **Wrong origin** | **Optional** — marketing redirect or separate site (decision required) |
| `www.keepyourcontracts.com` | **Wrong origin** | CNAME to apex or same redirect policy |

**Recommendation for cutover execution:** Attach **`compliance.keepyourcontracts.com` only** first. Do **not** move apex until Owner decides apex strategy (redirect vs second custom domain).

---

## 4. Target state

```text
Customer
  → https://compliance.keepyourcontracts.com  (Cloudflare DNS → Render custom domain)
  → kyc-backend (Docker on Render)
  → FastAPI + /ui static + APIs

Fallback (always available):
  → https://jetfighter-compliance.onrender.com

NOT in path:
  → Carl laptop / uvicorn / cloudflared / PowerShell
```

| Criterion | Target |
|-----------|--------|
| Laptop off | Customers unaffected |
| Tunnel stopped | Customers unaffected |
| Terminal closed | Customers unaffected |
| WiFi disconnected (operator) | Customers unaffected |
| Proof of done | Live probes on **both** Render URL and `compliance.*` |

---

## 5. Exact Render custom-domain actions (Owner — Dashboard)

**Location:** [Render Dashboard](https://dashboard.render.com/) → **kyc-backend** → **Settings** → **Custom Domains**

| Step | Action |
|------|--------|
| R1 | Click **Add Custom Domain** |
| R2 | Enter: `compliance.keepyourcontracts.com` |
| R3 | Copy Render’s required DNS record(s) exactly as shown (name + target + type) |
| R4 | Wait for Render status **Verified** / certificate issued (can take 15–60 min after DNS) |
| R5 | Set environment variable: `PUBLIC_BASE_URL=https://compliance.keepyourcontracts.com` |
| R6 | Set `ENVIRONMENT=production` |
| R7 | Set `INTAKE_TOKEN_SECRET` (strong, not `dev-dev-dev-dev-dev`) |
| R8 | Set `OPS_API_KEY` (random, store in password manager) |
| R9 | **Save** → trigger **Manual Deploy** (or wait for autoDeploy if env-only triggers) |
| R10 | Do **not** remove `jetfighter-compliance.onrender.com` — Render keeps default URL |

**Render will display a target similar to:**

- **Type:** `CNAME`  
- **Name:** `compliance` (or FQDN)  
- **Target:** `<service-identifier>.onrender.com` ← **copy from Render UI, do not guess**

> **Important:** Use the hostname Render shows for **this** service after adding the domain. Do not assume `jetfighter-compliance.onrender.com` is the CNAME target for custom domains.

---

## 6. Exact DNS table (Owner — Cloudflare)

**Zone:** `keepyourcontracts.com`  
**Goal:** `compliance` → Render only; no tunnel.

### 6.1 Records to add or update

| Action | Type | Name | Target / content | Proxy (orange cloud) | Notes |
|--------|------|------|------------------|----------------------|-------|
| **UPSERT** | `CNAME` | `compliance` | `<Render-provided-target>.onrender.com` | **DNS only (grey)** first pass; proxied OK after TLS proven | Replace any `cfargotunnel.com` target |
| **DELETE** | `CNAME` | `compliance` | `*.cfargotunnel.com` | — | If exists — tunnel deprecation |
| **VERIFY** | — | — | No A/AAAA for `compliance` pointing at home IP | — | — |

### 6.2 Apex / www (decision gate — not blocking compliance cutover)

| Action | Type | Name | Target | Notes |
|--------|------|------|--------|-------|
| **DEFER or REDIRECT** | — | `@` (`keepyourcontracts.com`) | TBD | Currently wrong origin; options: (a) redirect to `compliance.`, (b) separate marketing host, (c) second Render custom domain |
| **DEFER** | `CNAME` | `www` | `@` or marketing host | Align with apex decision |

### 6.3 Proxy / TLS recommendation

| Phase | Proxy | SSL/TLS mode |
|-------|-------|----------------|
| **First verification** | Grey cloud (DNS only) | Render handles cert on custom domain |
| **After green probes** | Orange cloud optional | Cloudflare **Full (strict)** if proxied |

If **530** persists with orange cloud: switch `compliance` to **DNS only**, re-test, then re-enable proxy.

### 6.4 HTTPS verification steps (after DNS + Render verified)

Run in order on **public internet** (not localhost):

```powershell
# 1) JSON health — must be KYC backend
Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz

# 2) Shop
Invoke-WebRequest https://compliance.keepyourcontracts.com/ui/shop.html -UseBasicParsing

# 3) Inquiry API smoke (no secret in body)
$fd = @{ name="Cutover"; email="cutover-test@example.com"; subject="TASK28"; message="probe" }
Invoke-RestMethod https://compliance.keepyourcontracts.com/api/inquiry/submit -Method POST -Body $fd

# 4) Readiness
Invoke-RestMethod https://compliance.keepyourcontracts.com/health/ready
```

**Pass criteria:**

- `/healthz` → `Content-Type: application/json`, `"ok":true,"service":"kyc-backend"`
- `/health/ready` → `public_base_url` contains `compliance.keepyourcontracts.com`
- `environment` → `production` (after env hardening)
- Inquiry → `intake_url` host is `compliance.keepyourcontracts.com` (not localhost)

---

## 7. Local tunnel deprecation map

**No `start_production.ps1` exists in repo** (confirmed). Production must not reference it.

| Artifact | Path | Classification | Execution action |
|----------|------|----------------|------------------|
| `cloudflared.exe` | `bin/cloudflared.exe` (gitignored) | **KEEP DEV ONLY** | Never document as prod; never autostart on login for customers |
| `.cloudflared/*.yml` | Local only (gitignored) | **KEEP DEV ONLY** | Do not commit |
| `run_tunnel.ps1` | root | **KEEP DEV ONLY** | Add header comment “DEV/EMERGENCY” in doc task; do not delete yet |
| `start_everything.ps1` | root | **KEEP DEV ONLY** | Already labeled DEV (Task 24) |
| `start_live_platform.ps1` | root | **REMOVE FROM PRODUCTION** docs | Rename in docs to “misleading name”; **ARCHIVE** later |
| `fix_everything.ps1` | root | **KEEP DEV ONLY** | Ops recovery local only |
| `open_control_panel.ps1` | root | **KEEP DEV ONLY** | |
| `JetFighter_Launch_Compliance.bat` | root | **ARCHIVE** | E:\ path — delete later after Owner OK |
| `A) Autostart the tunnel (uses your.txt` | root | **ARCHIVE** | Scheduled-task instructions — **DELETE LATER** |
| `dns_reset_and_audit.ps1` | root | **KEEP DEV ONLY** | DNS diagnostics, not prod runbook |
| `sync_to_extreme_nightly.ps1` | root | **KEEP DEV ONLY** | USB backup — not prod |
| `ui/command.html` tunnel copy | `ui/command.html` | **REMOVE FROM PRODUCTION** messaging | UI change in separate task |
| `docs/KYC_RENDER_PRODUCTION_CUTOVER.md` | docs | **SAFE** | Update after cutover with dates |
| Tunnel as prod in old docs | various `KYC_*` | **REMOVE FROM PRODUCTION** | Consolidate to this plan + doctrine |

**Production runbooks must list only:**

1. Push `main` → GitHub  
2. Render autoDeploy  
3. `scripts/verify-production-public.ps1` (planned) against Render + compliance URLs  
4. Cloudflare DNS (one-time / on change)

---

## 8. Production verification script plan (future code task)

**Do not change scripts in Task 28.** Next task implements:

### 8.1 Script: `scripts/verify-production-public.ps1` (new, replaces gate logic)

| Host variable | URL |
|---------------|-----|
| `$Render` | `https://jetfighter-compliance.onrender.com` |
| `$Branded` | `https://compliance.keepyourcontracts.com` |
| `$Apex` | `https://keepyourcontracts.com` (informational only until apex strategy set) |

**Checks (each host where applicable):**

| # | Check | Render | Branded (post-cutover) |
|---|--------|--------|-------------------------|
| 1 | `GET /healthz` JSON ok | Required PASS | Required PASS |
| 2 | `GET /health/ready` `environment=production` | Required PASS | Required PASS |
| 3 | `intake_secret_configured=true` | Required PASS | Required PASS |
| 4 | `public_base_url` matches host | WARN if onrender | Required match `compliance.*` |
| 5 | `GET /ui/shop.html` + `design-system.css` | PASS | PASS |
| 6 | PayPal `paypal.com/ncp/payment` ×5 | PASS | PASS |
| 7 | QR `GET /ui/assets/qr/kyc-cmmc-l1-qr.png` 200 | PASS | PASS |
| 8 | `POST /api/inquiry/submit` HTTPS intake_url | PASS | PASS — host must match probe host |
| 9 | `GET /api/intake/resolve?token=invalid` → 401 | PASS | PASS |
| 10 | `POST /api/evidence/register` → 422 without file | PASS | PASS |
| 11 | `GET /upload` 200 | PASS | PASS |
| 12 | `POST /events/payment/test` without `X-Ops-Key` → **403** | PASS in prod | PASS |
| 13 | No `127.0.0.1` / `localhost` in inquiry `intake_url` | PASS | PASS |

**Remove / demote:**

| Removed check | Reason |
|---------------|--------|
| `STRIPE_WEBHOOK_SECRET` required | PayPal-first production |
| Stripe unsigned POST → 401 required | Optional `WARN` only |
| `keepyourcontracts.com/healthz` as KYC gate | Apex not KYC today |

**Retain:** `scripts/verify-render-production.ps1` as fast Render-only smoke (CI/ops).

**Deprecate gate:** `verify-production-live.ps1` Stripe+apex logic → redirect to `verify-production-public.ps1` or replace body.

### 8.2 PayPal / QR reference IDs (for automated grep)

| Product | NCP ID |
|---------|--------|
| CMMC L1 | `PAFCVQWAP8CNL` |
| CMMC L2 | `TGE3GEWHDUTG4` |
| EU DPP | `PFMJJ4P5W5KHU` |
| AI Essential | `9SW62N7N2ADFW` |
| AI Growth | `ZH3BTPVUS8SPJ` |

---

## 9. Execution sequence (next task — ordered)

| Order | Phase | Owner | Repo/code | Rollback |
|-------|-------|-------|-----------|----------|
| **0** | Read this plan + doctrine | Agent/Owner | — | — |
| **1** | Render env hardening (§5 R6–R8) | Owner dashboard | No code | Revert env vars |
| **2** | Render add custom domain (§5 R1–R4) | Owner dashboard | No code | Remove custom domain in Render |
| **3** | Cloudflare DNS (§6) | Owner Cloudflare | No code | Restore previous `compliance` CNAME / tunnel record |
| **4** | Wait TLS verified on Render | Owner | — | — |
| **5** | Manual deploy if needed | Owner | — | Redeploy previous image |
| **6** | Live probes §6.4 | Agent | No code | DNS rollback |
| **7** | Update verifier script | Agent | `scripts/verify-production-public.ps1` | Git revert |
| **8** | Doc truth pass | Agent | README, AGENTS, deprecate tunnel-in-prod docs | Git revert |
| **9** | Optional: regenerate QR for compliance host | Agent | assets + `generate_qr.py` | Git revert |

**Parallel constraint:** Do **not** run steps 1–6 on laptop tunnel simultaneously as “prod.”

---

## 10. Rollback plan

### 10.1 Custom domain cutover fails (530, wrong cert, wrong app)

| Step | Action |
|------|--------|
| 1 | **Keep** `https://jetfighter-compliance.onrender.com` live — no code rollback |
| 2 | Cloudflare: revert `compliance` CNAME to previous target OR delete record |
| 3 | Render: remove custom domain OR leave inactive |
| 4 | Set `PUBLIC_BASE_URL` back to `https://jetfighter-compliance.onrender.com` |
| 5 | Verify Render URL probes (§8.1 Render column) |
| 6 | Communicate customers to interim URL until DNS fixed |

**No application deploy rollback required** for DNS-only failure.

### 10.2 Environment hardening causes startup failure (future code)

If a later task adds fail-fast startup and deploy breaks:

| Step | Action |
|------|--------|
| 1 | Render → revert env vars to last known good |
| 2 | Manual deploy previous image digest (Render → Deploys) |
| 3 | Verify `/healthz` on Render URL |

### 10.3 Data note

Rollback does **not** restore ephemeral `data/` lost on redeploy — storage migration is a separate rollback story (S3 versioning).

---

## 11. Go / no-go criteria

### 11.1 Go — start DNS cutover (step 3)

| # | Criterion |
|---|-----------|
| G1 | `GET https://jetfighter-compliance.onrender.com/healthz` → JSON ok |
| G2 | Render Dashboard: custom domain added, DNS instructions copied |
| G3 | Cloudflare: tunnel CNAME on `compliance` identified for removal |
| G4 | `ENVIRONMENT`, `INTAKE_TOKEN_SECRET`, `OPS_API_KEY` set on Render (recommended before public branded launch) |
| G5 | Owner accepts interim traffic on Render URL if DNS delayed |

### 11.2 Go — declare branded production live

| # | Criterion |
|---|-----------|
| N1 | `GET https://compliance.keepyourcontracts.com/healthz` → `{"ok":true,"service":"kyc-backend"}` |
| N2 | `GET https://compliance.keepyourcontracts.com/ui/shop.html` → 200, PayPal ×5 |
| N3 | `POST https://compliance.keepyourcontracts.com/api/inquiry/submit` → `intake_url` on `compliance.keepyourcontracts.com` |
| N4 | `/health/ready` → `environment: production`, `intake_secret_configured: true` |
| N5 | `POST /events/payment/test` without ops key → **403** |
| N6 | `verify-production-public.ps1` exit **0** (after script task) |
| N7 | Doctrine closure: commit hash + URLs + rollback note recorded |

### 11.3 No-go — stop and fix before cutover

| # | Condition |
|---|-----------|
| NG1 | Render URL `/healthz` not JSON ok |
| NG2 | Owner unwilling to remove tunnel origin on `compliance` |
| NG3 | Cannot set `INTAKE_TOKEN_SECRET` (tokens forgeable) |
| NG4 | Expecting laptop/tunnel to stay in path for customers |

---

## 12. Documentation truth consolidation (future doc task)

**Canonical docs after cutover (single truth):**

| Doc | Role |
|-----|------|
| `PRODUCTION_ENGINEERING_DOCTRINE.md` | Law |
| `RENDER_PRODUCTION_CUTOVER_PLAN.md` | This execution plan |
| `RENDER_PRODUCTION_CUTOVER.md` | Post-cutover results (create when done) |
| `BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md` | Historical fragility snapshot |
| `README.md` + `AGENTS.md` | Entry points |

**Mark stale / banner (do not delete in cutover task):**

- `KYC_PRODUCTION_LOCK_CONFIRMED.md` — pre-lock
- `KYC_FINAL_PRODUCTION_VERDICT.md` — Stripe/apex assumptions
- `KYC_DOMAIN_RUNTIME_HARDENING.md` — Stripe shop references outdated
- Any doc claiming tunnel or localhost as production

---

## 13. Task 28 closure (plan-only)

| Criterion | Status |
|-----------|--------|
| Plan created | **Yes** — this file |
| Code changed | **No** |
| DNS changed | **No** |
| Render changed | **No** |
| Next task can execute without guessing | **Yes** |

**Live verification (doctrine — unchanged production):**

```text
GET https://jetfighter-compliance.onrender.com/healthz
→ {"ok":true,"service":"kyc-backend"}  PASS (2026-05-20)
```

**Rollback note for this doc-only task:** Remove or revert `docs/RENDER_PRODUCTION_CUTOVER_PLAN.md` via git; no runtime impact.

**No local-only dependency:** Plan is committed paperwork only; production truth remains deployed Render URL until DNS cutover executes.

---

## Appendix A — Owner checklist (copy/paste)

```text
[ ] Render kyc-backend: add custom domain compliance.keepyourcontracts.com
[ ] Copy Render DNS target exactly into Cloudflare CNAME compliance
[ ] Delete compliance → *.cfargotunnel.com if present
[ ] Wait Render TLS verified
[ ] ENVIRONMENT=production
[ ] INTAKE_TOKEN_SECRET=<strong>
[ ] OPS_API_KEY=<strong>
[ ] PUBLIC_BASE_URL=https://compliance.keepyourcontracts.com
[ ] Manual deploy
[ ] Invoke-RestMethod https://compliance.keepyourcontracts.com/healthz
[ ] Run verify-production-public.ps1 (after script lands)
[ ] Record commit hash + probe results in cutover result doc
```

---

## Appendix B — Related deferred work (not blocking DNS cutover)

| Item | Priority | Task |
|------|----------|------|
| Ephemeral evidence storage | P0 | S3/R2 implementation |
| PayPal webhook → kickoff | P0 | Code + PayPal dashboard |
| `engine.py` `passscheduler.start()` typo | P1 | Code fix |
| Apex `keepyourcontracts.com` strategy | P2 | Owner decision |
| Blueprint sync | Owner-gated | render.yaml |

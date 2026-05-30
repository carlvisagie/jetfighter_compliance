> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# Brutal Production Dependency Audit — Task 25

**Date:** 2026-05-20  
**Scope:** `carlvisagie/jetfighter_compliance` (KeepYourContracts / KYC backend)  
**Mode:** Read-only audit — **no fixes applied**  
**Live probes:** Render `https://jetfighter-compliance.onrender.com`, `https://compliance.keepyourcontracts.com`, `https://keepyourcontracts.com`

---

## Executive verdict

| Question | Answer |
|----------|--------|
| **Is KYC production-grade right now?** | **PARTIAL** |
| **Can customers use Render URL today?** | **Yes** — static UI + inquiry/intake/upload APIs respond |
| **Is it safe, durable, and operator-independent?** | **No** |

**Why PARTIAL (not YES):**

1. **Render is live but misconfigured** — `ENVIRONMENT=development`, default `INTAKE_TOKEN_SECRET`, no `STRIPE_WEBHOOK_SECRET`, `POST /events/payment/test` **open without ops key** (verified live 2026-05-20).
2. **All client data is ephemeral** — projects, evidence, ledger, inquiries, job queue live under container `data/` with **no persistent volume**; redeploy/restart **can wipe real client evidence**.
3. **Branded DNS is broken or wrong** — `compliance.keepyourcontracts.com` → **HTTP 530**; `keepyourcontracts.com` does **not** serve KYC (`/healthz` empty HTML, `/ui/shop.html` **404**).
4. **Payments are manual** — PayPal NCP links only; **no PayPal webhook**; Stripe backend exists but UI/docs are split-brain; paid customers do not auto-onboard.
5. **Repository still encodes laptop+tunnel ops** — hardcoded `E:\JetFighter_Compliance`, `cloudflared`, PowerShell “launch” scripts; easy to run production on the wrong machine.
6. **Background worker likely broken in deployed code** — `services/engine.py` line 118: `passscheduler.start()` (syntax/typo) prevents scheduler start; queue/SLA/nightly jobs unreliable.

**Why not NO:** Render Docker service serves health, UI, inquiry kickoff, intake, evidence register; Task 24 surface verifier passes; inquiry path creates projects with HTTPS links on Render host.

---

## P0 — Production blockers (fix before calling it “production-grade”)

| # | Issue | Evidence |
|---|--------|----------|
| P0-1 | **Ephemeral filesystem storage** | `data/` gitignored; `services/config.py` uses `ROOT/data`; no S3/Postgres/Render disk in `Dockerfile`/`render.yaml` |
| P0-2 | **`ENVIRONMENT` not production on live** | `GET /health/ready` → `"environment":"development"` |
| P0-3 | **Default intake signing secret** | `intake_secret_configured: false`; `INTAKE_TOKEN_SECRET` defaults to `dev-dev-dev-dev-dev` in code |
| P0-4 | **Ops test kickoff exposed** | `POST /events/payment/test` → **200** without `X-Ops-Key` while env is development |
| P0-5 | **`compliance.keepyourcontracts.com` broken** | Live probe → **HTTP 530** (Cloudflare/origin misconfiguration) |
| P0-6 | **`keepyourcontracts.com` not KYC** | `/healthz` 200 empty HTML; `/ui/shop.html` **404** — wrong site or parking |
| P0-7 | **PayPal → kickoff automation gap** | Shop uses PayPal links only; no `/webhooks/paypal`; ops manual path |
| P0-8 | **`engine.py` scheduler typo** | `passscheduler.start()` — worker/queue/SLA/digest jobs may not run |

---

## P1 — Reliability / security risks

| # | Issue | Evidence |
|---|--------|----------|
| P1-1 | `render.yaml` declares `ENVIRONMENT=production` but dashboard/live disagree | Blueprint **not synced** per stabilization rules; live ≠ blueprint |
| P1-2 | `render.yaml` lists `DATABASE_URL`, `STRIPE_SECRET` — **unused** by main app | Dead config noise; organism uses hardcoded sqlite path |
| P1-3 | Stripe webhook route live but secret unset | `/webhooks/stripe` → **503**; verifier still expects Stripe for “full lock” |
| P1-4 | CORS `allow_origins=["*"]` | `server.py` TODO not enforced |
| P1-5 | `engine.step_send_intake` uses `SETTINGS.public_base_url` not `get_public_base_url()` | Queue emails may use localhost if only `RENDER_EXTERNAL_URL` set |
| P1-6 | Duplicate project risk | `kickoff()` then `enqueue("post_payment")` → `new_project()` again with new timestamp |
| P1-7 | SMTP not configured | `smtp_configured: false` — welcome/intake/digest emails may silently fail |
| P1-8 | QR/posters may encode wrong host | Historical assets targeted `compliance.keepyourcontracts.com` (530); `generate_qr.py` now Render — printed collateral may be stale |
| P1-9 | PayPal account/link dependency | Five hardcoded `paypal.com/ncp/payment/{ID}` — account suspension = revenue stop |
| P1-10 | Single-vendor hosting (Render starter) | No documented failover; cold start / plan limits unaddressed |

---

## P2 — Cleanup / doc debt (not blocking Render URL smoke tests)

| # | Issue |
|---|--------|
| P2-1 | 31+ `docs/KYC_*.md` with conflicting claims (Stripe vs PayPal, “LOCK CONFIRMED” vs open blockers) |
| P2-2 | `docs/README.md` still says shop uses “Stripe Payment Links” — UI is PayPal |
| P2-3 | Root clutter: `A) Autostart the tunnel...txt`, `.bak` UI files, `ui_backup_*`, `JetFighter_Launch_Compliance.bat` |
| P2-4 | `verify-production-live.ps1` tests Stripe + apex domain — misaligned with PayPal + broken DNS |
| P2-5 | `organism/` sqlite subsystem not integrated with main `data/` path |
| P2-6 | `config_auth.json` referenced in `server.py` dead code path; gitignored |
| P2-7 | Telemetry router writes `data/telemetry/` — same ephemeral disk |
| P2-8 | No `start_production.ps1` — only local/tunnel starters exist |

---

## 1. Hosting / production runtime

| Artifact | Classification | Notes |
|----------|----------------|-------|
| `Dockerfile` + Render `kyc-backend` | **SAFE** (canonical path) | `uvicorn` on `0.0.0.0:10000`; health `GET /healthz` |
| `render.yaml` `autoDeploy: true` | **SAFE** (if GitHub `main` connected) | Blueprint env may not match dashboard |
| `https://jetfighter-compliance.onrender.com` | **SAFE** (temporary canonical) | Task 24 verifier exit 0 |
| `start_everything.ps1` | **LOCAL ONLY** | `E:\JetFighter_Compliance`, uvicorn `127.0.0.1:8000`, cloudflared |
| `start_live_platform.ps1` | **LOCAL ONLY** / **DANGEROUS** | Name implies “live”; starts tunnel + local uvicorn |
| `fix_everything.ps1` | **LOCAL ONLY** | Kills python/cloudflared, starts tunnel |
| `run_tunnel.ps1` | **EMERGENCY ONLY** | Hardcoded `E:\` paths |
| `open_control_panel.ps1` | **LOCAL ONLY** | Local uvicorn + control UI |
| `setup_run.ps1`, `stage1_install.ps1` | **LOCAL ONLY** | Dev setup |
| `sync_to_extreme_nightly.ps1` | **LOCAL ONLY** | Robocopy `data/` to USB `KYC_TRANSPORT` — **manual backup**, not prod |
| `bin/cloudflared.exe` (gitignored) | **EMERGENCY ONLY** | Must not be production ingress |
| `.cloudflared/*.yml` (gitignored) | **EMERGENCY ONLY** | Not in repo; machine-local |
| `A) Autostart the tunnel (uses your.txt` | **LOCAL ONLY** | Scheduled task instructions for tunnel |
| `JetFighter_Launch_Compliance.bat` | **LOCAL ONLY** | `E:\` venv paths |
| `server.py` `if __name__` uvicorn `127.0.0.1` | **DEV ONLY** | |
| `ui/command.html` “Tunnel / Host” copy | **STALE DOC/UI** | Still tells operators tunnel may be down |
| Task 24 docs | **SAFE** | Render = prod; tunnel = dev |

**Windows / PowerShell production dependency:** The repo’s *operational gravity* still points at **Carl’s PC** (paths, autostart notes, “Full Launch” scripts). Production *intent* is Render; production *muscle memory* is still local.

---

## 2. Domain / DNS

| Host | Classification | Live probe (2026-05-20) |
|------|----------------|-------------------------|
| `jetfighter-compliance.onrender.com` | **Canonical production backend (interim)** | `/health/ready` JSON OK |
| `compliance.keepyourcontracts.com` | **Broken domain** | `/healthz` → **530** |
| `keepyourcontracts.com` | **Wrong / not attached to KYC** | `/healthz` 200 empty HTML; `/ui/shop.html` 404 |
| `*.cfargotunnel.com` | **Deprecated for prod** | Documented in Task 24; may still exist in Cloudflare |
| `purposefullivecoaching.academy` (historical control copy) | **Deprecated** | Old tunnel examples in backups |

**Doc conflict:** `verify-production-live.ps1` treats `https://keepyourcontracts.com` as custom domain success criterion — **that host is not serving this app today.**

---

## 3. Storage / evidence persistence

| Path | Purpose | Persisted on Render? |
|------|---------|----------------------|
| `data/projects/{P-*}/evidence/` | Client uploads | **Only until container loss** |
| `data/projects/{P-*}/meta.json`, `checklist.json`, `communications/` | Project state | Same |
| `data/ledger/ledger.log` | Hash chain ledger | Same |
| `data/inquiries/` | Inquiry JSON | Same |
| `data/jobs/J-*.json` | APScheduler queue | Same |
| `data/logs/` | App logs | Same |
| `data/telemetry/` | Telemetry drafts | Same |
| `data/vendors/vendors.json` | Vendor registry | Same |

**Git:** `data/` is in `.gitignore` — correct for secrets/uploads; means **no repo backup of production data**.

**Local-only backup:** `sync_to_extreme_nightly.ps1` mirrors `data/` to removable drive — **requires Carl’s machine + USB + scheduled run**.

### Answer: Could real client evidence be lost?

| Event | Risk |
|-------|------|
| Render **redeploy** / new instance | **YES** — high |
| Render **restart** | **YES** — unless persistent disk added |
| **PC shutdown** (if ever on tunnel/local) | **YES** for local `data/` |
| **Git push** | No direct loss (data not in git) |
| **PayPal-only payment** without kickoff | Project never created — “logical loss” of onboarding |

**Verdict:** **Not production-grade for compliance evidence** until durable object storage or managed DB + backup policy.

---

## 4. Environment variables

| Variable | In code | In `render.yaml` | Live / docs | Class |
|----------|---------|------------------|-------------|-------|
| `ENVIRONMENT` | `config.py`, `production.py` | `production` | **development** on Render | **REQUIRED** — **UNDOCUMENTED mismatch** |
| `PUBLIC_BASE_URL` | `config.py`, `public_url.py` | No | Render URL works via `RENDER_EXTERNAL_URL` | **OPTIONAL** on Render if external URL set |
| `RENDER_EXTERNAL_URL` | `public_url.py` | Auto (Render) | Active | **SAFE** (platform) |
| `INTAKE_TOKEN_SECRET` | `config.py`, `security.py` | No | Default dev secret | **SECRET** — **REQUIRED** — **FAIL** live |
| `STRIPE_WEBHOOK_SECRET` | `config.py`, `server.py` | sync false | Unset | **SECRET** — **OPTIONAL** if PayPal-only — verifier still **REQUIRED** |
| `STRIPE_SECRET` | Not read | sync false | — | **DEAD** in code |
| `OPS_API_KEY` | `production.py` | No | Unset; guard inactive | **SECRET** — **REQUIRED** for prod lock |
| `SMTP_*`, `SMTP_ENABLED` | `config.py` | partial in yaml | Unset | **OPTIONAL** (email fails soft) |
| `DIGEST_EMAIL_TO` | `config.py` | No | — | **OPTIONAL** |
| `AUTO_NIGHT_EXPORT`, `WEEKLY_DIGEST`, `EXPORT_KEEP_LATEST` | `config.py` / engine | No | Defaults on | **OPTIONAL** — **UNDOCUMENTED** ops |
| `DATABASE_URL` | organism only | sync false | Unused main path | **DEAD** (main app) |
| `SHOPIFY_*` | warnings only if set | Removed from yaml | Remove from dashboard | **DEAD** |
| `.env` | local `load_dotenv()` | gitignored | Local dev | **SECRET** — never commit |

**Undocumented / fragile:** Queue playbook env `auto_sla_escalation_minutes` referenced via `getattr` — not in Settings model.

---

## 5. Payment rail dependency

| Component | Classification | Notes |
|-----------|----------------|-------|
| PayPal NCP links in `ui/shop.html` (×5) | **ACTIVE** | Manual external checkout |
| PayPal webhook / IPN | **MISSING** | **MANUAL GAP** — ops must run `new_client.html` or inquiry |
| `POST /webhooks/stripe` + `stripe_hook.py` | **DORMANT** (no secret) | Code **ACTIVE**; live **503** without secret |
| `tests/test_stripe_webhook.py` | **DORMANT** tests | |
| Stripe Payment Links in UI | **DEAD** | Removed Task 19 |
| `docs/README.md` Stripe mention | **STALE** | Contradicts PayPal |
| `verify-production-live.ps1` Stripe checks | **DANGEROUS** | Fails “full lock” for wrong rail |
| QR assets (`ui/assets/qr/`, posters) | **ACTIVE** | Decode to URLs; may point at broken subdomain if old prints |
| Inquiry → `kickoff()` | **ACTIVE** | Free path; creates project (no payment proof) |

**Payment-to-kickoff truth:** Only **inquiry submit**, **ops test**, or **Stripe webhook (if configured)** call `kickoff()`. **PayPal payment does not.**

---

## 6. Deployment truth (“works locally but not live”)

| Risk | Detail |
|------|--------|
| Port mismatch | Local scripts use **8000/8080**; Docker **10000** |
| Path mismatch | Local `E:\JetFighter_Compliance` vs clone `C:\Users\Carl\jetfighter_compliance` |
| `render.yaml` not synced | Dashboard env can diverge from repo blueprint |
| Blueprint says `ENVIRONMENT=production` | Live shows **development** |
| Worker typo | `passscheduler.start()` — local may not run worker either unless different branch |
| `load_dotenv()` | Local `.env` can mask missing Render vars |
| CORS / cookies | Not tested across custom domain |
| Static UI | Served from image — **OK** on Render |
| File upload size 50MB | In code — Render request limits may differ |

**Auto-deploy:** Documented as yes; **push to `main` required** — “GitHub not pushed” = stale live (historically happened per P0 closeout doc).

---

## 7. Repo truth

| Item | Status |
|------|--------|
| **Active repo** | `github.com/carlvisagie/jetfighter_compliance` |
| **Wrong repo risk** | `docs/AGENTS.md` warns against `purposeful-platform` (SAGE) — easy confusion |
| **Wrong clone path** | Docs use `C:\Users\Carl\jetfighter_compliance`; scripts use `E:\JetFighter_Compliance` |
| **Shadow / duplicate** | `ui_backup_before_client_redesign_*`, many `*.bak` — not deployed but confusing |
| **Stale docs** | `KYC_FINAL_PRODUCTION_VERDICT.md`, `KYC_PRODUCTION_LOCK_CONFIRMED.md` claim blockers; `KYC_P0_CLOSEOUT` says “production-ready” with same blockers |
| **Missing doc** | `KYC_RUNTIME_RECONCILIATION.md` referenced in de-Shopify result — **not in repo** |
| **Uncommitted production data** | All runtime data local/ephemeral — by design gitignored |

---

## 8. Operational runbooks

| Script / doc | Classification |
|--------------|----------------|
| `scripts/verify-render-production.ps1` | **PRODUCTION APPROPRIATE** — surface checks, no tunnel |
| `scripts/verify-production-live.ps1` | **PRODUCTION APPROPRIATE** intent — currently **fails** live; Stripe/apex assumptions **DANGEROUS** |
| `docs/KYC_RENDER_PRODUCTION_CUTOVER.md` | **SAFE** — accurate Render-first policy |
| `docs/KYC_OWNER_*` checklists | **SAFE** but **stale** (Stripe-heavy) |
| `start_live_platform.ps1` | **DANGEROUS** — name vs Task 24 policy |
| `start_everything.ps1` | **LOCAL ONLY** — labeled dev after Task 24 |
| `fix_everything.ps1` | **LOCAL ONLY** |
| `dns_reset_and_audit.ps1` | **LOCAL ONLY** — writes to `JetFighter_Automation\diagnostics` |
| `scripts/task14_*.py`, `lane2_unify_ui.py` | **LOCAL ONLY** — one-off UI refactors |
| `scripts/generate_payment_qr_assets.py` | **LOCAL ONLY** — asset generation |
| **Missing** `start_production.ps1` | No first-class “prod start” besides Render dashboard |

---

## 9. Critical failure modes

| Failure mode | Current protection | Risk | Required fix (priority) |
|--------------|-------------------|------|-------------------------|
| Carl’s PC off | Render hosts API | **Low** if customers use Render URL only | **P0:** Stop advertising tunnel/local as prod |
| Cloudflare tunnel stopped | None needed if DNS correct | **High** if DNS still points to tunnel | **P0:** DNS → Render; remove tunnel CNAME |
| Render redeploy / restart | Health check restarts process | **Critical** — **data loss** | **P0:** Persistent volume or S3+DB |
| Upload / evidence loss | None on platform | **Critical** | **P0:** Durable storage + backup |
| `ENVIRONMENT` left `development` | None | **High** — ops routes open | **P0:** Set `production` on Render |
| Default `INTAKE_TOKEN_SECRET` | Warning logs only | **Critical** — forgeable intake tokens | **P0:** Rotate secret on Render |
| PayPal paid, no webhook | None | **High** — manual onboarding | **P0/P1:** PayPal webhook or ops SOP |
| Stripe webhook unset | 503 on route | **Medium** if PayPal-only | **P1:** Align docs/verifiers to PayPal |
| DNS `compliance.*` wrong | None | **High** — 530 for branded URL | **P0:** Cloudflare → Render custom domain |
| `keepyourcontracts.com` wrong host | None | **High** — marketing broken | **P0:** Point apex or subdomain to Render |
| GitHub not pushed | Manual deploy lag | **Medium** | **P1:** CI deploy visibility |
| Wrong repo edited (SAGE) | AGENTS.md warning | **Medium** | **P2:** Pre-commit hook / path check |
| PayPal account suspended | None | **High** | **P1:** Monitoring + backup processor |
| SMTP down | Log warning | **Medium** | **P1:** Configure SMTP or disable email promises |
| Worker scheduler broken | try/except logs | **High** — queue stuck | **P0:** Fix `engine.py` start (when fixing allowed) |
| CORS `*` | None | **Medium** | **P1:** Restrict origins |
| Duplicate projects from queue | Partial idempotency on order_id in kickoff only | **Medium** | **P1:** Idempotent `post_payment` job |

---

## 10. Fragile dependency inventory (master list)

### Depends on Carl’s laptop
- `start_everything.ps1`, `start_live_platform.ps1`, `fix_everything.ps1`, `open_control_panel.ps1`, `run_tunnel.ps1`
- `sync_to_extreme_nightly.ps1` (USB backup)
- `E:\JetFighter_Compliance` path assumptions
- `.venv` local Python
- `.env` local secrets
- Scheduled tunnel autostart notes

### Depends on open PowerShell / manual processes
- All `Start-Process` / `-NoExit` launchers
- `fix_everything.ps1` “one click” recovery
- Manual Render dashboard env changes (documented repeatedly, not automated)
- Manual PayPal → ops kickoff
- Manual DNS changes in Cloudflare/Render

### Depends on Cloudflare Tunnel (production risk if DNS wrong)
- `cloudflared` binary + local configs
- Historical autostart task docs
- `ui/command.html` tunnel messaging

### Depends on local / ephemeral storage
- Entire `data/` tree
- Telemetry under `data/telemetry/`
- `organism/data/kyc.db` (separate, unused by main server)

### Depends on manual dashboard settings
- Render env vars (not blueprint-synced)
- Stripe dashboard webhook (still in checklists)
- PayPal link management (external)
- Cloudflare DNS / SSL mode
- Render custom domain attachment

### Depends on single vendors
- **Render** (hosting)
- **PayPal** (payments)
- **Cloudflare** (DNS)
- **GitHub** (deploy source)

### Stale / wrong assumptions in docs
- Stripe as primary payment in `README.md` and owner docs
- `keepyourcontracts.com` as live custom domain
- “LOCK CONFIRMED” / “production-ready” while readiness fails
- `KYC_DESHOPIFY_RESULT.md` still says shop retains Stripe links (false post–Task 19)

---

## 11. Fix plan (priority order — **do not execute in Task 25**)

| Order | Action |
|-------|--------|
| 1 | **P0** Attach durable storage (Render disk or S3) for `data/projects`, `ledger`, `inquiries` |
| 2 | **P0** Render env: `ENVIRONMENT=production`, strong `INTAKE_TOKEN_SECRET`, `OPS_API_KEY` |
| 3 | **P0** DNS: fix `compliance.keepyourcontracts.com` → Render; decide apex `keepyourcontracts.com` |
| 4 | **P0** Fix `engine.py` scheduler start; make `post_payment` idempotent |
| 5 | **P0** PayPal → webhook or documented ops SOP with SLA |
| 6 | **P1** Update `verify-production-live.ps1` + owner docs for PayPal-first reality |
| 7 | **P1** Configure SMTP or remove email promises from kickoff |
| 8 | **P1** Restrict CORS; deprecate/archive local tunnel scripts |
| 9 | **P2** Doc consolidation; remove stale verdicts; fix README payment line |
| 10 | **P2** Regenerate QR/posters after DNS cutover |

---

## 12. Task 25 success criteria (audit completeness)

| Criterion | Answered |
|-----------|----------|
| Every laptop dependency | **Yes** — §1, §10 |
| Every local-only dependency | **Yes** — §1, §3, §8 |
| Every tunnel dependency | **Yes** — §1, §2 |
| Every storage risk | **Yes** — §3 |
| Every env risk | **Yes** — §4 |
| Every payment risk | **Yes** — §5 |
| Every deploy risk | **Yes** — §6 |
| Every domain risk | **Yes** — §2 |

---

## Appendix — Live readiness snapshot (2026-05-20)

```json
GET https://jetfighter-compliance.onrender.com/health/ready
{
  "environment": "development",
  "public_base_url": "https://jetfighter-compliance.onrender.com",
  "stripe_webhook_configured": false,
  "intake_secret_configured": false,
  "smtp_configured": false,
  "data_writable": true
}
```

**Audit author:** Agent (Task 25, read-only)  
**No code, DNS, Render blueprint, or backend behavior was changed.**

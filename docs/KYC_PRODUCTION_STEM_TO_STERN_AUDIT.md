# KYC Production Stem-to-Stern Audit

**Audit date:** 2026-05-26  
**Repository:** `E:\JetFighter_Compliance` (KeepYourContracts / JetFighter_Compliance)  
**Production host probed:** `https://compliance.keepyourcontracts.com`  
**Auditor scope:** Audit only — no feature work performed  
**Git HEAD:** `795612e` — `feat: add KYC constitution, sacred-area guardrails, and agent protection rules`

---

## Executive Summary

KeepYourContracts production is **partially operational** on the custom domain `compliance.keepyourcontracts.com`. Core readiness checks pass (`environment: production`, `intake_secret_configured: true`, writable data dirs, inquiry onboarding active). Operator routes are gated (`GET /api/projects` → 403 on prod).

However, this audit finds **critical gaps** that prevent a clean production GO:

1. **SMTP is not configured on production** — welcome emails, inquiry notifications, and operator test email all silently skip; customers receive intake URLs only if returned in the API response or manually relayed.
2. **Unauthenticated write endpoints** — `POST /api/coc/event` and `POST /api/telemetry/event` accept anonymous writes (confirmed locally: HTTP 200 without session or `X-Ops-Key`).
3. **Large uncommitted deployment drift** — ~211 lines changed in `server.py` plus entire Customer Friction layer (`services/customer_friction.py`, `ui/continue.html`, tests) exist locally but are **not on production** (`/ui/continue.html` → 404 live).
4. **Test suite regression** — 1 of 235 tests fails (`test_ledger_event_writes_central_memory`), breaking the documented organism contract for ledger → central memory linking on inquiry kickoff.
5. **`render.yaml` incomplete** — declares `SMTP_*` and dead `DATABASE_URL` but omits `OPS_PASSWORD`, `INTAKE_TOKEN_SECRET`, `PUBLIC_BASE_URL`, and `OPS_API_KEY` as documented production requirements.

**Production readiness verdict: GO WITH CONDITIONS**

Inquiry → kickoff → intake can proceed without email if operators manually share links. Full customer self-service (email delivery, magic continuation upload, QR resume) and security hardening are **not production-ready** until conditions below are met.

---

## Pytest Results

```
Command:  python -m pytest tests/ -q  (from repo root)
Result:   234 passed, 1 failed, 174 warnings in 41.91s
Failure:  tests/test_organism_integration.py::test_ledger_event_writes_central_memory
          AssertionError: assert 'ledger_event' in {'inquiry_submitted', 'project_created'}
```

| Metric | Value |
|--------|-------|
| Total tests | 235 |
| Passed | 234 |
| Failed | 1 |
| Warnings | 174 (FastAPI `on_event` deprecation, httpx `app` shortcut) |

---

## Production Health Check

**Endpoint:** `GET https://compliance.keepyourcontracts.com/health/ready`

```json
{
  "ok": true,
  "status": "ready",
  "checks": {
    "data_writable": true,
    "projects_dir": true,
    "public_base_url": "https://compliance.keepyourcontracts.com",
    "inquiry_onboarding_active": true,
    "intake_secret_configured": true,
    "smtp_configured": false,
    "environment": "production"
  }
}
```

| Check | Live value | Assessment |
|-------|------------|------------|
| `smtp_configured` | **false** | BLOCKER — no outbound email |
| `intake_secret_configured` | true | PASS |
| `environment` | production | PASS |
| `public_base_url` | compliance.keepyourcontracts.com | PASS |
| `/api/projects` (no auth) | 403 | PASS — ops gate active |
| `/ui/continue.html` | 404 | HIGH — customer friction layer not deployed |
| `POST /api/coc/event` (no auth) | 400 (validation) / reachable | HIGH — not 403; unauthenticated when payload valid |

---

## Git Status Summary

**Branch:** `main` (up to date with `origin/main`)

### Uncommitted modified (production-relevant)

| Area | Files | Notes |
|------|-------|-------|
| Core server | `server.py` (+211 lines) | Customer friction routes, SMTP telemetry, continuation APIs |
| Auth | `services/ops_auth.py`, `services/production.py`, `services/security.py` | `continue.html` public UI, continuation tokens |
| Email | `services/emails.py`, `services/config.py` | Structured SMTP result + telemetry |
| Deploy | `render.yaml`, `requirements.txt` | SMTP env block; `qrcode` dependency |
| UI | `ui/upload.html`, `ui/intake.html`, `ui/control.html` | Customer friction UX, operator SMTP test |
| Tests | `tests/test_public_ui_exposure.py`, `tests/test_organism_observability.py` | Updated for continue.html |

### Untracked (not committed, not deployed)

- `services/customer_friction.py`
- `ui/continue.html`, `ui/assets/js/customer-friction.js`, `ui/assets/styles/customer-friction.css`
- `tests/test_customer_friction_layer.py`, `tests/test_smtp_operator.py`
- `docs/KYC_SMTP_SETUP.md`
- Runtime artifacts: `data/memory/telemetry.jsonl`, `organism-test-result.json`, `validation-e2e-production.*`

### Risk

Production is running commit `795612e` while the working tree contains substantial unaudited-on-prod changes. **Local code ≠ live code.**

---

## Findings by Severity

| ID | Severity | Area | Finding | Evidence |
|----|----------|------|---------|----------|
| F-01 | **BLOCKER** | SMTP | Production `smtp_configured: false` — welcome/inquiry emails silently skipped | `/health/ready` live probe |
| F-02 | **BLOCKER** | Auth / Ledger | `POST /api/coc/event` is **public** — unauthenticated ledger append | Local TestClient 200 without login; not in `PROTECTED_API_PREFIXES` |
| F-03 | **BLOCKER** | Deploy | Customer Friction layer uncommitted; `/ui/continue.html` 404 on prod | git status + live 404 |
| F-04 | **BLOCKER** | Tests / Memory | `test_ledger_event_writes_central_memory` fails — ledger events not in central memory timeline after inquiry kickoff | pytest failure |
| F-05 | **BLOCKER** | IaC | `render.yaml` missing `OPS_PASSWORD`, `INTAKE_TOKEN_SECRET`, `PUBLIC_BASE_URL`, `OPS_API_KEY` | render.yaml vs docs/LAUNCH_PATH.md |
| F-06 | **HIGH** | Upload security | `POST /api/evidence/register` requires no token — anyone who knows/guesses `P-*` project_id can upload | `ops_auth.py` explicit bypass; `test_upload_flow.py` |
| F-07 | **HIGH** | Auth / Telemetry | `POST /api/telemetry/event` (drafts router) is public — unauthenticated file append to `data/telemetry/` | Local TestClient 200; `server.py` includes `telemetry_router` |
| F-08 | **HIGH** | CORS | `allow_origins=["*"]` + `allow_credentials=True` — invalid/over-permissive combo | `server.py:44-49` |
| F-09 | **HIGH** | Tokens | Intake tokens (`parse_intake_token`) have **no max_age** — non-expiring signed links | `services/security.py:16-17` |
| F-10 | **HIGH** | Docs / Scripts | `scripts/verify-render-production.ps1` targets `jetfighter-compliance.onrender.com`, not `compliance.keepyourcontracts.com` | script line 5 |
| F-11 | **HIGH** | Deploy | `requirements.txt` adds `qrcode` locally; prod may lack dependency until redeploy | uncommitted requirements.txt |
| F-12 | **MEDIUM** | Health | Render healthCheckPath is `/healthz` (liveness only) — does not catch SMTP/degraded readiness | `render.yaml:7` |
| F-13 | **MEDIUM** | IaC | `DATABASE_URL` in render.yaml unused by main app (filesystem persistence) | docs/BRUTAL_PRODUCTION_DEPENDENCY_AUDIT.md |
| F-14 | **MEDIUM** | QR | `/api/customer/qr.svg?url=` generates QR for arbitrary URL (length capped 2000) — abuse/spam vector | `server.py:550-558` |
| F-15 | **MEDIUM** | Error handling | Memory/ledger integration wrapped in bare `except Exception: pass` — silent data loss | `server.py` kickoff, coc_event |
| F-16 | **MEDIUM** | CI | Full suite failure would block CI job "Full test suite" in `kyc_guardrails.yml` | 1 failing test |
| F-17 | **LOW** | Secrets hygiene | Local `.env` contains `SMTP_PASSWORD` (gitignored, not tracked) — ensure never committed | grep + `.gitignore` |
| F-18 | **LOW** | FastAPI | `@app.on_event("startup")` deprecated | pytest warnings |
| F-19 | **LOW** | Drafts | Telemetry router writes literal `` `n `` instead of newline in jsonl | `drafts/telemetry_fastapi_endpoint.py:53` |
| F-20 | **CLEANUP** | Dead code | `services/engine.py.bak`, `services/engine.py.bak_queue_fix`, `services/server.py` duplicate | repo scan |
| F-21 | **CLEANUP** | Dead code | `ui_backup_before_client_redesign_20260517-172621/` backup tree outside `/ui` | repo scan |
| F-22 | **CLEANUP** | Dead code | `server.py` `safe_load_json` / `cfg = {}` block unused | `server.py:129-138` |
| F-23 | **CLEANUP** | Stale docs | `KYC_FINAL_PRODUCTION_VERDICT.md`, `KYC_PRODUCTION_LOCK_CONFIRMED.md` describe 2026-05-19 failures superseded by current domain | doc headers |
| F-24 | **CLEANUP** | Git noise | `__pycache__`, runtime `data/*` jsonl changes showing in `git status` | git status |
| F-25 | **CLEANUP** | Docs gap | `KYC_OPS_AUTH.md` public API list omits `/api/customer/*`, `/api/telemetry/event` | doc vs code |

---

## Per-Area Audit

### 1. `server.py`

**Role:** FastAPI entrypoint — routes, middleware, kickoff, inquiry/intake/upload, memory/operator APIs.

| Topic | Status | Detail |
|-------|--------|--------|
| Route inventory | Documented | 40+ routes; inquiry-led onboarding is active path |
| Ops middleware | PASS | `ops_auth_middleware` gates protected UI/API |
| Customer flow | PARTIAL | Inquiry → kickoff → intake works; continuation/QR in uncommitted code |
| Legacy Stripe | INACTIVE | `/webhooks/stripe` returns 503 without secret (by design per LAUNCH_PATH) |
| Test routes | GATED | `/events/payment/test`, `/api/test-webhook` require ops access in production |
| Health | PASS | `/healthz` liveness; `/health/ready` exposes config flags + memory telemetry |
| Security gaps | FAIL | `/api/coc/event`, `/api/telemetry/event` unauthenticated |

### 2. `services/*`

#### `production.py`
- `is_production()` checks `ENVIRONMENT=production` — live prod confirms.
- `readiness_checks()` correctly reports SMTP, intake secret, data dirs.
- `require_ops_access()` enforces session or `X-Ops-Key` in production — verified on `/api/projects`.
- `_DEV_INTAKE_SECRET` guard warns on default secret — prod shows `intake_secret_configured: true`.

#### `ops_auth.py`
- Public UI: shop, inquiry, intake, upload, **continue** (local only), login, assets.
- Protected UI/API lists comprehensive for operator surfaces.
- **Gap:** `/api/coc/event` not listed as protected; `/api/evidence/register` explicitly public.
- Backup UI blocking via regex — tested in `test_backup_ui_files_not_served`.

#### `security.py`
- Intake tokens: signed, no expiration (HIGH).
- Continuation tokens: 90-day max age — good pattern; intake should match.

#### `emails.py`
- Graceful skip when SMTP unconfigured + telemetry events — correct behavior.
- Operator test email endpoint requires auth — PASS.
- Production SMTP: **not configured**.

#### `customer_friction.py` (untracked)
- Continuation magic links, QR, upload guidance, momentum messaging, session persistence.
- Integrated in local `server.py` but **not deployed**.

#### `memory/*`
- Central memory, telemetry, organism integration registry well-structured.
- Ledger → memory link fails test on inquiry path (F-04).
- Silent exception swallowing hides integration failures.

#### `acquisition/*`
- Mock domain blocklist enforced — guardrail tests pass.
- Forensics bridge on inquiry/intake/evidence — plugged per registry.

### 3. `ui/*` — Public vs Ops Exposure

| Classification | Pages |
|----------------|-------|
| **Public (customer)** | shop, inquiry, intake, upload, continue (local), index, vendor_quote, login |
| **Protected (operator)** | control, memory, command, status, inbox, readiness/*, lead_discovery, etc. |

- `tests/test_public_ui_exposure.py` — 9 tests; scans for forbidden links/terms on public pages.
- `tests/test_ops_route_auth.py` — 9 tests; 403/302 behavior verified.
- `docs/PUBLIC_UI_EXPOSURE_AUDIT.md` (2026-05-25) — does not mention `continue.html` (added locally).
- Backup files under `ui/` — none (guardrail PASS); backups exist in `ui_backup_before_client_redesign_*` outside served tree.

### 4. `tests/*` — Coverage Gaps

**Present (24 test files, ~235 tests):** guardrails, public UI, ops auth, central memory, organism observability, operator guidance, upload flow, production guards, SMTP operator (untracked), customer friction (untracked), stripe webhook, acquisition, engine/ledger/projects/process.

**Missing / weak coverage:**

| Gap | Risk |
|-----|------|
| No test that `/api/coc/event` requires auth | F-02 undetected |
| No test that `/api/telemetry/event` requires auth | F-07 undetected |
| No test for intake token expiration policy | F-09 undetected |
| No test that evidence upload rejects missing token (when policy changes) | F-06 |
| No integration test for SMTP on production (expected — env-specific) | F-01 |
| No E2E test for email delivery | F-01 |
| `test_ledger_event_writes_central_memory` failing | F-04 |
| RFQ vendor flow — minimal coverage | MEDIUM |
| CORS policy | not tested |
| Rate limiting on public POST endpoints | not tested |

### 5. `scripts/*`

| Script | Purpose | Audit note |
|--------|---------|------------|
| `verify-render-production.ps1` | Render surface probe | Uses old Render URL, not custom domain |
| `verify-production-live.ps1` | Full lock verification | Referenced in stale lock docs |
| `acquisition_*.py` | Lead discovery ops | Not on launch path |
| `lane2_unify_ui.py`, `patch_internal_ui_nav.py` | One-off UI migrations | Historical |

### 6. `docs/*` — Stale vs Reality

| Document | Status |
|----------|--------|
| `LAUNCH_PATH.md` | **Current** — inquiry-led path; SMTP "optional" conflicts with kickoff email dependency |
| `KYC_SMTP_SETUP.md` | **New/untracked** — accurate for local code |
| `KYC_OPS_AUTH.md` | **Mostly current** — missing customer/telemetry API notes |
| `KYC_FINAL_PRODUCTION_VERDICT.md` | **Stale** — 2026-05-19, pre-custom-domain |
| `KYC_PRODUCTION_LOCK_CONFIRMED.md` | **Stale** — lock NOT confirmed; contradicted by live state |
| `PUBLIC_UI_EXPOSURE_AUDIT.md` | **Slightly stale** — no continue.html |
| `KYC_PRODUCTION_HARDENING.md` | Partially current — filesystem storage accurate |

### 7. `render.yaml`

```yaml
# Present: ENVIRONMENT, SMTP_*, DATABASE_URL (dead)
# Missing: OPS_PASSWORD, OPS_SECRET, INTAKE_TOKEN_SECRET, PUBLIC_BASE_URL, OPS_API_KEY, DIGEST_EMAIL_TO
```

- `healthCheckPath: /healthz` — will not fail deploy when SMTP missing.
- `autoDeploy: true` — pushes to main deploy; uncommitted local work not included.

### 8. Environment Handling

- `services/config.py` loads `.env` via `python-dotenv`; aliases for SMTP vars supported.
- `.env` gitignored (PASS) — but local file contains live credentials; rotate if ever exposed.
- Settings singleton loaded at import — env changes require process restart.
- No validation that `PUBLIC_BASE_URL` matches deployed domain (prod currently correct via Render env).

### 9. Authentication

| Mechanism | Status |
|-----------|--------|
| Ops session cookie (`kyc_ops_session`) | Working — secure flag in production |
| `OPS_PASSWORD` login | Required for protected routes (503/403/302 when unset) |
| `X-Ops-Key` / `OPS_API_KEY` | Working for test kickoff in production mode |
| Intake token | Signed; no expiry |
| Continuation token | 90-day expiry (local code) |
| Evidence upload | **No token required** |
| CoC JSON event | **No auth** |

### 10. Upload Security

- Filename sanitization via `safe_upload_filename()` — strips path components.
- 50MB size limit on evidence register.
- Project ID validation (`P-*`, must exist).
- **No bearer/token required** for upload — knowledge of project_id is sufficient.
- Upload guidance/session endpoints optionally validate token when provided.

### 11. Public / Private Routes

See `services/ops_auth.py` lists. Notable **public write** routes:

- `POST /api/inquiry/submit`
- `POST /api/intake/submit` (token required in form)
- `POST /api/evidence/register` (no token)
- `POST /api/coc/event` (no auth)
- `POST /api/telemetry/event` (no auth)
- `POST /api/customer/continuation/event` (continuation token)
- `POST /webhooks/stripe` (signature when configured)

### 12. Customer Flow (inquiry → intake → upload)

```
inquiry.html → POST /api/inquiry/submit
  → kickoff() → project_id, intake_url, upload_url [, continuation_url local only]
  → [email skipped — SMTP false]
intake.html?token= → GET /api/intake/resolve → POST /api/intake/submit
upload.html → POST /api/evidence/register (project_id only)
```

**Live:** Steps 1–3 functional without email.  
**Local-only:** continuation.html, QR resume, upload guidance API, session persistence.

### 13. Operator Flow

- Login at `/ui/login.html` → control/memory/command surfaces.
- Cockpit, guidance, bottlenecks, SMTP status — protected APIs.
- SMTP test email endpoint — auth required; returns 503 when SMTP unconfigured.

### 14. Data Persistence

- Filesystem under `data/` — projects, ledger, jobs, inquiries, memory jsonl.
- Render persistent disk assumed (data_writable: true on prod).
- No PostgreSQL on main path despite `DATABASE_URL` in render.yaml.
- Ledger append-only log; artifact registration computes SHA256.

### 15. Central Memory Links

| Event | Linked? | Test |
|-------|---------|------|
| inquiry_submitted | YES | PASS |
| project_created | YES | PASS |
| intake_completed | YES | PASS |
| ledger_event (ORDER) | **NO** | **FAIL** |
| evidence_uploaded | YES | PASS |

### 16. Telemetry

- `services/memory/telemetry.py` — organism telemetry jsonl; emitted on health, email, friction events.
- `drafts/telemetry_fastapi_endpoint.py` — separate public POST endpoint writing to `data/telemetry/daily/` — unauthenticated.

### 17. SMTP

| Item | Status |
|------|--------|
| Code path | Complete — STARTTLS, structured results, operator test |
| render.yaml | Declares SMTP vars (sync: false) |
| Production | **`smtp_configured: false`** |
| Customer impact | No welcome email; inquiry notify skipped unless `DIGEST_EMAIL_TO` + SMTP |

### 18. QR / Magic Continuation Upload

**Local code (uncommitted):**

- `make_continuation_token` / `parse_continuation_token` (90-day TTL)
- `/ui/continue.html`, `/api/customer/continuation/resolve`, `/api/customer/qr.svg`
- Kickoff returns `continuation_url` in API response
- `tests/test_customer_friction_layer.py` — 16 tests (not in CI until committed)

**Production:** `/ui/continue.html` → **404** — feature absent.

### 19. CI Guardrails (`.github/workflows/kyc_guardrails.yml`)

| Job step | Scope |
|----------|-------|
| Static guardrails | `test_kyc_guardrails.py` |
| Public UI exposure | `test_public_ui_exposure.py` |
| Ops route auth | `test_ops_route_auth.py` |
| Central memory | `test_central_memory.py` |
| Organism observability | `test_organism_observability.py` |
| Operator guidance | `test_operator_guidance.py` |
| Full suite | `pytest tests/` — **would fail today** |

**Gaps:** No dedicated SMTP prod check, no unauthenticated-write regression tests, customer friction tests not in workflow until committed.

---

## Dead Code / Stale Docs

### Dead code candidates

- `services/server.py` — duplicate coc/evidence stubs
- `services/engine.py.bak`, `services/engine.py.bak_queue_fix`
- `backups/server_pre_telemetry_router.py`
- `ui_backup_before_client_redesign_20260517-172621/` — entire tree
- `server.py` lines 129–138 (`safe_load_json`, empty `cfg`)

### Stale documentation

- `docs/KYC_FINAL_PRODUCTION_VERDICT.md` — pre-custom-domain snapshot
- `docs/KYC_PRODUCTION_LOCK_CONFIRMED.md` — claims lock not achieved; still accurate on SMTP
- `docs/KYC_OWNER_BLOCKER_CLOSEOUT_TASK18.md` — likely partially resolved (domain now works)
- `scripts/verify-render-production.ps1` — wrong canonical host

---

## Production Readiness Verdict

### **GO WITH CONDITIONS**

| Criterion | Met? |
|-----------|------|
| Custom domain serves app | YES |
| Inquiry onboarding active | YES |
| Intake secret rotated | YES |
| Ops routes protected | YES |
| SMTP configured | **NO** |
| Customer email self-service | **NO** |
| Unauthenticated write routes hardened | **NO** |
| Local == deployed code | **NO** |
| Full test suite green | **NO** |

---

## Blocker remediation (2026-05-26)

| Blocker | Status | Notes |
|---------|--------|-------|
| F-04 Ledger → central memory | **FIXED** | `kickoff()` passes `entity_id` from `safe_link_after_kickoff` into `safe_link_ledger_event`; existing-order path links ORDER ledger too |
| F-02 `POST /api/coc/event` public | **FIXED** | `require_ops_access` + `/api/coc/event` in `PROTECTED_API_PREFIXES`; tests in `test_ops_route_auth.py` |
| render.yaml env contract | **FIXED** | `OPS_PASSWORD`, `OPS_SECRET`, `OPS_API_KEY`, `INTAKE_TOKEN_SECRET`, `PUBLIC_BASE_URL`, SMTP vars documented (`sync: false`) |
| Test suite | **PASS** | `238 passed` locally after fixes |
| SMTP production | **OPERATOR** | Live `smtp_configured: false` — `SMTP_ENABLED` not `true` on Render; set `SMTP_ENABLED=true` plus host/user/pass/from |

**Production readiness (post-fix deploy):** Deploy commit with blocker fixes, then set `SMTP_ENABLED=true` on Render. Until then, inquiry/intake/upload work; email delivery remains off.

### Conditions before full GO

1. Configure SMTP on Render — set `SMTP_ENABLED=true`, host, user, pass, from email; confirm `/health/ready` shows `smtp_configured: true`.
2. Deploy blocker-fix commit to production.
3. (Optional) Protect or disable `POST /api/telemetry/event` draft router.
4. Verify CI passes on `main`.

---

## Recommended Fix Order

1. **Configure SMTP on Render** — set `SMTP_ENABLED=true`, host, user, pass, from email; verify `/health/ready` and operator test email.
2. **Harden public write routes** — add `/api/coc/event` and `/api/telemetry/event` to `PROTECTED_API_PREFIXES` (or disable telemetry router in production).
3. **Fix ledger → central memory link** — debug `safe_link_ledger_event` on inquiry kickoff; make `test_ledger_event_writes_central_memory` pass.
4. **Commit + deploy pending work** — customer friction layer, email improvements, render.yaml, requirements.txt (`qrcode`).
5. **Update render.yaml** — add `OPS_PASSWORD`, `INTAKE_TOKEN_SECRET`, `PUBLIC_BASE_URL`, `OPS_API_KEY`, `DIGEST_EMAIL_TO`; remove or document dead `DATABASE_URL`.
6. **Require token for evidence upload** — or HMAC project-scoped upload secret; update `test_upload_flow.py`.
7. **Add intake token max_age** — align with continuation token (90 days or shorter).
8. **Restrict CORS** — replace `allow_origins=["*"]` with production domain(s).
9. **Update verification scripts** — point `verify-render-production.ps1` at `compliance.keepyourcontracts.com`.
10. **Clean up dead code/backups** — remove `.bak` files and `ui_backup_*` tree or move outside repo.
11. **Refresh stale docs** — mark historical verdict docs; update `LAUNCH_PATH.md` SMTP from "optional" to "required for email delivery".
12. **Add CI regression tests** — unauthenticated write probes for coc/telemetry endpoints.

---

## Appendix: Mock / Secret Grep Summary

| Pattern | Location | Assessment |
|---------|----------|------------|
| `_DEV_INTAKE_SECRET` | `production.py` | Dev guard constant — OK |
| `MOCK_PRODUCTION` | tests only | OK |
| `is_mock_domain` | acquisition | Production guard — OK |
| `.env SMTP_PASSWORD` | local only, gitignored | Hygiene — OK |
| No hardcoded prod secrets in committed code | — | PASS |

---

*End of audit. Generated 2026-05-26 by stem-to-stern audit pass.*

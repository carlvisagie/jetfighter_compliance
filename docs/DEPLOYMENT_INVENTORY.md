# KYC Platform — Deployment Readiness Inventory

_Last refresh: 2026-06-03 — full test suite **818/818 passing**._

This file is the single source of truth for "what is deploy-ready and what
still needs attention." Operators and engineers should consult it before
shipping. It is generated against the actual codebase (not a wish list).

---

## 0. Top-line status

| Indicator | Value |
| --- | --- |
| Backend service | `kyc-backend` (FastAPI on Render Docker, plan `starter`) |
| Healthcheck | `GET /healthz` |
| Production domain | `compliance.keepyourcontracts.com` |
| Render fallback domain | `jetfighter-compliance.onrender.com` |
| Persistent disk | `kyc-data` → `/var/data` (10 GB) |
| Python entrypoint | `server.py` (100 routes) |
| Test suite | **818 tests, 100% green** (~22 min cold run) |
| Service packages | 10 (`services/*/__init__.py`) |
| Organism Core (extracted) | `organism_core/` (domain-agnostic awareness layer) |

---

## 1. GREEN — Production-ready, deploy as-is

### 1.1 Intake pipeline (the heart)
- **Customer surface:** `/ui/intake` (`ui/intake.html`)
- **Upload API:** `POST /api/intake/upload`
- **Operator queue:** `GET /api/operator/intake/queue`
- **Operator audit:** `GET /api/operator/intake/{id}/audit`
- **Operator file access:** list / view / download endpoints under `/api/operator/intake/{id}/files/`
- **Durability:** `services/intake/durable_root.py` refuses uploads in production
  if `/var/data` mount probe fails. Every upload is fsync'd, hash-ledgered,
  and verified before the operator queue exposes it.
- **Forensic proof gate:** `services/intake/proof_gate.py` blocks the system
  from claiming a successful upload until file count + hashes are reconciled.
- **Reconcile:** `GET /api/operator/intake/reconcile` (fleet view) and
  `/api/operator/intake/reconcile/{id}` (single intake).
- **Raw disk scan:** `/api/operator/intake/raw-disk-scan` — never cached.
- **Test coverage:** 87 hardening / durability / integrity tests, all green.

### 1.2 Visual Intelligence Observatory (VIO 2.0)
- **UI:** `ui/vio.html` + `ui/assets/js/vio.js` + `ui/assets/styles/vio.css`
- **Overview API:** `GET /api/operator/vio/overview` — includes a global
  `organism` block (system health, bottleneck, mismatches) cached 45s.
- **Per-company composite API:** `GET /api/operator/vio/company/{intake_id}`
  — returns uploaded docs (with view/download URLs), generated docs,
  missing docs, evidence summary, identifiers, and derived findings
  (extraction failures, payment-link stale, file-on-disk mismatch, etc.).
- **Header organism strip:** live system awareness pinned at top of VIO.
- **Status:** functionally complete. Polish remaining is cosmetic only.

### 1.3 Awareness / organism layer
- **`organism_core/`** — domain-agnostic, reusable package:
  awareness engine, signals, health checks, severity, recommendations,
  residue scanner, snapshot persistence.
- **`services/organism_state/`** — KYC bindings:
  collectors, checks, derivation, recommendations, residue patterns.
- **API surface:**
  - `GET /api/operator/organism/state` — current organism snapshot
  - `GET /api/operator/organism/history` — recent snapshots
  - `GET /api/cognitive-topology` — high-level subsystem map
  - VIO overview embeds the latest organism summary
- **Recursion guard:** `VioCollector` calls `build_vio_overview(include_organism=False)`
  to prevent infinite re-entry through the organism summary.

### 1.4 Email pipeline
- **Adapter architecture:** `services/emails.py` + `services/email_adapters/`
  (Resend primary, SMTP fallback). Provider-agnostic.
- **Forensic logging:** every send goes through the central service and is
  appended to the communications ledger (`services/intake/communications.py`).
- **Resend:** Cloudflare-friendly headers (`User-Agent`, `Accept`) in
  `services/email_adapters/resend_adapter.py`.
- **SMTP:** generic, no Gmail-specific assumptions.
- **Production env vars wired** in `render.yaml` (RESEND_API_KEY,
  RESEND_FROM_EMAIL, SMTP_*).

### 1.5 Authentication
- Operator login: `/api/ops/login` (cookie session) — middleware in
  `server.py` gates every `/api/operator/*` and ops surface.
- API key fallback: `OPS_API_KEY` header for scripts.
- Public surfaces are explicitly allow-listed in
  `services/ops_auth.py` / `services/public_ui.py`.

### 1.6 CORS (fixed this pass)
- **Production**: locked to `compliance.keepyourcontracts.com` and
  `jetfighter-compliance.onrender.com`.
- **Local dev / preview / tests**: `*` (when `ENVIRONMENT != production`).
- Override via `CORS_ALLOW_ORIGINS` env var (comma-separated) — no code
  change needed for additional domains.

### 1.7 Test suite hygiene (fixed this pass)
- `pytest.ini` added — collection scoped to `tests/`; the abandoned
  `organism/` SQLAlchemy prototype is excluded.
- All 113 stale `/api/founding-beta/*` URL references rewritten to the
  canonical `/api/intake/*` and `/api/operator/intake/*` paths.
- 7 surface-rename assertions updated to match current HTML/JS.
- Total: **818 passing, 0 failing.**

---

## 2. AMBER — Works, but flagged for attention soon

| Area | Status | Notes |
| --- | --- | --- |
| **Legacy JS symbol names** | works | `loadFoundingBetaIntake`, `renderFoundingBeta`, `CockpitFoundingBeta` are still the internal function/module names inside `ui/control.html` & `ui/assets/js/cockpit-intake.js`. User-facing HTML IDs / file names are already renamed. Internal rename is a low-risk cleanup, can be a follow-up PR. |
| **`services/founding_beta`** | thin compat shim | If anything imports from it, refactor to `services.intake`. Residue scanner catches this automatically. |
| **`services/customer_session.py`** | works | Still logs "session_upload_shim" — leave as audit breadcrumb but rename log labels in next sweep. |
| **Reddit autonomous acquisition** | needs creds | All four `REDDIT_*` env vars are `sync: false` — they must be set in Render before the connector will post. Without them, the connector is harmless (no posts, no errors). |
| **DATABASE_URL** | reserved | Listed in `render.yaml` but the platform is currently file-system + JSONL backed. Keep the env var defined; no migration required today. |
| **`docs/KYC_FOUNDING_BETA_DOCTRINE.md` etc.** | historical | Retain as platform history; new docs should reference "intake" only. |

---

## 3. RED — Must be confirmed before launch

| Item | Required action | Owner |
| --- | --- | --- |
| **Render persistent disk attached** | Verify `kyc-data` (10 GB) is physically mounted at `/var/data` in the production service. Without it, uploads will be refused (this is by design — see `services/intake/durable_root.py`). Check via Render dashboard → service → Disks. | Operator |
| **OPS_PASSWORD / OPS_SECRET / OPS_API_KEY** | Set in Render (all marked `sync: false`). Logging in to `compliance.keepyourcontracts.com/ui/control.html` is impossible without `OPS_PASSWORD`. | Operator |
| **INTAKE_TOKEN_SECRET** | Set in Render. Required for magic-link tokens issued at upload time; missing secret → broken customer redirect from `/api/customer/session/complete`. | Operator |
| **PUBLIC_BASE_URL** | Set in Render to `https://compliance.keepyourcontracts.com`. Magic links, QR codes, and email CTAs all use this. | Operator |
| **RESEND_API_KEY + verified `RESEND_FROM_EMAIL`** | Set in Render. Confirm `keepyourcontracts.com` is verified in Resend → Domains. Without this, the SMTP fallback will be used. | Operator |
| **DNS cutover** | Confirm `compliance.keepyourcontracts.com` resolves to Render. See `docs/NAMECHEAP_RENDER_DNS_CUTOVER.md`. | Operator |
| **Post-deploy VIO smoke test** | `scripts/seed_vio_live.py` to verify the 5 manufactured companies render correctly in the VIO detail panel on production. | Operator |

---

## 4. Endpoint reality check

Operator-facing routes counted from `server.py`:

- **Public:** `/healthz`, `/ui/intake`, `/ui/control.html`, `/ui/vio.html`,
  `/api/customer/session/*`, `/api/intake/upload`,
  `/api/payment/*` (webhook + redirect surfaces).
- **Operator (auth required):**
  - intake: `/api/operator/intake/queue`, `/diagnostics`, `/reconcile`,
    `/reconcile/{id}`, `/raw-disk-scan`, `/{id}/audit`, `/{id}/files`,
    `/{id}/files/{filename}/{view,download}`, `/retention-check/{id}`,
    `/action`
  - VIO: `/api/operator/vio/overview`, `/api/operator/vio/company/{id}`
  - organism: `/api/operator/organism/state`, `/history`
  - diagnostics: `/api/operator/telemetry-status`, `/storage-status`,
    `/audit-log`, etc.
- Total: **100 registered routes** in `server.py`.

---

## 5. What this pass changed

1. **`pytest.ini`** — added; suite now collects in 0.4s.
2. **`server.py`** — CORS restricted in production.
3. **`services/intake/auto_payment.py`** — fixed `_send_payment_link` wrapper
   to forward `update_status` kwarg (was eating the arg → TypeError at runtime).
4. **`services/acquisition/routing.py`, `services/acquisition/orchestration.py`,
   `services/customer_session.py`, `services/intake/intake.py`,
   `ui/assets/js/customer-session-flow.js`** — replaced all backend
   references to `/ui/founding-beta` with `/ui/intake`.
5. **`tests/` (19 files)** — 113 stale `/api/founding-beta/*` URLs rewritten
   to canonical `/api/intake/*` and `/api/operator/intake/*`; 7 stale UI
   assertions updated to match the post-rebrand HTML and JS.
6. **`docs/DEPLOYMENT_INVENTORY.md`** — this file (replaces the old brief).

---

## 6. How to deploy

```
git push origin main
# Render watches main → autoDeploy: true → builds Docker → boots /healthz
```

Pre-flight (one-time, in Render dashboard):
1. Confirm disk `kyc-data` is attached and `KYC_DATA=/var/data`.
2. Set all `sync: false` env vars listed in §3.
3. Confirm DNS for `compliance.keepyourcontracts.com` points to Render.

Post-flight smoke (every deploy):
1. `curl -fsS https://compliance.keepyourcontracts.com/healthz`
2. Log into `/ui/control.html`, confirm queue loads.
3. Visit `/ui/vio.html`, confirm organism strip + 5 seeded companies.
4. Run `python scripts/seed_vio_live.py` if data is missing.

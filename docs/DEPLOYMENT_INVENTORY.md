# KYC Platform — Deployment Readiness Inventory

_Capability inventory only — not live production counts._

**Live production snapshot** (commit SHA, test count, risks): [`PRODUCTION_TRUTH_AUDIT.md`](PRODUCTION_TRUTH_AUDIT.md)  
**Deploy gate:** [`DEPLOYMENT_GATE.md`](DEPLOYMENT_GATE.md)  
**Governance:** [`PRODUCTION_CONSTITUTION.md`](PRODUCTION_CONSTITUTION.md)

This file tracks **what is deploy-ready and what still needs attention** at the feature level. It is generated against the actual codebase (not a wish list).

---

## 0. Top-line status

| Indicator | Value |
| --- | --- |
| Backend service | **Live Render dashboard name:** `jetfighter_compliance` (Blueprint name in `render.yaml`: `kyc-backend`). FastAPI on Render Docker, plan `starter`. Open the dashboard name when working in the Render UI. |
| Healthcheck | `GET /healthz` |
| Production domain | `compliance.keepyourcontracts.com` |
| Render fallback domain | `jetfighter-compliance.onrender.com` |
| Persistent disk | `kyc-data` → `/var/data` (10 GB) |
| Python entrypoint | `server.py` (100 routes) |
| Test suite | See [`PRODUCTION_TRUTH_AUDIT.md`](PRODUCTION_TRUTH_AUDIT.md) for current count |
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

### 1.2 Visual Intelligence Observatory — Levels 1 and 2
- **Doctrine:** [`docs/VIO_DOCTRINE.md`](./VIO_DOCTRINE.md) — the binding
  visual-language and motion charter the VIO build is implemented against.
  Companion to [`docs/VIO_CONSTITUTION.md`](./VIO_CONSTITUTION.md).
- **UI:** `ui/vio.html` + `ui/assets/js/vio.js` (Level 1) +
  `ui/assets/js/vio-level2.js` (Level 2) + `ui/assets/styles/vio.css`.

#### Level 1 — the unified line view
- **Surface:** every company renders as one continuous SVG trace through the
  7-stage backbone (`intake → classification → validation → evidence_mapping
  → review → approval → conversion`), with a single allowed branch for
  `client follow-up`. Lines are urgency-sorted top-down, `done` companies
  always last. Stillness is the baseline; the only animation in the system
  is a 4-second breathe on `waiting_client`.
- **Overview API:** `GET /api/operator/vio/overview` — each company row
  carries `stage`, `stage_index`, `stage_state`, `urgency_score`,
  `days_in_stage`, `on_branch`, `branch_label`, and `attention[]` alongside
  the legacy `state`, `timeline`, and `quick_stats` for back-compat. Includes
  a global `organism` block (system health, bottleneck, mismatches),
  cached 45 s, plus `stage_backbone` and `stage_counts` for the header
  legend.

#### Level 2 — the immersive landscape
- **Surface:** clicking any Level 1 trace takes the page over with a
  full-screen horizontal landscape. The company orb anchors the left; the
  same 7-stage spine runs right; perpendicular branches sprout up and down
  from the stages **only where data warrants it** — clean companies render
  as a clean spine, complex companies render bushy. Branches: context,
  identifiers, service tier, generated paperwork (above the spine); papers
  uploaded, missing documents, findings, payment, project (below the spine).
- **Leaves:** every leaf has a distinct silhouette (folded pages for uploads,
  double-bordered pages for generated, dashed empty pages for gaps, triangles
  for findings, pills for identifiers, payment cards with magnetic band,
  hexagons for projects). Every visual element is clickable; click opens a recursive
  side panel with the full per-leaf detail (file metadata + view/download
  for documents, severity + hint for findings, why-this-matters + example
  for gaps, paid/amount/link for payment, etc.). Click the orb or a stage
  anchor to surface overview / stage-meaning. ESC or back-chevron returns
  to Level 1.
- **Doctrine-compliant:** stillness baseline preserved; the only animation
  in Level 2 is the same `waiting_client` breathe on the orb. Hover gives
  a 1-px stroke bump on leaves — that is the entire interactive treatment.
- **Per-company composite API:** `GET /api/operator/vio/company/{intake_id}`
  — feeds Level 2 directly. Returns uploaded docs (with view/download
  URLs), generated docs, missing docs, evidence summary with extracted
  identifiers (technologies, vendors, compliance refs, company names),
  intake context block, payment, and derived findings (extraction failures,
  payment-link stale, file-on-disk mismatch, etc.).
- **Header organism strip (both levels):** live system awareness pinned at
  the top of VIO. Silent when the organism is healthy.
- **Defensive hygiene:** `services/vio_overview._clean_company_name`
  scrubs URL-pasted company fields down to the apex domain, both at
  display time and at intake creation. Covered by
  `tests/test_vio_company_name_sanitiser.py`.
- **Contract tests:**
  `tests/test_vio_document_visibility.py` (Level 1 + composite API),
  `tests/test_vio_level2_contract.py` (Level 2 payload shape),
  `tests/test_vio_company_name_sanitiser.py` (defensive hygiene).
- **Status:** Levels 1 and 2 functionally complete and doctrine-compliant.

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
- All stale legacy-intake URL references rewritten to the canonical
  `/api/intake/*` and `/api/operator/intake/*` paths (113 fixes across
  19 test files).
- 7 surface-rename assertions updated to match current HTML/JS.
- Total: **818 passing, 0 failing.**

---

## 2. AMBER — Works, but flagged for attention soon

| Area | Status | Notes |
| --- | --- | --- |
| **Legacy internal JS symbol names** | works | Some module-internal function names inside `ui/control.html` & `ui/assets/js/cockpit-intake.js` still carry the pre-rebrand prefix. User-facing HTML IDs and file names are already renamed. Internal rename is a low-risk cleanup, can be a follow-up PR. |
| **Legacy intake compat shim** | works | A thin compatibility module remains under `services/` for any straggler import. Refactor any new imports to `services.intake`; the residue scanner catches reintroduction automatically. |
| **`services/customer_session.py`** | works | Still logs "session_upload_shim" — leave as audit breadcrumb but rename log labels in next sweep. |
| **Reddit autonomous acquisition** | needs creds | All four `REDDIT_*` env vars are `sync: false` — they must be set in Render before the connector will post. Without them, the connector is harmless (no posts, no errors). |
| **DATABASE_URL** | reserved | Listed in `render.yaml` but the platform is currently file-system + JSONL backed. Keep the env var defined; no migration required today. |
| **Historical pre-rebrand docs** | retained | Older doctrine docs from the pre-rebrand era remain in `docs/` as platform history; new docs reference "intake" only. |

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
   references to the pre-rebrand customer URL with `/ui/intake`.
5. **`tests/` (19 files)** — 113 stale pre-rebrand API URLs rewritten
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

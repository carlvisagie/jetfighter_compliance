# KeepYourContracts — Production Hardening

**Date:** 2026-05-19  
**Mode:** Stabilization — boring operational reliability  
**Service:** Render `kyc-backend` (Docker, `server:app`, port 10000)

---

## Runtime assumptions

| Assumption | Truth |
|------------|--------|
| Process model | Single FastAPI process + background APScheduler worker |
| Storage | Filesystem under `data/` (projects, ledger, jobs, inquiries) — **not** `DATABASE_URL` on main path |
| Static UI | `ui/` mounted at `/ui` |
| Public URL | `get_public_base_url()` → `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL` |
| Commerce | Stripe Payment Links + `POST /webhooks/stripe` — no Shopify |
| Email | Optional SMTP; kickoff works without email (links still returned in API) |

---

## Startup assumptions

On `startup` event:

1. Log **warnings** from `startup_warnings()` (misconfig, dead env vars).
2. Start background **worker** (`services/engine.py`) — failure logged, process continues.
3. Log **readiness** snapshot (data writable, public base URL).

App **does not exit** on missing Stripe/SMTP — degraded mode with logged warnings.

---

## Deployment assumptions

| Item | Value |
|------|--------|
| Platform | Render web service `kyc-backend` |
| Build | `Dockerfile` → `uvicorn server:app --host 0.0.0.0 --port 10000` |
| Health check | `GET /healthz` → `{"ok":true}` (liveness only) |
| Blueprint | `render.yaml` — **do not auto-sync** per Owner stabilization rule |
| Custom domain | `keepyourcontracts.com` — **not live on backend** until DNS fixed |

---

## Environment variable classification

### REQUIRED (production operations)

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | Set to `production` on Render |
| `INTAKE_TOKEN_SECRET` | Sign intake tokens — **must not** stay `dev-dev-dev-dev-dev` |
| `STRIPE_WEBHOOK_SECRET` | Verify Stripe `checkout.session.completed` webhooks |
| `PUBLIC_BASE_URL` **or** `RENDER_EXTERNAL_URL` | Correct intake/upload links in email (Render sets latter automatically) |

### OPTIONAL (enhanced operations)

| Variable | Purpose |
|----------|---------|
| `SMTP_ENABLED`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` | Kickoff + inquiry notification email |
| `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` | From header |
| `DIGEST_EMAIL_TO` | Inquiry alerts + digests |
| `OPS_API_KEY` | Unlocks test kickoff routes in production via `X-Ops-Key` header |
| `AUTO_NIGHT_EXPORT`, `WEEKLY_DIGEST`, `EXPORT_KEEP_LATEST` | Reporting worker |
| `DATABASE_URL` | Listed in blueprint; **not used** by main `server.py` path today |

### REMOVE (dead / decommissioned)

| Variable | Reason |
|----------|--------|
| `SHOPIFY_WEBHOOK_SECRET` | Shopify removed |
| `SHOPIFY_SECRET` | Unused |
| `STRIPE_SECRET` | In blueprint but **not read** by code (Payment Links are dashboard-only unless future API use) |

---

## Operational topology

```
Internet
   │
   ├─ keepyourcontracts.com ──► Cloudflare (WRONG ORIGIN today — placeholder)
   │
   └─ jetfighter-compliance.onrender.com ──► kyc-backend (FastAPI)
         │
         ├─ /healthz, /health/ready
         ├─ /ui/*  (static)
         ├─ /webhooks/stripe
         ├─ /api/inquiry/submit, /api/intake/*, /api/evidence/register
         └─ data/  (persistent disk on Render — verify attached)
```

---

## Security findings

| Finding | Severity | Mitigation applied |
|---------|----------|-------------------|
| Test kickoff open in prod | Medium | `POST /events/payment/test` + `/api/test-webhook` require `OPS_API_KEY` when `ENVIRONMENT=production` |
| CORS `allow_origins=["*"]` | Low | Documented; restrict when custom domain stable |
| `/api/projects` lists project IDs | Low | Required for ops UI (`new_client`, `control`); accepted |
| Upload without project check | Medium | `validate_project_id()` + filename sanitization |
| Path traversal via filename | Medium | `safe_upload_filename()` |
| Stripe webhook unsigned | High | HMAC verify; 503 if secret missing |
| Default intake secret | High | Startup warning + readiness flag |
| Intake token in URL | Low | Expected; HTTPS required on public domain |
| `GET /api/ping-host.json` | Low | SSRF-style probe — ops only; no change this task |

---

## Hardening actions (this task)

| Action | Location |
|--------|----------|
| Startup config warnings | `services/production.py` → `startup_warnings()` |
| Readiness endpoint | `GET /health/ready` |
| Ops route guard | `require_ops_access()` on test kickoff routes |
| Evidence upload validation | `validate_project_id`, `safe_upload_filename`, 50MB cap |
| Inquiry response includes `upload_url` | `server.py` |
| Payment test payload validation | `extract_generic` try/except |

---

## Rollback

Revert `services/production.py` and related `server.py` guards if ops workflows break. Set `ENVIRONMENT=development` on Render to restore open test routes (not recommended for public URL).

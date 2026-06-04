# KYC operator authentication

Internal UI and APIs require an operator session or `X-Ops-Key`. **No alternate auth routes** (Bearer, `X-OPS-PASSWORD`, etc.).

## Server contract

| Mode | Client | Server check |
|------|--------|--------------|
| **Session** | `POST /api/ops/login` `{"password":"<OPS_PASSWORD>"}` → cookie `kyc_ops_session` | `OPS_PASSWORD` env on server |
| **API key** | Header `X-Ops-Key: <OPS_API_KEY>` | `OPS_API_KEY` env on server |

## Production scripts (password only)

All production HTTP scripts use `scripts/lib/ops_client.py` — **one path**:

1. Load `OPS_PASSWORD` (and optional `PROD_BASE_URL`) from repo-root **`.ops_env`** only (gitignored).
2. `GET /api/public/build-info` on branded + Render URLs — commits must match (when `verify_deploy=True`).
3. `GET /api/ops/session` — server must have `password_configured`.
4. `POST /api/ops/login` → session cookie on the shared `httpx.Client`.
5. `GET /api/ops/auth-check` — must return 200 with `auth_mode: session_cookie`.

If `OPS_API_KEY` is set in the environment, scripts **fail fast** with `scripts_use_ops_password_only`. Do not put `OPS_API_KEY` in `.ops_env`.

```python
from scripts.lib.ops_client import authenticate_production, OpsAuthError

client, headers, diag = authenticate_production()
# headers is always {}; cookies live on client
```

Example `.ops_env` (repo root, never commit):

```
OPS_PASSWORD=your-render-dashboard-password
PROD_BASE_URL=https://compliance.keepyourcontracts.com
```

## Environment (server / UI)

| Variable | Purpose |
|----------|---------|
| `OPS_PASSWORD` | Password for `/ui/login.html` and `POST /api/ops/login` |
| `OPS_SECRET` | Session cookie signing (falls back to `INTAKE_TOKEN_SECRET`) |
| `OPS_API_KEY` | Header auth (`X-Ops-Key`) — **not used by production scripts** |

## Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/public/build-info` | Public | `service`, `git_commit`, `environment` |
| `GET /api/ops/session` | Public | `password_configured`, `api_key_configured`, `auth_contract` |
| `GET /api/ops/auth-check` | Ops | Confirms auth + returns `data_root`, `git_commit` |
| `POST /api/ops/login` | Public | Session login |
| `GET /api/ops/boot-status` | Public | Cached boot snapshot |

## Routes

- **Public UI:** shop, inquiry, intake, upload, login, continue, `/ui/assets/*` (see `services/ops_auth.py::PUBLIC_PAGES`)
- **Protected UI:** control, memory, command, vio, … → redirect to `/ui/login.html`
- **Protected API:** `/api/operator/*`, `/api/ops/auth-check`, `/api/memory/*`, … → **403** without auth
- **Public API:** `/healthz`, `/health/ready`, `/api/public/*`, `/api/intake/*` (upload-first customer intake — `upload`, `resolve`, `submit`, `extend`, `complete`, `payment-link`)

> Historical note: `/api/founding-beta/*` and `/ui/founding-beta` were hard-deleted on 2026-05-29 (commit `fabdbc8`). The customer-facing upload path is now `/api/intake/upload`; the operator surface lives under `/api/operator/intake/*`. See `docs/FOUNDING_BETA_RENAME_PLAN.md` for the remaining nomenclature work.

Cookie: `kyc_ops_session` (httponly, 7-day max age, `secure` in production).

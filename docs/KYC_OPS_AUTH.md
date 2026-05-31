# KYC operator authentication

Internal UI and APIs require an operator session or `X-Ops-Key`. **No alternate auth routes.**

## Canonical contract

| Mode | Client | Server check |
|------|--------|--------------|
| **API key** | Header `X-Ops-Key: <OPS_API_KEY>` | `OPS_API_KEY` env on server |
| **Session** | `POST /api/ops/login` `{"password":"<OPS_PASSWORD>"}` → cookie `kyc_ops_session` | `OPS_PASSWORD` env on server |

**Not supported:** `Authorization: Bearer`, `X-OPS-PASSWORD`, `X-OPS-API-KEY`, or custom headers.

## Environment

| Variable | Purpose |
|----------|---------|
| `OPS_PASSWORD` | Password for `/ui/login.html` and `POST /api/ops/login` |
| `OPS_SECRET` | Session cookie signing (falls back to `INTAKE_TOKEN_SECRET`) |
| `OPS_API_KEY` | Header auth for scripts (`X-Ops-Key`) — preferred for automation |

## Script helper

All production scripts use `scripts/lib/ops_client.py`:

```python
from scripts.lib.ops_client import authenticate_production, OpsAuthError

client, headers, diag = authenticate_production()
# session mode: headers={}; use same client (cookies)
# api_key mode: headers={"X-Ops-Key": "..."}
```

Flow:

1. `GET /api/public/build-info` on branded + Render URLs — commits must match
2. `GET /api/ops/session` — verify server auth config
3. Authenticate (API key preferred if `OPS_API_KEY` set, else session login)
4. `GET /api/ops/auth-check` — must return 200

## Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/public/build-info` | Public | `service`, `git_commit`, `environment` |
| `GET /api/ops/session` | Public | `password_configured`, `api_key_configured`, `auth_contract` |
| `GET /api/ops/auth-check` | Ops | Confirms auth + returns `data_root`, `git_commit` |
| `POST /api/ops/login` | Public | Session login |
| `GET /api/ops/boot-status` | Public | Cached boot snapshot |

## Routes

- **Public UI:** shop, inquiry, intake, upload, login, founding-beta, `/ui/assets/*`
- **Protected UI:** control, memory, command, … → redirect to `/ui/login.html`
- **Protected API:** `/api/operator/*`, `/api/ops/auth-check`, `/api/memory/*`, … → **403** without auth
- **Public API:** `/healthz`, `/health/ready`, `/api/public/*`, `/api/founding-beta/*`

Cookie: `kyc_ops_session` (httponly, 7-day max age, `secure` in production).

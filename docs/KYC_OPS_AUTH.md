# KYC operator authentication

Internal UI and APIs require an operator session or `X-Ops-Key`.

## Environment

| Variable | Purpose |
|----------|---------|
| `OPS_PASSWORD` | Password for `/ui/login.html` and `POST /api/ops/login` |
| `OPS_SECRET` | Session cookie signing (falls back to `INTAKE_TOKEN_SECRET`) |
| `OPS_API_KEY` | Optional header auth for scripts (`X-Ops-Key`) |

Set `OPS_PASSWORD` on Render for production. Without it, protected routes return **503** (config) or redirect to login with `?error=config`.

## Routes

- **Public UI:** `shop`, `inquiry`, `intake`, `upload`, `login`, `index`, `vendor_quote`, `/ui/assets/*`
- **Protected UI:** control, memory, command, status, inbox, readiness/*, etc. → redirect to `/ui/login.html`
- **Protected API:** `/api/memory/*`, `/api/operator/*`, `/api/knowledge/*`, `/api/projects`, `/api/project/*`, `/api/events/*`, … → **403** JSON
- **Public API:** `/healthz`, `/health/ready`, `/api/inquiry/*`, `/api/intake/*`, `/api/evidence/register`

## Session

Cookie: `kyc_ops_session` (httponly, 7-day max age, `secure` in production).

Logout: `POST /api/ops/logout`

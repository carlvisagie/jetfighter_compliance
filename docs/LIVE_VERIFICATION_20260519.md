# Live Verification Log — 2026-05-19

**Probe host:** `jetfighter-compliance.onrender.com`  
**Verdict:** Service **up**; stabilization code **not yet live** on this host.

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /healthz` | 200 | OK |
| `GET /health/ready` | 404 | Deploy pending |
| `POST /api/inquiry/submit` | 404 | Deploy pending |
| `POST /webhooks/stripe` | 404 | Deploy pending |
| `POST /events/payment/test` | 200 | Old build; `intake_url` uses `127.0.0.1:8080` |

**Action:** Deploy latest `main` → re-run checklist in `KYC_PRODUCTION_VERIFICATION.md`.

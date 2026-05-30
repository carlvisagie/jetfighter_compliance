> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KeepYourContracts — Production Verification

**Date:** 2026-05-19  
**Verified against:** Local pytest + HTTP probes to `jetfighter-compliance.onrender.com`  
**Note:** Live Render may lag repo until next deploy (e.g. `/webhooks/stripe` returned **404** on probe — route exists in repo).

---

## Route health matrix

| Route | Role | Local tests | Render probe | Status |
|-------|------|-------------|--------------|--------|
| `GET /healthz` | Liveness | ✓ | 200 JSON | **Healthy** |
| `GET /health/ready` | Readiness | ✓ | Not probed | **Healthy** (after deploy) |
| `GET /` | Redirect → shop | ✓ | Not probed | **Healthy** |
| `GET /ui/shop.html` | Landing | ✓ | 200 | **Healthy** |
| `GET /ui/inquiry.html` | Inquiry form | ✓ | 200 | **Healthy** |
| `POST /api/inquiry/submit` | Inquiry → kickoff | ✓ | Not probed | **Healthy** |
| `POST /webhooks/stripe` | Stripe → kickoff | ✓ | **404** | **Deploy pending** |
| `POST /events/payment/test` | Ops kickoff | ✓ (dev) | 200* | **Guarded in prod** |
| `GET /ui/intake`, `POST /api/intake/submit` | Intake | ✓ | Not probed | **Healthy** |
| `GET /api/intake/resolve` | Token → project | ✓ | Not probed | **Healthy** |
| `GET /upload`, upload JS | Upload UI | ✓ | 200 | **Healthy** |
| `POST /api/evidence/register` | Evidence | ✓ | Not probed | **Healthy** |
| `GET /api/project/{id}/status` | Status API | ✓ | Not probed | **Healthy** |
| `GET /ui/status.html`, `/ui/control.html` | Ops dashboards | — | 200 | **Healthy** |
| `GET /api/projects` | Project list | ✓ | 200 | **Healthy** (ops) |
| `GET /api/ping-host.json` | Host probe | — | 200 | **Undocumented ops** |
| `GET /api/project/{id}/export` | ZIP export | — | — | **Dead** (UI references, no handler) |
| `keepyourcontracts.com/*` | Custom domain | — | Wrong origin | **Degraded** (DNS) |

\*Production `POST /events/payment/test` without `X-Ops-Key` should return **403** after deploy.

---

## Verified healthy routes (customer path)

1. `/ui/shop.html` — landing with Stripe Payment Links  
2. `/ui/inquiry.html` → `POST /api/inquiry/submit`  
3. `kickoff()` → email + `intake_url` + `upload_url`  
4. `/ui/intake?token=` → `POST /api/intake/submit`  
5. `/upload?project_id=` → `POST /api/evidence/register`  

---

## Verified degraded routes

| Item | Condition |
|------|-----------|
| Custom domain | `keepyourcontracts.com` not routed to Render |
| Stripe webhook on live host | 404 until deploy ships `/webhooks/stripe` |
| SMTP | Emails no-op if `SMTP_ENABLED` false |
| `/api/project/{id}/export` | Missing implementation |

---

## Production checklist (Owner)

### Before deploy

- [ ] `INTAKE_TOKEN_SECRET` — strong random value on Render  
- [ ] `STRIPE_WEBHOOK_SECRET` — from Stripe Dashboard webhook  
- [ ] `ENVIRONMENT=production`  
- [ ] `OPS_API_KEY` — random secret for ops test routes  
- [ ] `PUBLIC_BASE_URL=https://jetfighter-compliance.onrender.com` (or custom domain when live)  
- [ ] Remove `SHOPIFY_*` from Render env  
- [ ] Stripe webhook URL: `https://<host>/webhooks/stripe`, event `checkout.session.completed`  

### After deploy

- [ ] `curl -s https://<host>/healthz` → `{"ok":true}`  
- [ ] `curl -s https://<host>/health/ready` → `"ok":true`, checks populated  
- [ ] `curl -sI https://<host>/ui/shop.html` → 200  
- [ ] Submit test inquiry on `/ui/inquiry.html` → receives intake URL  
- [ ] Stripe test payment → project created (Dashboard webhook delivery log)  
- [ ] Upload file on `/upload?project_id=…` → 200 from evidence API  
- [ ] `POST /events/payment/test` without key → **403**  
- [ ] Custom domain: `/healthz` returns **JSON** not HTML  

### Stripe Dashboard

- [ ] Payment Links active (3 products in `ui/shop.html`)  
- [ ] Webhook signing secret matches Render  
- [ ] Optional: `metadata.sku` on each Payment Link for explicit SKU mapping  

---

## Deployment checklist

1. Push `jetfighter_compliance` to default branch.  
2. Confirm Render auto-deploy completes (Docker build green).  
3. Watch logs for `[startup]` warnings — resolve any CRITICAL.  
4. Run production checklist curls above.  
5. Do **not** sync `render.yaml` blueprint without Owner approval.  

---

## Rollback guidance

| Symptom | Action |
|---------|--------|
| Deploy breaks health | Render → rollback to previous deploy |
| Test routes blocked | Set `OPS_API_KEY` on ops machine; pass `X-Ops-Key` header |
| Stripe double-projects | kickoff idempotency uses session id — verify webhook retries return `existing: true` |
| Upload 404 project | Client must use valid `P-…` id from kickoff/intake |

---

## Monitoring guidance

| Probe | Interval | Expect |
|-------|----------|--------|
| `GET /healthz` | 1–5 min | `ok: true` |
| `GET /health/ready` | 5 min | `ok: true`, `stripe_webhook_configured: true` in prod |
| Stripe Dashboard | Daily | Webhook delivery success rate |
| Render logs | On alert | No repeated `Inquiry kickoff failed` |

Alert on: healthz non-200, ready `data_writable: false`, Stripe webhook 4xx/5xx spike.

---

## Flow verification summary

| Path | Verified |
|------|----------|
| Inquiry → kickoff → intake → upload → evidence | pytest ✓ |
| Stripe webhook → kickoff → intake → upload → evidence | pytest ✓ (code); live pending deploy |
| Ops manual kickoff | pytest ✓ (dev); prod requires `X-Ops-Key` |

See `docs/KYC_DIRECT_FLOW_VERIFICATION.md` for step-by-step detail.

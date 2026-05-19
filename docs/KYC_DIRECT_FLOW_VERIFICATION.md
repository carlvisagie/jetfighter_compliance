# KeepYourContracts — Direct Flow Verification

**Date:** 2026-05-19  
**Verified on:** Local pytest + Render hostname HTTP probes  
**Shopify:** Removed (not in path)

---

## Target flow

```
Landing → Inquiry OR Stripe → kickoff() → intake token → intake → upload → evidence → workflow
```

---

## Path A — Inquiry (verified)

| Step | Endpoint / page | Verified |
|------|-----------------|----------|
| 1 Landing | `/ui/shop.html` | Render 200 |
| 2 Inquiry form | `/ui/inquiry.html` | Render 200 |
| 3 Submit | `POST /api/inquiry/submit` | pytest: returns `project_id`, `intake_url` |
| 4 kickoff | internal | Creates `P-INQ-{ts}-…`, email, ledger event |
| 5 Intake page | `/ui/intake?token=…` | Token from `make_intake_token` |
| 6 Intake submit | `POST /api/intake/submit` | Returns `upload_url` |
| 7 Upload | `/upload?project_id=…` | HTML + JS wired |
| 8 Evidence | `POST /api/evidence/register` | pytest: file stored |

**Test:** `tests/test_webhook.py::test_inquiry_submit_kickoff`, `tests/test_upload_flow.py`

---

## Path B — Stripe Payment Link (verified in code + pytest)

| Step | Endpoint / page | Verified |
|------|-----------------|----------|
| 1 Shop CTA | External `buy.stripe.com/…` | Links in `ui/shop.html` |
| 2 Payment | Stripe hosted checkout | External |
| 3 Webhook | `POST /webhooks/stripe` | pytest with signed payload |
| 4 kickoff | `checkout.session.completed` | Returns `intake_url`, `upload_url` |
| 5–8 | Same as inquiry path | Shared kickoff/intake/upload/evidence |

**Test:** `tests/test_stripe_webhook.py::test_stripe_webhook_kickoff`

**Production requirement:** `STRIPE_WEBHOOK_SECRET` set on Render; webhook URL registered in Stripe.

---

## Path C — Ops manual kickoff (verified)

| Step | Endpoint | Verified |
|------|----------|----------|
| Admin form | `ui/new_client.html` | `POST /events/payment/test` |
| Test UI | `ui/webhook_test.html` | `POST /api/test-webhook` → kickoff |

**Test:** `tests/test_webhook.py::test_kickoff_via_payment_test`

---

## kickoff() continuity

| Behavior | Verified |
|----------|----------|
| `new_project()` | meta.json + checklist + evidence dir |
| `init_workflow` / `set_phase(INTAKE)` | called |
| Intake token | `make_intake_token` |
| Public URLs | `get_public_base_url()` — uses `PUBLIC_BASE_URL` or `RENDER_EXTERNAL_URL` |
| Idempotency | Same `order_id` → returns existing project (Stripe retries) |
| Email body | intake + upload links |

---

## Intake continuity

| Item | Verified |
|------|----------|
| `GET /api/intake/resolve?token=` | Returns `project_id`, `email` |
| `ui/intake.js` loaded | Yes (script tag in `intake.html`) |
| Form posts to `/api/intake/submit` | Yes |
| Post-submit redirect offer | `upload_url` confirm → `/upload?project_id=…` |

---

## Upload continuity

| Item | Verified |
|------|----------|
| Query `?project_id=` | Pre-fills form |
| Query `?token=` | Resolves via `/api/intake/resolve` |
| Multi-file upload | One `POST /api/evidence/register` per file |
| Evidence on disk | `data/projects/{id}/evidence/{filename}` |

---

## Evidence / workflow continuity (unchanged)

| API | Role |
|-----|------|
| `POST /api/evidence/register` | Artifact + ledger |
| `POST /api/coc/event` | Chain of custody |
| `GET /api/project/{id}/status` | Status board |
| RFQ routes | Vendor flow (retained) |

---

## Domain continuity (not verified on custom domain)

| Check | Render hostname | keepyourcontracts.com |
|-------|-----------------|------------------------|
| Full flow in browser | **Yes** (API + UI) | **No** — wrong origin |

Until DNS fixed, verify flows on `https://jetfighter-compliance.onrender.com`.

---

## Remaining operational risks

1. **Custom domain** not pointed at Render — primary customer-facing gap.
2. **Stripe webhook** must be registered in Stripe Dashboard after deploy.
3. **`PUBLIC_BASE_URL`** — set explicitly once custom domain live (Render URL works via `RENDER_EXTERNAL_URL` until then).
4. **SMTP** — kickoff emails no-op if `SMTP_ENABLED` false.
5. **QR asset** `/ui/assets/qr/kyc_upload_qr.png` — file may be missing (cosmetic).
6. **`/api/project/{id}/export`** — referenced in control UI but not implemented (pre-existing).

---

## Verification commands

```bash
# Local
cd jetfighter_compliance
python -m pytest tests/test_webhook.py tests/test_stripe_webhook.py tests/test_upload_flow.py -q

# Render (after deploy)
curl -s https://jetfighter-compliance.onrender.com/healthz
curl -sI https://jetfighter-compliance.onrender.com/ui/shop.html
```

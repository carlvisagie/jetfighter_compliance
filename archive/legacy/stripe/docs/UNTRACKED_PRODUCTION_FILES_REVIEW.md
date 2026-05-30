> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# Untracked Production Files Review — Task 29

**Date:** 2026-05-20  
**Mode:** Inspect only — **no commit of reviewed source files**  
**Git status at review:** `?? services/paypal_hook.py`, `?? services/storage.py`  
**Related plan:** [`RENDER_PRODUCTION_CUTOVER_PLAN.md`](./RENDER_PRODUCTION_CUTOVER_PLAN.md) Appendix B (deferred PayPal + S3 work)

---

## Executive summary

| File | Classification | Commit now? |
|------|----------------|-------------|
| `services/paypal_hook.py` | **DEFER_FOR_TASK** | **No** — wire + test in dedicated PayPal task |
| `services/storage.py` | **DEFER_FOR_TASK** | **No** — integrate + `boto3` + migration in storage task |

Both files are **orphan modules**: not imported by `server.py` or any committed code. **Live Render deploy is unaffected.** They are **future-task artifacts** from an interrupted implementation pass (payment continuity + persistent storage), not production runtime.

**Secret scan:** **PASS** — no embedded credentials; only `os.getenv(...)` references.

---

## 1. Repository state

```text
git status --short
?? services/paypal_hook.py
?? services/storage.py
```

| Check | Result |
|-------|--------|
| Tracked on `main`? | **No** |
| Imported anywhere? | **No** (`grep` — zero references) |
| In Docker image on Render? | **No** (untracked = not in last deploy from `main`) |
| Runtime impact today | **None** |

---

## 2. `services/paypal_hook.py`

### Purpose

PayPal webhook support for **Phase 5 — Payment continuity** (per cutover plan):

- Maps NCP payment link IDs to internal SKUs (matches `ui/shop.html`)
- `verify_paypal_webhook()` — PayPal REST signature verification via `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`
- `parse_paypal_event()` — extracts `order_id`, email, name, skus from `CHECKOUT.ORDER.*` / `PAYMENT.CAPTURE.COMPLETED` events

### Belongs to

| Category | Match |
|----------|--------|
| PayPal webhook automation | **Yes** — primary intent |
| Persistent storage | No |
| Abandoned local experiment | **Partial** — incomplete slice of Task 26+ work, not random scratch |
| Future task artifact | **Yes** |

### Secret scan

| Pattern | Found? |
|---------|--------|
| `whsec_` | No |
| `sk_live` / `sk_test` | No |
| `OPS_API_KEY=` (assigned value) | No |
| `INTAKE_TOKEN_SECRET=` (assigned value) | No |
| Hardcoded `password` | No |
| Embedded API secrets | No |

**Env names only (safe):** `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, `PAYPAL_MODE` — read via `os.getenv`, never logged with values in this file.

**Note:** `secret` variable on line 38 is local name holding `os.getenv("PAYPAL_CLIENT_SECRET")` — not a committed secret.

### Risk

| Risk | Level | Detail |
|------|-------|--------|
| Production exposure | **None** | Not deployed; not imported |
| Commit without wiring | **Medium** | Misleading “done” signal; dead code in repo |
| Commit as-is + partial route later | **Low** | Acceptable if next task adds `POST /webhooks/paypal` + tests |
| Verify returns `False` if `PAYPAL_WEBHOOK_ID` unset | **Low** | Safe default; must not ship route without verification |

### Gaps before production use

- No `server.py` route (e.g. `/webhooks/paypal`)
- No call to `kickoff()` from webhook handler
- No tests (`tests/test_paypal_webhook.py`)
- No Render env documentation for PayPal vars
- `verify-production-live.ps1` still Stripe-centric (separate doc task)

### Recommended action

**DEFER_FOR_TASK** — keep file locally; **do not commit** until a scoped task:

1. Add `POST /webhooks/paypal` → verify → `parse_paypal_event` → `kickoff()`
2. Owner: PayPal Developer webhook URL on **public deployed host**
3. Tests + live URL verification per doctrine

**Alternative (not recommended now):** `DELETE_TEMP` only if Owner wants a clean tree and will re-implement from plan — loses ~140 lines of correct SKU mapping.

---

## 3. `services/storage.py`

### Purpose

**Phase 3 — Persistent storage** (per cutover plan / brutal audit P0-1):

- `StorageBackend` ABC — `local` vs `s3` via `STORAGE_BACKEND`
- `S3StorageBackend` — S3-compatible (Cloudflare R2, Backblaze B2, AWS) using `boto3`
- Object metadata on write: `object_id`, `sha256`, `size`, `stored_utc`, `uri`
- Helpers: `project_exists`, `list_project_ids`, `ensure_local_cache_dirs`

### Belongs to

| Category | Match |
|----------|--------|
| Persistent storage implementation | **Yes** — primary intent |
| PayPal webhook automation | No |
| Abandoned local experiment | **Partial** — adapter only; no integration |
| Future task artifact | **Yes** |

### Secret scan

| Pattern | Found? |
|---------|--------|
| `whsec_` / `sk_live` / `sk_test` | No |
| `OPS_API_KEY=` / `INTAKE_TOKEN_SECRET=` | No |
| Hardcoded credentials | No |

**Env names only (safe):** `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_ENDPOINT_URL`, `S3_REGION`, `STORAGE_BACKEND`.

### Risk

| Risk | Level | Detail |
|------|-------|--------|
| Production exposure | **None** | Not imported; Render still uses `data/` in `server.py` |
| Commit without `boto3` | **Medium** | `requirements.txt` has no `boto3` — import fails if wired prematurely |
| Partial migration | **High** if half-wired | Projects on disk, evidence on S3 — must be one coordinated task |
| `append_text` on S3 | **Low** | Read-modify-write for ledger — OK for small scale; document limits |

### Gaps before production use

- Not used by `server.py`, `ledger.py`, `projects.py`, `evidence_register`
- `boto3` not in `requirements.txt`
- No production startup rule (`STORAGE_BACKEND=s3` required when `ENVIRONMENT=production`)
- No Render env docs for bucket/credentials
- No migration of existing `data/projects` to bucket

### Recommended action

**DEFER_FOR_TASK** — keep file locally; **do not commit** until storage cutover task:

1. Add `boto3` to `requirements.txt`
2. Refactor evidence + project JSON + ledger paths through `get_storage()`
3. Render env: `STORAGE_BACKEND=s3`, bucket, keys (dashboard only — never in git)
4. Live verify upload survives manual redeploy

**Alternative:** `DELETE_TEMP` if abandoning this approach — not recommended; aligns with audit P0.

---

## 4. Classification matrix

| File | KEEP_AND_COMMIT | DELETE_TEMP | DEFER_FOR_TASK | DANGEROUS_DO_NOT_COMMIT |
|------|-----------------|-------------|----------------|-------------------------|
| `paypal_hook.py` | — | Optional | **Selected** | — |
| `storage.py` | — | Optional | **Selected** | — |

**Neither file is DANGEROUS_DO_NOT_COMMIT** — no secrets, no malware patterns, no tunnel config.

**Neither is KEEP_AND_COMMIT now** — incomplete integration would violate “build exactly the way it will be used.”

---

## 5. Decision for cutover sequencing

Per [`RENDER_PRODUCTION_CUTOVER_PLAN.md`](./RENDER_PRODUCTION_CUTOVER_PLAN.md):

| Cutover step | Use these files? |
|--------------|------------------|
| DNS + Render custom domain | **No** |
| Env hardening (`ENVIRONMENT`, secrets) | **No** |
| Doc-only / verifier script | **No** |
| PayPal automation task | **Use `paypal_hook.py` as starting point** |
| S3/R2 storage task | **Use `storage.py` as starting point** |

**Rule:** Do not commit orphan modules before cutover DNS — avoids confusion about what is live on Render.

---

## 6. Owner / agent options after this review

| Option | Action |
|--------|--------|
| **A (recommended)** | Leave files **untracked** until Task 30+; implement with wiring + tests + single commit |
| **B** | Add to `.gitignore` local WIP — **not recommended** (hides work) |
| **C** | `DELETE_TEMP` both — only if re-building from scratch |
| **D** | Commit in `wip/` branch — only if Owner wants backup off-machine |

---

## 7. Task 29 closure

| Criterion | Status |
|-----------|--------|
| Untracked files reviewed | **Done** |
| Secret scan | **PASS** (no real secrets) |
| No runtime changes | **Done** (review doc only committed) |
| Review doc committed | **Pending push** — this file |
| Mystery resolved before cutover | **Done** |

**Files NOT committed in Task 29:** `services/paypal_hook.py`, `services/storage.py`

---

## Appendix — Line counts

| File | Lines | Dependencies |
|------|-------|----------------|
| `paypal_hook.py` | 141 | `httpx` (already in requirements) |
| `storage.py` | 216 | `boto3` (**not** in requirements yet) |

# AGENTS.md — KeepYourContracts (KYC compliance organism)

**You are not editing a loose web app.** This repository is a **central-memory compliance organism**: inquiry → intake → evidence → ledger → operator cockpit, with telemetry and self-healing indexed in one brain.

**Wrong repo?** Coaching / SAGE lives in `purposeful-platform`. Stay here for KYC / JetFighter_Compliance.

---

## FIRST RULE — PRODUCTION IS THE ONLY TRUTH

There is **one** environment: **production**. Everything else is noise.

- **Production** = `https://compliance.keepyourcontracts.com`, Render service **`jetfighter_compliance`** (the Blueprint label is `kyc-backend`, the live Dashboard service id is `jetfighter_compliance` — they refer to the same deploy; open the latter when working in the Render UI), Render disk **`kyc-data`** mounted at `/var/data`. The disk is the only place customer truth ever lives. If the disk-persistence probe ever reports `ephemeral_lost`, treat as SEV-1 and re-attach the disk before accepting new uploads — see `docs/KYC_UPLOAD_IMMUTABILITY_PROOF.md` § "2026-06-04 — Disk attach incident".
- The local `data/` directory on a developer machine is **not** a source of truth. It contains pytest junk and old experiments. Do not `ls` it to answer "how many intakes / projects / uploads do we have." Do not cite anything you found there.
- Pytest writes only to per-session temp dirs (`tests/conftest.py` enforces this). Test counts are invisible to humans and to you.

**Before quoting any count to the operator, you MUST:**

1. Hit `https://compliance.keepyourcontracts.com/api/operator/<endpoint>` with `X-Ops-Key: $OPS_API_KEY`.
2. Read the `_env` envelope on the response.
3. Confirm `_env.environment == "production"` AND `_env.trust == "trusted"`.
4. Cite the count **with provenance**: environment, data_root, server_time_utc, git_commit.

**Forbidden:**

- Saying "we have N intakes" without the `_env` envelope alongside it.
- Reading the local `data/` directory and treating what you find as production reality.
- Inventing or guessing counts because the operator endpoint was slow.
- Running scripts that write to `data/` and then quoting the result.

Full doctrine and enforcement matrix: [`docs/PRODUCTION_IS_THE_ONLY_TRUTH.md`](docs/PRODUCTION_IS_THE_ONLY_TRUTH.md).

Violating this rule cost the platform a forensic audit on 2026-06-04. Do not repeat that failure.

---

## Live production proofs (must be re-verified before quoting status)

| Proof | How to run | Last verified |
|---|---|---|
| Operator session login + build commit | `python scripts/probe_boot_status.py` | 2026-06-04 commit `bb3aeb6` |
| Scheduler started with 12 cron jobs | (same — look for `scheduler: started`) | 2026-06-04 commit `bb3aeb6` |
| Organism state + VIO overview shape | `python scripts/probe_vio_overview.py` | 2026-06-04 |
| Disk persistence across restart | `python scripts/prove_disk_persistence.py` | 2026-06-04 `verified_persistent` |
| Full pytest suite (865 tests) | `python -m pytest -q --timeout=60` | 2026-06-04 865 passed |

All four probes require `.ops_env` with `OPS_PASSWORD` (+ `RENDER_API_KEY` for the restart proof).

---

## Mandatory read before any edit

1. **This file** (`AGENTS.md`)
2. **[`docs/PRODUCTION_IS_THE_ONLY_TRUTH.md`](docs/PRODUCTION_IS_THE_ONLY_TRUTH.md)** — environment contract (the rule above, fully expanded)
3. **[`docs/KYC_CONSTITUTION.md`](docs/KYC_CONSTITUTION.md)** — binding law (IRON LAW, sacred areas, change gate)
4. **[`docs/CENTRAL_MEMORY.md`](docs/CENTRAL_MEMORY.md)** — memory model and vessels
5. **[`docs/KYC_ORGANISM_INTEGRATION_AUDIT.md`](docs/KYC_ORGANISM_INTEGRATION_AUDIT.md)** — engine ↔ memory wiring
6. **[`docs/LAUNCH_PATH.md`](docs/LAUNCH_PATH.md)** — active production onboarding path
7. **`server.py`** — real routes (HTML may lie; code is truth)
8. **`render.yaml`** — production env contract

Optional but useful: [`docs/PRODUCTION_ENGINEERING_DOCTRINE.md`](docs/PRODUCTION_ENGINEERING_DOCTRINE.md), [`docs/PUBLIC_UI_EXPOSURE_AUDIT.md`](docs/PUBLIC_UI_EXPOSURE_AUDIT.md), [`docs/FOUNDING_BETA_RENAME_PLAN.md`](docs/FOUNDING_BETA_RENAME_PLAN.md) (known-amber tracking).

---

## KYC IRON LAW

**Central memory is the canonical brain.**

Every **active** engine must either:

- **read/write central memory directly** (`services/memory/*`, `data/memory/*`), or
- **emit telemetry / adaptive signals** into central memory (`data/memory/telemetry.jsonl`, `adaptive_signals.jsonl`).

**No active business truth may live outside organism memory** without an explicit, documented bridge in `services/memory/organism_integration.py` and an entry in the organism integration audit.

Support layers (email transport, health probes, static export) may be **outside** only if they do not hold durable customer truth and they emit telemetry when they act.

---

## Protected sacred areas (do not casually refactor or delete)

| Area | Why |
|------|-----|
| `services/memory/*` | Canonical brain implementation |
| `services/acquisition/*` | Forensics + discovery; bridged to memory |
| `server.py` auth / public–private route gates | Customer safety boundary |
| `services/ops_auth.py` | Operator session + API protection |
| `ui/control.html` | Operator cockpit |
| `ui/memory.html` | Organism observability |
| `ui/login.html` | Ops gate |
| Public vs customer UI separation | `test_public_ui_exposure.py` |
| `data/memory/*` | Durable organism state |
| `docs/KYC_CONSTITUTION.md` | Binding rules |
| `tests/test_public_ui_exposure.py` | Public exposure guardrails |
| `tests/test_ops_route_auth.py` | Ops auth guardrails |
| `tests/test_operator_guidance.py` | Cockpit guidance contract |
| `tests/test_organism_observability.py` | Telemetry contract |
| `tests/test_central_memory.py` | Memory contract |
| `tests/test_kyc_guardrails.py` | Repo-level agent protection |

---

## Future agent rules (non-negotiable)

1. Read `AGENTS.md` and `docs/KYC_CONSTITUTION.md` before edits.
2. **Do not remove** central memory linkage from onboarding engines (inquiry, intake, kickoff, ledger, evidence, forensics).
3. **Do not create new memory islands** — no parallel JSON/SQLite truth stores without audit + bridge.
4. **Do not expose** internal ops pages publicly (control, memory, command, webhook_test, etc.).
5. **Do not add** public nav/links to control/memory/command pages from customer HTML.
6. **Do not weaken** server-side ops auth (`OPS_PASSWORD`, session cookie, `X-Ops-Key`, middleware).
7. **Do not add** fake AI/autonomy claims in UI or docs.
8. **Do not add** mocked discovery domains as production leads (`example.com`, etc.).
9. **Do not bypass** or delete guardrail tests to “make CI green.”
10. **Do not alter** customer-facing pricing/claims without explicit owner approval.
11. **Do not reintroduce the banned legacy card-payment rail** — PayPal is the payment path. See [`docs/STRIPE_FINAL_STATUS.md`](docs/STRIPE_FINAL_STATUS.md) and [`archive/legacy/stripe/`](archive/legacy/stripe/).
12. **Do not add** new docs that contradict canonical docs — update these files instead.

---

## Change gate (before every commit)

The agent **must** verify:

| Check | Command / test |
|-------|----------------|
| Public UI exposure | `pytest tests/test_public_ui_exposure.py -q` |
| Ops auth | `pytest tests/test_ops_route_auth.py -q` |
| Central memory | `pytest tests/test_central_memory.py -q` |
| Organism observability | `pytest tests/test_organism_observability.py -q` |
| Operator guidance | `pytest tests/test_operator_guidance.py -q` |
| KYC guardrails | `pytest tests/test_kyc_guardrails.py -q` |
| Full suite | `python -m pytest tests/ -q` |
| No secrets in diff | No `.env`, tokens, passwords in staged files |
| No public ops links | Guardrail tests above |
| No mock production data | `test_kyc_guardrails.py` + discovery mock blocklist |

CI runs the same checks in [`.github/workflows/kyc_guardrails.yml`](.github/workflows/kyc_guardrails.yml).

---

## Customer-facing vs operator surfaces

| Customer (public) | Operator (protected) |
|-----------------|----------------------|
| `/ui/shop.html` | `/ui/control.html` |
| `/ui/inquiry.html` | `/ui/memory.html` |
| `/ui/intake.html` | `/ui/command.html`, `/ui/knowledge.html` |
| `/ui/upload.html` | `/api/memory/*`, `/api/operator/*` |

Primary onboarding: `POST /api/inquiry/submit` → `kickoff()` → intake/upload URLs (+ email when SMTP configured).

**Inactive for launch:** Shopify, Cloudflare tunnel cutover. **Legacy card-payment rail is banned** — see [`docs/STRIPE_FINAL_STATUS.md`](docs/STRIPE_FINAL_STATUS.md).

---

## Production

| Item | Value |
|------|--------|
| Service | Render `jetfighter_compliance` (Blueprint name `kyc-backend`; Docker) |
| Public URL | `https://compliance.keepyourcontracts.com` |
| Health | `GET /healthz`, `GET /health/ready` |
| Verify scripts | `scripts/verify-render-production.ps1`, `scripts/verify-production-live.ps1` |

Task **DONE** only with: commit hash, live URL verified, test command + pass count (per production doctrine).

---

## Do not

- Merge KYC organism memory into Sage `client_profile` without an owner bridge spec
- Treat `organism/` sqlite as production truth
- Document banned legacy payment rails or Shopify as the launch path
- Commit SMTP passwords or API keys
- Add `ui/*.bak` or `ui/*.backup*.html` files

When in doubt: read `server.py`, change less, run the change gate, verify on the deployed URL.

# KYC Constitution — KeepYourContracts compliance organism

**Status:** Binding for all human and AI contributors.  
**Supersedes:** Ad-hoc README fragments and conflicting one-off docs.  
**Entry point for agents:** [`../AGENTS.md`](../AGENTS.md)

---

## Article I — Nature of the system

KeepYourContracts (JetFighter_Compliance) is a **central-memory compliance organism**, not a collection of unrelated scripts.

- **Brain:** `services/memory/*` + `data/memory/*`
- **Organs:** inquiry, intake, kickoff, workflow, evidence, ledger, acquisition forensics, RFQ, jobs
- **Nervous system:** timelines, telemetry, adaptive signals
- **Immune system:** self-healing (suggestions only — no auto-delete of customer data)
- **Skin:** public customer UI (`shop`, `inquiry`, `intake`, `upload`)
- **Command deck:** operator UI (`control`, `memory`, `login`) behind server-side auth

---

## Article II — KYC IRON LAW

> **Central memory is the canonical brain.**

Every **active** engine MUST either:

1. **Read/write central memory** through `services/memory/central_memory.py`, entity graph, timeline, signals, or organism adapters; OR  
2. **Emit telemetry** (`emit_telemetry`) and/or **adaptive signals** into `data/memory/` when performing customer-impacting work.

**Forbidden:** Durable business truth (who inquired, who paid, what was uploaded, workflow phase, forensic outcomes) stored only in ad-hoc files with no bridge to central memory.

**Allowed outside layers (non-truth transport):**

- SMTP send attempts (telemetry only)
- Health/readiness probes
- Static report generation (reads project dirs; should trend toward memory-aware exports)
- Legacy `organism/` sqlite — **not** production truth

---

## Article III — Sacred areas

Changes to these paths require explicit owner intent and full change-gate pytest:

| Path | Protection |
|------|------------|
| `services/memory/*` | Brain — entities, timelines, learning, self-heal, observability |
| `services/acquisition/*` | Discovery + forensics — must stay bridged |
| `server.py` | Route table + kickoff/inquiry/intake + auth middleware |
| `services/ops_auth.py` | Public/protected UI and API classification |
| `ui/control.html` | Operator cockpit |
| `ui/memory.html` | Organism observability UI |
| `ui/login.html` | Authentication gate |
| Customer UI (`shop`, `inquiry`, `intake`, `upload`) | No internal links; no ops terminology |
| `data/memory/*` | Live organism state |
| `docs/KYC_CONSTITUTION.md` | This document |
| Guardrail tests (see AGENTS.md) | CI enforcement |

---

## Article IV — Public / private boundary

1. **Customer pages** are listed in `tests/test_public_ui_exposure.py` (`PUBLIC_PAGES`).
2. **Internal pages** must include `noindex,nofollow` and require ops session (or valid `X-Ops-Key` for APIs).
3. **Never** link from public HTML to `/ui/control.html`, `/ui/memory.html`, `/ui/command.html`, or `/api/memory/`.
4. Backup or scratch HTML under `ui/` (`*.bak`, `*.backup*.html`) is **forbidden** in the repo.

Enforcement: `tests/test_public_ui_exposure.py`, `tests/test_ops_route_auth.py`, `tests/test_kyc_guardrails.py`, GitHub Actions `kyc_guardrails.yml`.

---

## Article V — Acquisition and discovery

1. Lead discovery is **controlled onboarding validation**, not autonomous outbound spam.
2. **Mock/example domains** must be rejected in import paths (`is_mock_domain` in `services/acquisition/intelligence_paths.py`).
3. Acquisition weight files (`data/acquisition/intelligence/weights.json`) are a **bridged island** — outcomes must flow through `safe_write_after_acquisition_outcome`.
4. Agents must not wire “fake discovery” or seeded production leads without owner approval.

---

## Article VI — Authentication and secrets

1. Production internal routes require `OPS_PASSWORD` (session) and/or `OPS_API_KEY` (`X-Ops-Key`).
2. **Never** log or return SMTP passwords, API keys, or `INTAKE_TOKEN_SECRET`.
3. **Never** weaken middleware to make tests pass without updating guardrail tests.
4. Intake tokens remain signed with `INTAKE_TOKEN_SECRET` — do not revert to dev default in production.

---

## Article VII — Legacy systems (frozen unless instructed)

| System | Status |
|--------|--------|
| `POST /webhooks/stripe` | Test-only; not launch path |
| Shopify integration docs | Historical |
| Cloudflare tunnel rebuild docs | Historical |
| `organism/` sqlite subsystem | Outside production truth |

Agents must **not** reactivate these as the primary onboarding path without owner written instruction.

---

## Article VIII — Documentation hierarchy

Canonical docs (update in place; do not contradict):

1. `AGENTS.md`
2. `docs/KYC_CONSTITUTION.md` (this file)
3. `docs/CENTRAL_MEMORY.md`
4. `docs/KYC_ORGANISM_INTEGRATION_AUDIT.md`
5. `docs/LAUNCH_PATH.md`

Other docs are supplementary. If conflict arises, canonical docs win.

---

## Article IX — Change gate (pre-commit)

Before any commit, verify:

```
python -m pytest tests/test_public_ui_exposure.py tests/test_ops_route_auth.py \
  tests/test_central_memory.py tests/test_organism_observability.py \
  tests/test_operator_guidance.py tests/test_kyc_guardrails.py -q
python -m pytest tests/ -q
```

Additionally confirm:

- [ ] No secrets in staged files
- [ ] No new public links to ops UI
- [ ] No new memory islands without audit update
- [ ] No fake AI/autonomy marketing copy on customer pages
- [ ] Organism integration audit updated if engine wiring changed

---

## Article X — Amendments

Only the repository owner may:

- Relax IRON LAW for a specific engine (document exception in integration audit)
- Add customer-facing pricing or compliance claims
- Re-enable Stripe/Shopify as production path

Agents may propose amendments via PR + audit doc update; they may not silently amend this constitution.

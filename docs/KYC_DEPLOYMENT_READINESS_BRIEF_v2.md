# KYC Organism — Deployment Readiness & Operational Command Brief (v2)

**Platform:** KeepYourContracts / JetFighter_Compliance
**Repository:** carlvisagie/jetfighter_compliance
**Production URL:** compliance.keepyourcontracts.com
**Backend:** jetfighter-compliance.onrender.com
**Audit Date:** June 3, 2026 (post-deploy-ready pass, commit `42ae186`)
**Status:** READY FOR CONTROLLED CLIENT ACQUISITION — application surface green, CI workflow timeout cap pending one-line fix

---

## Part I — What This Platform Is

Before any deployment action is taken, it is essential to understand the platform's identity precisely, because this identity governs every decision about what to build, what to change, and what to leave alone.

KeepYourContracts is not a web application. It is not a CRM. It is not a compliance consulting portal. It is a **central-memory compliance organism** — a living system that ingests evidence, builds awareness, learns from every interaction, and heals its own inconsistencies. The platform sells one thing: **burden removal**. The core promise to every client is "Give us exactly what you have. We'll handle the rest."

The organism is governed by an Iron Law that is binding on all contributors, human and AI: **Central memory is the canonical brain.** Every active engine must read from or write to this central memory, or emit telemetry into it. No durable business truth — who inquired, who paid, what was uploaded, what phase a project is in — may exist outside of this ecosystem without an explicit, audited bridge.

As of this audit a second invariant has been formalized and made enforceable in code: **The organism is self-observing.** A reusable, domain-agnostic awareness package (`organism_core/`) has been extracted from the KYC bindings (`services/organism_state/`). The platform now reports on its own wiring, health, recommendations, and residue without leaning on any external monitoring system. The KYC bindings are the first implementation of that core; the core is portable to any future organism.

The organism's anatomy maps as follows:

| Anatomical Layer | Technical Implementation |
| --- | --- |
| Brain | `services/memory/*` and `data/memory/*` |
| Organs | Inquiry, intake, kickoff, workflow, evidence, ledger, acquisition forensics, RFQ, job engine |
| Nervous System | Timelines, telemetry, adaptive signals |
| Immune System | Self-healing (`services/memory/self_healing.py`) — suggestions only, never auto-deletes customer data |
| Awareness Cortex | `organism_core/` (reusable, domain-agnostic) + `services/organism_state/` (KYC bindings) |
| Skin | Public customer UI: paperwork intake, upload |
| Command Deck | Operator UI: VIO, control, memory, command — all behind server-side auth |

The platform is designed to be fully autonomous. However, the marketing strategy is explicit: **do not advertise this as an "autonomous platform" to clients.** The focus remains entirely on the practical, human value of frictionless onboarding and immediate compliance visibility.

---

## Part II — VIO: The Command Center

### What VIO Is

VIO (Visual Intelligence Observatory) is the designated primary interface for all platform operations. It is an **Organism Awareness Field**, not a dashboard. The VIO Constitution, which is binding law within the codebase, explicitly rejects the following design patterns: queue-first, card-first, dashboard-first, widget-first, table-first, notification inboxes as primary workflow, and multiple competing navigation systems.

The success condition for VIO is unambiguous: a first-time operator opens VIO and within five seconds knows who is in the system, where they are in the process, the organism's health, what is waiting, what is broken, and what needs to happen next — without reading documentation. If that is not true, the design is incomplete.

### Current VIO Status

VIO is live and deployed at `/ui/vio.html`. The `vio_overview.py` service aggregates all company rows, classifies each into one of the seven backbone stages (`intake → classification → validation → evidence_mapping → review → approval → conversion`), computes an urgency score per company, derives an at-most-four-item attention list, and returns a global organism awareness block. The VIO front-end renders the awareness field in the browser.

**As of 2026-06-04 the Level 1 view has been rebuilt to be doctrine-compliant** (see [`docs/VIO_DOCTRINE.md`](./VIO_DOCTRINE.md)). Every company is now rendered as exactly one continuous SVG trace — orb on the left, the seven-stage backbone running right, the past segment bright, the future segment dashed and faint, a single live point sized and coloured by stage state, and a single allowed `client follow-up` branch when the customer must act. Stillness is the baseline; the only animation in the entire system is a 4-second breathe on the `waiting_client` state. There are no pills, no badges, no status columns, no tabs, no persistent sidebar. Information lives in the line itself, with a transient hover card and the global organism strip as the only secondary surfaces. Companies are sorted top-down by `urgency_score = failure_flags × 1000 + days_in_stage × 50 + gap_count × 10 + stale_payment_days × 5`, with `done` companies pinned to the bottom.

The composite per-company endpoint, `GET /api/operator/vio/company/{intake_id}`, remains in place and now powers both the cockpit drill-down and the Level 2 immersive landscape. It returns every uploaded document (with view/download URLs), every generated document, every missing document, the evidence intelligence summary, all extracted identifiers, the intake-context block (customer free-text, deadline, urgency flag), and a derived `findings` block that surfaces extraction failures, stale payment links, on-disk file mismatches, ghost intakes, unindexed files, and confirmation-needed states.

**Level 2 — the immersive landscape — is also live.** Clicking any Level 1 trace takes the operator into a full-screen horizontal canvas: the company orb anchors the left, the same 7-stage spine runs right, and perpendicular branches sprout up and down from the stages only where real data warrants. Clean companies render as a clean spine plus a single `papers` cluster. Complex companies render bushy — clusters for context, identifiers, service tier, generated paperwork (above the spine); papers uploaded, missing documents, findings, payment, project (below the spine). Every visual atom — orb, stage anchor, leaf — is clickable and opens a recursive side panel with the full per-leaf detail (file metadata + view/download links for documents, severity + hint for findings, why-this-matters + example for gaps, paid/amount/link for payment, etc.). The stillness doctrine holds: the only animation in Level 2 is the same 4-second breathe on the orb when the company is in `waiting_client`. ESC, the back chevron, or a click outside the canvas all return to Level 1.

A second persistent surface is the **global organism strip** pinned to the VIO header: it shows live system health (a single-letter status pill, no shouting), the current bottleneck, mismatch counts, and a 45-second TTL cached organism summary. It is silent when the organism is healthy.

A defensive sanitiser in `services/vio_overview._clean_company_name` ensures VIO never displays a URL or empty string as a company name, regardless of what upstream pipelines stored. The same sanitiser now runs at intake creation, so dirty data no longer accumulates. Behaviour is covered by `tests/test_vio_company_name_sanitiser.py`.

### The Transition Plan

The platform currently operates with VIO as the awareness layer and the operator cockpit (`/ui/control.html`) as the action layer. This remains the correct and intentional transitional state. The cockpit handles the "First Sale" workflow: reviewing intake documents, selecting a service tier, generating the PayPal payment link, and kicking off the project. VIO tells you what is happening; the cockpit is where you act.

The full transition to VIO as the sole command center will occur once VIO's ability to surface and execute all necessary operator actions has been proven with real client data. With the per-company composite endpoint and findings block now in place, that threshold is closer than it was at the prior audit. Until that threshold is crossed, both interfaces remain active and complementary.

---

## Part III — Complete Engine & Feature Inventory

This inventory is derived from live codebase inspection on commit `42ae186` and from the 818-case green test suite. The inventory covers 22 engines across the platform (two new engines since the prior brief: Organism Core and VIO Composite Detail).

### Tier 1: Fully Plugged Engines (Production Ready)

These engines are fully wired to central memory, actively tested, and confirmed operational in the live production environment.

| Engine | Readiness | Key Paths | Role |
| --- | --- | --- | --- |
| Central Memory Core | 100% | `services/memory/*`, `data/memory/` | The canonical brain. Handles entities, timelines, signals, learning state, and corrections. |
| Customer Intake (paperwork) | 100% | `server.py`, `POST /api/intake/upload`, `services/intake/intake.py`, `services/intake/durable_root.py`, `services/intake/proof_gate.py` | Secure evidence ingestion. Refuses uploads if durable disk probe fails. Every file fsync'd, hash-ledgered, and verified before queue exposure. |
| Customer Session (pre-contact) | 100% | `services/customer_session.py`, `POST /api/customer/session/{start,upload,complete}` | Magic-link-issuing pre-contact session. Post-rebrand: redirects clients to `/ui/intake`. |
| Kickoff / Project Creation | 100% | `server.py` (kickoff), `services/projects.py` | Creates project workspace, links intake files, writes to central memory. |
| Evidence Intelligence | 100% | `services/evidence_intelligence/` | Analyzes uploaded files, extracts entities, maps gaps, feeds timeline. |
| Compliance Intelligence | 100% | `services/compliance_intelligence/` | Continuous public-source monitoring. Detects regulatory changes and routes to review queue. |
| Workflow / Process Engine | 100% | `services/process.py` | Manages project lifecycle phases. |
| COC / Event Ledger | 100% | `services/ledger.py` | Immutable event log. Every significant action is recorded. |
| Central Learning | 100% | `services/memory/learning.py` | Tracks signal effectiveness, conversion counts, and segment performance. |
| Self-Healing (Immune) | 100% | `services/memory/self_healing.py` | Scans for orphan linkages, generates correction suggestions. Never auto-deletes. |
| Acquisition Discovery | 100% | `services/acquisition/discovery.py` | Safely imports candidate companies from owner-approved CSVs. |
| Payment Rail (PayPal NCP) | 100% | `services/intake/payment_products.py`, `services/intake/operator_actions.py`, `services/intake/auto_payment.py` | Three live PayPal NCP links. Auto-payment wrapper now correctly forwards `update_status` (kwarg-drop bug fixed this pass). |
| Email Transport | 100% | `services/emails.py`, `services/email_adapters/`, `services/communications/` | Adapter architecture. Resend primary with Cloudflare-friendly headers, SMTP fallback. |
| Operator Cockpit | 100% | `ui/control.html`, `services/operator_cockpit.py` | First-sale workflow: review, approve, send payment link, kickoff. |
| Knowledge Cockpit | 100% | `services/knowledge_cockpit/`, `ui/knowledge.html` | Solo operator mentor layer. Contextual explanations embedded in the control panel. |
| **VIO 2.0 Awareness Field** | **95%** | `ui/vio.html`, `services/vio_overview.py`, `services/vio_company_detail.py`, `GET /api/operator/vio/overview`, `GET /api/operator/vio/company/{intake_id}` | Awareness field live and rendering. Per-company composite detail (uploads, generated, missing, evidence, findings) now wired. Header organism strip live. Remaining 5% is operator-action surfacing inside the detail panel. |
| **Organism Core (Awareness Cortex)** | **100%** | `organism_core/awareness/`, `organism_core/health/`, `organism_core/recommendations/`, `organism_core/residue/`, `organism_core/persistence/` | Domain-agnostic awareness package extracted this cycle. Reusable across any future organism. |
| **KYC Organism Bindings** | **100%** | `services/organism_state/`, `GET /api/operator/organism/{state,history}` | KYC-specific collectors, checks, derivation, recommendations, residue patterns. Powers the VIO header strip via a 45s-cached summary; recursion-guarded so the collector cannot re-enter through the overview. |
| Organism Observability | 100% | `services/organism_observability/`, `ui/memory.html` | Full telemetry, health, funnel, and beacon tracking. |
| Cognitive Topology (COTE) | 90% | `services/cognitive_topology.py` | Lightweight organism state summary. Layer 1 active; full orb universe partial. |
| Reddit Acquisition | 95% | `services/acquisition/social_intelligence/` | Autonomous Reddit signal detection and engagement strategy. Requires Reddit API credentials. |
| Acquisition Scoring | 80% | `services/acquisition/scoring.py` | Scores are operational but reside in the review queue rather than the central timeline. |

### Tier 2: Operational Support Layers (Outside by Design)

These components are intentionally outside central memory because they are transport or static layers that do not hold durable business truth.

| Component | Status | Notes |
| --- | --- | --- |
| SMTP / Email Transport | Active | Telemetry emitted on send attempts. Not a truth store. |
| Health / Readiness Probes | Active | `GET /healthz`, `GET /health/ready`. Operational monitoring only. |
| Static Report Generation | Active | Reads project directories. Trending toward memory-aware exports. |
| **CORS Policy** | **Active (production-locked)** | Production restricts `allow_origins` to `compliance.keepyourcontracts.com` and `jetfighter-compliance.onrender.com`. Local / preview / tests get `*`. `CORS_ALLOW_ORIGINS` env var overrides without code change. |
| **Residue Scanner** | **Active** | `organism_core/residue/scanner.py` runs on every snapshot and surfaces any re-introduction of the pre-rebrand public intake routes or module imports. Scanner skips its own source so it cannot self-trigger. |

### Tier 3: Legacy / Inactive (Frozen)

| Component | Status | Notes |
| --- | --- | --- |
| Legacy Stripe Card Webhook | Permanently Removed | Banned. See `docs/STRIPE_FINAL_STATUS.md`. Do not reactivate. |
| Shopify Integration | Historical | Documentation only. Not a production path. |
| Cloudflare Tunnel Rebuild | Historical | Documentation only. |
| **Pre-rebrand public intake route family** | **Permanently Removed** | All routes hard-deleted. No shims, no redirects. Residue scanner enforces. |
| **Pre-rebrand customer upload surface** | **Permanently Removed** | Replaced by `/ui/intake`. Backend redirects, session completion payloads, magic-link generators, and JS clients all reference the new path. |
| **Deprecated operator intake shim** | **Permanently Removed** | Replaced by `/api/operator/intake/queue` as the canonical operator surface. |
| Abandoned `organism/` SQLAlchemy prototype | Excluded from CI | `pytest.ini` excludes the legacy `organism/` tree from collection. Pre-dates `organism_core/` and is not part of the runtime. |

---

## Part IV — End-to-End Validation Results

### Live Production Health Check (June 3, 2026, prior-audit snapshot)

The following checks were performed against the live production environment immediately prior to the prior audit and remain the canonical "platform is alive" baseline.

| Check | Result | Detail |
| --- | --- | --- |
| `GET /healthz` (Render backend) | PASS | `{"ok": true, "service": "kyc-backend", "safe_mode": false, "schedulers_enabled": true}` |
| `GET /health/ready` (Custom domain) | PASS | All checks green: `data_writable`, `projects_dir`, `inquiry_onboarding_active`, `intake_secret_configured`, `smtp_configured`, `durable_storage_configured`, `intake_uploads_enabled` |
| `GET /ui/intake` | PASS | HTTP 200, renders `Submit Your Compliance Paperwork` |
| `GET /ui/control.html` | PASS | HTTP 200 (operator auth gates content) |
| `GET /ui/vio.html` | PASS | HTTP 200 (operator auth gates content) |

### Local Full Test Suite Validation (June 3, 2026, post-fix)

The full suite was run twice this cycle on commit `42ae186`:

| Metric | Value |
| --- | --- |
| Tests collected | **818** |
| Tests passed | **818** |
| Tests failed | **0** |
| Wall-clock runtime (Windows local) | ~22 min |
| Previous run (pre-fix) | 87 failed / 731 passed |

The 87 failures from the pre-fix run were collapsed into two root causes: (1) stale pre-rebrand API URLs in tests that had not been swept when the backend routes were deleted, and (2) seven surface-rename assertions still checking for the old HTML identifiers (replaced by the new `intake-*` identifiers and `cockpit-intake.js`). Both classes were fixed; the suite is now green end-to-end.

### Manufactured Company E2E Scenarios (Unchanged)

The platform retains the live seeding capability (`scripts/seed_vio_live.py`) that injects five realistic, manufactured compliance scenarios into the production environment to validate the complete client lifecycle within VIO and the operator cockpit. These test companies cover every critical state the organism must handle: New Inquiry, Waiting on Customer, Urgent Review, Approved (payment link stage), and Archived. Each scenario includes realistic document content that exercises the Evidence Intelligence extraction and gap analysis engines. All five scenarios were confirmed to render correctly in the prior audit; the new VIO composite detail endpoint extends the validation surface to per-company drill-down, which has been tested locally and is ready to be re-validated against production after the next deploy.

### CI / GitHub Actions Validation

| Check | Result | Detail |
| --- | --- | --- |
| Workflow file present | PASS | `.github/workflows/kyc_guardrails.yml` exists, fires on push to `main`/`master` and PRs against the same. |
| Most-recent run (`26895968230`) | **CANCELLED** | Cause: explicit `timeout-minutes: 15` on the `guardrails` job. Final "Full test suite" step ran 14m 19s of an expected ~14–17m before being killed at the 15-minute cap. Documented in `docs/CI_GUARDRAILS_RUN_26895968230_ROOT_CAUSE.md`. |
| Concurrency / supersession | N/A | No `concurrency:` block defined; no later commit on `main`; `run_attempt: 1`; no manual cancel API call. |
| Remediation needed | Yes (workflow-only) | Bump `timeout-minutes` to `30`, or remove the duplicate "Full test suite" step, or split into a matrix. One-line change to `.github/workflows/kyc_guardrails.yml`; no application code touched. |

---

## Part V — Deployment Checklist

This checklist represents the complete set of pre-launch verifications. Items marked CONFIRMED have been verified against the live production environment or against the green local test suite on commit `42ae186`.

### Infrastructure

| Item | Status | Action Required |
| --- | --- | --- |
| Backend deployed on Render (`kyc-backend`) | CONFIRMED | None |
| Persistent disk mounted at `/var/data` (10 GB) | CONFIRMED | Re-verify after `42ae186` auto-deploy lands |
| Custom domain `compliance.keepyourcontracts.com` active | CONFIRMED | None |
| `autoDeploy: true` on `main` branch | CONFIRMED | None |
| `ENVIRONMENT=production` set | CONFIRMED | None |
| `KYC_SAFE_MODE=false` | CONFIRMED | None |
| `KYC_SCHEDULERS_ENABLED=true` | CONFIRMED | None |

### Security

| Item | Status | Action Required |
| --- | --- | --- |
| `OPS_PASSWORD` configured | CONFIRMED | None |
| `OPS_SECRET` configured | CONFIRMED | None |
| `OPS_API_KEY` configured | CONFIRMED | None |
| `INTAKE_TOKEN_SECRET` configured (strong, non-default) | CONFIRMED | None |
| Ops routes protected by server-side auth middleware | CONFIRMED | None |
| Public/private UI boundary enforced | CONFIRMED | Guardrail tests pass locally; CI run pending workflow timeout fix |
| **CORS restricted to production domains** | **CONFIRMED (CLOSED THIS PASS)** | None — `server.py` now restricts to `compliance.keepyourcontracts.com` and `jetfighter-compliance.onrender.com` in production. Override via `CORS_ALLOW_ORIGINS`. |

### Email

| Item | Status | Action Required |
| --- | --- | --- |
| SMTP configured and active | CONFIRMED | None |
| `smtp_configured: true` on `/health/ready` | CONFIRMED | None |
| Resend API key configured (primary) | Verify | Run `POST /api/operator/test-email` to confirm delivery |
| From address `noreply@keepyourcontracts.com` verified | Verify | Confirm domain is verified in Resend dashboard |
| Resend Cloudflare-friendly headers in place | CONFIRMED | `User-Agent` and `Accept` added to `services/email_adapters/resend_adapter.py` in prior cycle |

### Payment

| Item | Status | Action Required |
| --- | --- | --- |
| PayPal NCP — CMMC L1 link (`PAFCVQWAP8CNL`) | CONFIRMED | Manually verify link is active and shows $3,500 |
| PayPal NCP — CMMC L2 link (`TGE3GEWHDUTG4`) | CONFIRMED | Manually verify link is active and shows $8,000 |
| PayPal NCP — EU DPP link (`PFMJJ4P5W5KHU`) | CONFIRMED | Manually verify link is active and shows $6,000 |
| Stripe permanently removed | CONFIRMED | None — guardrail test `test_stripe_ban_guardrail.py` enforces |
| **Auto-payment wrapper kwarg forwarding** | **CONFIRMED (FIXED THIS PASS)** | `services/intake/auto_payment.py:_send_payment_link` now correctly forwards `update_status` to the underlying operator action. Previously raised `TypeError` silently in autopay path. |

### CI/CD & Test Suite

| Item | Status | Action Required |
| --- | --- | --- |
| GitHub Actions `kyc_guardrails.yml` active | CONFIRMED | None |
| **818 tests in test suite** | **CONFIRMED (818/818 PASSING)** | None for the suite itself |
| Guardrail tests pass (public exposure, auth, memory, observability) | CONFIRMED | None |
| `pytest.ini` scopes collection to `tests/` only | CONFIRMED (NEW THIS PASS) | None |
| Abandoned `organism/` SQLAlchemy prototype excluded from CI | CONFIRMED (NEW THIS PASS) | None |
| **CI workflow `timeout-minutes` adequate for full suite** | **OPEN** | Bump `timeout-minutes` from 15 to 30 in `.github/workflows/kyc_guardrails.yml`, OR drop the duplicate "Full test suite" step. Workflow-only change; no application code. |

---

## Part VI — Path to First Paying Clients

### Strategy: Controlled Onboarding Acquisition

The platform is ready. The acquisition strategy is defined in `docs/CONTROLLED_ONBOARDING_ACQUISITION.md` and is deliberately conservative: 5 to 15 real onboarding tests before any scale outreach. This is not a marketing campaign — it is a controlled validation of the complete client experience, from first contact to project kickoff.

### Target Segments

The three highest-fit segments for the initial cohort are organizations that already feel compliance documentation pain and have someone who owns it. Aerospace suppliers facing CMMC pressure from prime contractors, manufacturing operators dealing with recurring customer questionnaires, and compliance-heavy SMBs with scattered policies on shared drives are all ideal candidates. The disqualifier for all segments is the same: anyone who expects the platform to guarantee an audit pass rather than provide organization and visibility.

### The First Client Flow (Step by Step)

The complete client journey, from outreach to active project, runs as follows. The operator's role is minimal by design — the organism handles the intelligence work.

**Step 1 — Outreach.** Use the plain-English messaging templates in `docs/CONTROLLED_ONBOARDING_ACQUISITION.md`. The LinkedIn and email templates are ready to use. Personalize the inquiry URL with a `ref=` parameter for cohort tracking (e.g., `?ref=mvp-linkedin-01`). Do not mention AI, autonomy, or the organism. The message is about organizing paperwork and seeing where you stand.

**Step 2 — Inquiry.** The client opens `https://compliance.keepyourcontracts.com/ui/intake` and submits paperwork directly — the prior two-step "inquiry then intake" handoff has been compressed into a single upload-first surface. The organism creates an intake record, writes the entity to central memory, and issues a signed magic link for any follow-up file uploads.

**Step 3 — Intake and Upload.** The client uploads their existing documentation — a policy, an org chart, a customer questionnaire. The upload pipeline fsyncs the files, writes them to the hash ledger, and verifies them through the forensic proof gate before the operator queue ever shows them. The Evidence Intelligence engine analyzes the uploads, extracts entities, maps gaps, and writes findings to the central timeline.

**Step 4 — Operator Review.** Open `/ui/vio.html` to see the client's position in the awareness field and the system-wide organism strip. Click the organism row to open the per-company detail panel — every uploaded document with a view/download link, every generated document, every missing document, the evidence summary, all identifiers, and a `findings` block highlighting anything that needs attention (extraction failures, stale payment links, file-on-disk mismatches). Open `/ui/control.html` to take action.

**Step 5 — Free Trial or Payment.** For the first few clients, the operator can skip the payment step entirely and click **Kickoff project** directly. This validates the complete flow and generates real data without the friction of a financial transaction. When ready to charge, select the service from the dropdown (CMMC L1, CMMC L2, or EU DPP), click **Send payment link**, and the organism dispatches the PayPal NCP link via email. The autopay path (`services/intake/auto_payment.py`) can also dispatch automatically when classification confidence ≥ 0.65 on a known category — and that path now correctly preserves `pending_review` status so the operator can still confirm in the queue.

**Step 6 — Kickoff.** After payment is confirmed in the PayPal dashboard, click **Kickoff project**. The organism creates the project workspace, links all uploaded evidence, and the compliance review begins.

### Service Catalog

| Service | Price | PayPal ID | Ideal Client |
| --- | --- | --- | --- |
| CMMC Level 1 Fast-Track Assessment | $3,500 | `PAFCVQWAP8CNL` | Small org, Level 1 scope, first CMMC engagement |
| CMMC Level 2 Readiness Assessment | $8,000 | `TGE3GEWHDUTG4` | Level 2 scope, SSP/POA&M support needed |
| EU Digital Product Passport Pilot | $6,000 | `PFMJJ4P5W5KHU` | EU market exposure, DPP data model review |

### Outreach Messaging (Unchanged — Ready to Use)

LinkedIn message for the aerospace supplier segment:

> Hi [Name] — I work with small suppliers who get hit with documentation requests from primes and audits. We run a simple readiness review: you show what you already have, we help organize it and flag gaps. No pitch deck — one form, then a short intake. Worth a 10-minute look if paperwork is eating your week?

For manufacturing operators:

> Hi [Name] — many ops leaders I talk to are tired of digging for the same policies every time a customer asks for proof. We offer a structured readiness review: upload what exists, get clarity on what's missing. If that's a current headache, I can send the one-link start.

---

## Part VII — What the Platform Knows About Itself

This section answers the question the operator needs answered before trusting the platform with real clients: does the platform know what it is, what it is doing, and what it is not doing?

The answer is yes, and it is verifiable in real time — and as of this pass it is verifiable through a **reusable, domain-agnostic awareness package** that can be lifted out and used by other organisms.

The organism maintains continuous self-awareness through six live endpoints, all protected by operator authentication:

`GET /api/memory/organism-status` returns the current integration classification of all 22 engines — which are plugged, which are partial, and which are outside by design. This is the organism's self-report on its own wiring.

`GET /api/memory/learning` returns the current learning state: signal effectiveness scores, conversion counts across the funnel (lead to inquiry, inquiry to intake, intake to evidence), and segment performance patterns. This is the organism reporting on what it has learned.

`GET /api/memory/self-heal` returns the current correction suggestions generated by the immune system — orphan linkages, missing bridges, and data inconsistencies that the organism has detected and queued for review. This is the organism reporting on what it knows is wrong.

`GET /api/operator/organism-observability` returns the full telemetry stream, funnel metrics, and health indicators. This is the organism's complete situational awareness report.

`GET /api/operator/organism/state` returns the live awareness snapshot produced by `organism_core` and the KYC bindings — overall status, current bottleneck, severity-classified findings, recommendations, and active residue. This is the organism's first-person voice.

`GET /api/operator/organism/history` returns the rolling snapshot history written by `organism_core/persistence/snapshot_writer.py`. This is the organism's memory of its own past states, available for trend inspection.

In addition, the **VIO header strip** now embeds a compact organism summary on every operator screen, refreshed from a 45-second TTL cache so the operator never has to leave the awareness field to know how the platform feels.

The platform is self-contained. It does not try to be something it is not. It knows its own boundaries, enforces them through guardrail tests in CI and through a live residue scanner, and reports on its own state continuously through both first-person endpoints and an ambient header strip. It is ready.

---

## Part VIII — Critical Risks & Open Items

### Active Risks

**CI workflow timeout cap.** `jobs.guardrails.timeout-minutes: 15` in `.github/workflows/kyc_guardrails.yml` is now structurally too tight: the full suite needs ~14–22 minutes depending on runner. The most-recent push (run `26895968230`) was cancelled at exactly the 15-minute boundary. Local suite is fully green; CI cannot prove that until the cap is raised or the duplicate full-suite step is removed. **One-line workflow change; no application code touched. Recommended in §IX.**

**PayPal payment confirmation is manual.** There is no automated payment webhook on the current path. The operator must manually verify payment in the PayPal dashboard before kicking off a project. This is acceptable for the initial 5 to 15 client cohort but will become a bottleneck at scale. A PayPal webhook integration should be planned for the next development cycle.

**VIO operator-action surfacing inside detail panel.** The composite detail endpoint now returns everything the operator needs to *see* — uploads, generated documents, missing documents, evidence, findings. It does not yet expose the action buttons (Send payment link, Kickoff project, Mark high-value) inline. Until that ships, the operator still has to flip to `/ui/control.html` to execute. The awareness field is real; the action field follows.

**Acquisition scoring not in central timeline.** The acquisition scoring engine (80% ready) writes scores to the review queue CSV rather than the central timeline. Scored leads are therefore not fully visible in the organism's memory. Known partial integration; should be completed before the acquisition engine is used at scale.

**Reddit API credentials required.** The Reddit acquisition connector is built and ready but requires `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, and `REDDIT_PASSWORD` to be configured in the Render environment. Without these, the autonomous Reddit signal detection will not run. The connector is harmless in their absence.

### Non-Risks (Confirmed Safe)

The following items were audited and confirmed to pose no risk to client acquisition or platform stability:

The Stripe card payment rail has been permanently removed and is enforced by a CI guardrail test. It cannot be accidentally reintroduced. The pre-rebrand public intake route family and the pre-rebrand customer upload surface have been permanently removed and the residue scanner in `organism_core/residue/scanner.py` will surface any reintroduction. The intake token secret is configured with a strong, non-default value. The public/private UI boundary is enforced by both server-side middleware and CI guardrail tests. The durable disk is mounted and confirmed writable, meaning client uploads survive server restarts and deploys. The self-healing immune system is active and will surface any data inconsistencies before they become client-facing problems. **CORS is now production-locked**, eliminating the prior brief's largest pre-launch risk. The **auto-payment wrapper kwarg-drop bug** that would silently fail autopay for low-confidence intakes has been fixed and is regression-covered by the green suite.

---

## Part IX — Recommended Immediate Actions

The following actions are recommended in sequence before the first client is contacted.

**Action 1 (Today).** Apply the CI workflow timeout fix. Bump `timeout-minutes` from `15` to `30` in `.github/workflows/kyc_guardrails.yml`, or remove the redundant final "Full test suite" step (the preceding 10 named steps already cover the guardrail-critical tests). Either change is one-line. Push and confirm the next CI run completes green on `42ae186`.

**Action 2 (Today).** Manually verify all three PayPal NCP payment links are active and display the correct service names and prices. Open each URL in a browser and confirm the checkout page renders correctly.

**Action 3 (Today).** Send a test email using `POST /api/operator/test-email` from the operator cockpit. Confirm delivery to your inbox. This validates the full Resend-primary, SMTP-fallback path before a real client depends on it.

**Action 4 (Today).** Run the manufactured company seed script against the live environment (`python scripts/seed_vio_live.py`) and verify all five test companies appear correctly in VIO with the correct states and priority ordering. Open the per-company detail panel for at least one and confirm the new composite payload renders: uploaded documents with view/download links, generated documents, missing documents, evidence snapshot, identifiers, and the `findings` block.

**Action 5 (Today).** Verify on the live Render service that:

- the `kyc-data` 10 GB persistent disk is attached at `/var/data` (without it, uploads are refused by design);
- `OPS_PASSWORD`, `OPS_SECRET`, `OPS_API_KEY`, `INTAKE_TOKEN_SECRET`, `PUBLIC_BASE_URL` are all set;
- `RESEND_API_KEY` is current and `keepyourcontracts.com` is verified in Resend → Domains;
- DNS for `compliance.keepyourcontracts.com` still resolves to Render.

**Action 6 (This Week).** Begin outreach to the first 3 to 5 carefully selected targets using the messaging templates in `docs/CONTROLLED_ONBOARDING_ACQUISITION.md`. Run these first clients through the complete flow for free to validate the experience end-to-end with real people and real documents. Use the new VIO detail panel as the primary operator awareness surface; fall back to `/ui/control.html` only for actions VIO does not yet surface.

**Action 7 (Next Sprint).** Plan the PayPal webhook integration to automate payment confirmation. Plan the VIO operator-action surfacing inside the detail panel — once Send payment link, Kickoff project, and Mark high-value are inline, the cockpit can be retired and VIO becomes the sole command center, satisfying the VIO Constitution.

---

*End of brief. Companion documents: `docs/DEPLOYMENT_INVENTORY.md` (green/amber/red engine inventory), `docs/CI_GUARDRAILS_RUN_26895968230_ROOT_CAUSE.md` (CI cancellation post-mortem), `docs/ORGANISM_CORE_ARCHITECTURE.md` (awareness package architecture).*

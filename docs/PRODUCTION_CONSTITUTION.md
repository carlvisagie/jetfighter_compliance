# Production Constitution — KeepYourContracts

**Status:** Binding governance for production operations.  
**Scope:** Production fortress only — no feature or business-logic changes.  
**Companion law:** [`KYC_CONSTITUTION.md`](KYC_CONSTITUTION.md) (organism IRON LAW)  
**Environment truth:** [`PRODUCTION_IS_THE_ONLY_TRUTH.md`](PRODUCTION_IS_THE_ONLY_TRUTH.md)

---

## 1. System Purpose

KeepYourContracts is a **central-memory compliance organism** that receives customer paperwork, preserves forensic custody, extracts evidence intelligence, and gives operators a truthful cockpit (VIO + control) without alternate truth stores.

Production exists to serve **real customers on durable disk** — not local developer trees, not pytest temp dirs, not blueprint drift.

---

## 2. Canonical Production Architecture

| Item | Canonical value |
|------|-----------------|
| **Repository** | `https://github.com/carlvisagie/jetfighter_compliance.git` |
| **Branch** | `main` |
| **Render service (live)** | `jetfighter_compliance` (`srv-d83gut57vvec739efv6g`) |
| **Blueprint label** | `kyc-backend` in `render.yaml` — **do not reapply blueprint blindly** (disk attach incident 2026-06-04) |
| **Public URL** | `https://compliance.keepyourcontracts.com` |
| **Render URL** | `https://jetfighter-compliance.onrender.com` |
| **Data root** | `/var/data` (`KYC_DATA`, disk `kyc-data`, 10 GB) |
| **Entrypoint** | `server.py` (FastAPI) |
| **Organism adapter** | `services/organism_state/` → `organism_core/` |

Architecture detail per subsystem: [`docs/architecture/`](architecture/).

---

## 3. Canonical Intake Flow

1. Customer reaches `/ui/intake` or session upload APIs.
2. `POST /api/intake/upload` → `services/intake/intake.py` persists under `intakes/<FB-*>/uploads/`.
3. Durability + hash verify → audit receipt → transaction log → index row.
4. Proof gate (`services/intake/proof_gate.py`) before customer success.
5. Operator queue: `GET /api/operator/intake/queue`.

**Canonical intake lifecycle phases:** `upload_received` → `files_persisted` → `hash_verified` → `audit_written` → `intake_committed` → `index_committed` (+ classification / EI hooks).

Full detail: [`architecture/intake.md`](architecture/intake.md), [`FORENSIC_INTEGRITY_ENGINE.md`](FORENSIC_INTEGRITY_ENGINE.md).

---

## 4. Canonical Evidence Flow

1. Upload files live in `intakes/<id>/uploads/` (authoritative custody).
2. Promotion mirror: `projects/<id>/evidence/` (operator/EI visibility).
3. Evidence intelligence artifacts: `projects/<id>/evidence_intelligence/` (derived, rebuildable).
4. Derived registry: rebuilt from disk + audit + transactions — **not** a second source of truth.
5. Central memory bridge: `services/memory/organism_integration.py`.

Full detail: [`architecture/evidence_intelligence.md`](architecture/evidence_intelligence.md), [`EVIDENCE_INTELLIGENCE_LAYER.md`](EVIDENCE_INTELLIGENCE_LAYER.md).

---

## 5. Canonical Organism Flow

1. Collectors gather signals (`services/organism_state/collectors.py`).
2. Checks evaluate fleet truth (`disk_vs_intake_index`, `evidence_vs_files`, …).
3. Snapshot: `GET /api/operator/organism/state` → `data/organism_state.json`.
4. Telemetry + adaptive signals → `data/memory/`.

Full detail: [`architecture/organism.md`](architecture/organism.md), [`ORGANISM_CORE_ARCHITECTURE.md`](ORGANISM_CORE_ARCHITECTURE.md).

---

## 6. Canonical VIO Flow

1. Operator opens `/ui/vio.html` (protected).
2. Overview: `GET /api/operator/vio/overview`.
3. Company detail + cognitive topology feed L1/L2 surfaces.
4. Environment ribbon from `GET /api/operator/environment-label` — **must** show PRODUCTION on live host.

Full detail: [`architecture/vio.md`](architecture/vio.md), [`VIO_CONSTITUTION.md`](VIO_CONSTITUTION.md).

---

## 7. Canonical Acquisition Flow

1. Controlled onboarding validation — not autonomous spam (`CONTROLLED_ONBOARDING_ACQUISITION.md`).
2. Discovery connectors → leads store → memory bridge.
3. Manual acquisition flag: `KYC_ENABLE_MANUAL_ACQUISITION`.

Full detail: [`architecture/acquisition.md`](architecture/acquisition.md).

---

## 8. Protected Components

See also **PROTECTED SYSTEMS** in [`../AGENTS.md`](../AGENTS.md).

| Component | Path / contract |
|-----------|-----------------|
| Central memory | `services/memory/*`, `data/memory/*` |
| Intake custody | `services/intake/*`, `intakes/*/uploads/` |
| Evidence intelligence | `services/evidence_intelligence/*` |
| Organism state | `services/organism_state/*`, `organism_core/*` |
| Ops auth | `services/ops_auth.py`, `OPS_PASSWORD`, session cookie |
| Durable storage gate | `services/durable_storage.py`, `/var/data` probe |
| Render disk config | Live `jetfighter_compliance` disk mount — not unapplied blueprint |
| Guardrail tests | `tests/test_public_ui_exposure.py`, `test_kyc_guardrails.py`, CI workflow |

---

## 9. Forbidden Changes (without owner approval)

- Alternate data roots or shadow indexes for customer files
- Silent repair of integrity disagreements (incidents + operator visibility required)
- Weakening ops auth or exposing control/memory/command publicly
- Mock discovery domains in production paths
- Reintroducing banned legacy card-payment rails (PayPal is the only path; see payment-rail ban doc in `docs/`)
- Force-push or delete `main`
- Feature/UI redesign under the guise of “fortress” work

---

## 10. Deployment Rules

1. **No deployment changes in fortress patches** unless explicitly authorized.
2. Live service is managed via Render dashboard/API — blueprint name mismatch is documented in `render.yaml`.
3. Every deploy must preserve disk `kyc-data` at `/var/data`.
4. Pre-deploy gate: [`DEPLOYMENT_GATE.md`](DEPLOYMENT_GATE.md).
5. Post-deploy: verify `GET /api/public/build-info` commit matches intended SHA on **both** branded and Render URLs.

---

## 11. Production Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Full pytest green | `python -m pytest tests/ -q` |
| Health | `GET /healthz` → 200 |
| Readiness | `GET /health/ready` → 200 |
| Build info | `GET /api/public/build-info` → `environment: production` |
| Fleet reconcile | `GET /api/operator/intake/reconcile` → no failing intake IDs |
| Organism `evidence_vs_files` | `GET /api/operator/organism/state` → check `ok: true` |
| Scheduler | Boot logs / `probe_boot_status.py` → schedulers started |
| Truth audit current | [`PRODUCTION_TRUTH_AUDIT.md`](PRODUCTION_TRUTH_AUDIT.md) date + commit |

Live snapshot: [`PRODUCTION_TRUTH_AUDIT.md`](PRODUCTION_TRUTH_AUDIT.md).  
Restore baseline: [`RESTORE_POINT.md`](RESTORE_POINT.md).

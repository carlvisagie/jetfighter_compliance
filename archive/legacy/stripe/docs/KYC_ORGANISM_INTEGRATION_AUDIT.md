> **DEPRECATED — NOT DEPLOYED — HISTORICAL ONLY**
> Archived under rchive/legacy/stripe/. Do not use for launch decisions.

# KYC Organism Integration Audit

**Audit date:** 2026-05-26 (guardrails + constitution pass)  
**Binding law:** [`KYC_CONSTITUTION.md`](./KYC_CONSTITUTION.md) · [`../AGENTS.md`](../AGENTS.md)  
**Metaphor:** central memory = brain · engines = organs · timeline = nervous system · learning = adaptive memory · self-healing = immune system

## KYC IRON LAW (summary)

Central memory is canonical. Active engines **plugged** below must keep read/write or telemetry bridges. **Do not** add new islands without updating this audit and `tests/test_organism_integration.py`.

---

## Executive summary

| Metric | Count |
|--------|------:|
| Engines audited | 20 |
| Plugged | 14 |
| Partial | 2 |
| Outside (allowed) | 3 |
| Legacy inactive | 1 |
| Duplicate memory islands | 1 (acquisition weights — bridged) |

**Verdict:** `organism_partial` → trending **unified** after adapter pass. Critical onboarding vessels (inquiry, intake, kickoff, ledger, evidence, forensics, leads) write central memory. Reports/email remain read-only outside layers by design.

Live status: `GET /api/memory/organism-status`

---

## Classification key

| Class | Meaning |
|-------|---------|
| **1. Plugged** | Reads and/or writes central memory via adapters |
| **2. Partial** | Some hooks; parallel store or read-only |
| **3. Outside** | Operational but not indexed (acceptable for transport/UI) |
| **4. Legacy inactive** | Documented; not production path |
| **5. Duplicate island** | Separate durable truth; bridge required |

---

## Module audit matrix

### Central memory core — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/memory/*.py`, `data/memory/` |
| **Reads** | entities, timelines, signals, learning_state, corrections |
| **Writes** | all memory JSONL + learning_state |
| **Read before** | Yes (`read_entity_context`, `lookup`) |
| **Write after** | Yes (all `link_*`, `safe_*`) |
| **Orphan risk** | Low |
| **Duplicate truth** | None |
| **Fix** | — |

---

### Acquisition discovery / import — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/acquisition/discovery.py`, `scripts/acquisition_import_candidates.py` |
| **Reads** | `safe_read_before_lead_score` before CSV row scoring |
| **Writes** | `link_lead`, `resolve_or_create_entity` after import |
| **Orphan risk** | Low |
| **Duplicate truth** | Low (CSV + queue remain operational copies) |

---

### Acquisition scoring / ranking — **PARTIAL (2)**

| Field | Value |
|-------|-------|
| **Paths** | `services/acquisition/scoring.py` |
| **Reads** | `memory_context` from discovery |
| **Writes** | Review queue CSV only |
| **Read before** | Yes |
| **Write after** | No (scores not in central timeline) |
| **Orphan risk** | Low |
| **Fix** | Optional: emit learning signal on band changes |

---

### Acquisition forensics / fingerprints — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `forensics.py`, `fingerprints.py`, `history.py` |
| **Reads** | Project dirs, intelligence JSONL |
| **Writes** | `forensic_events.jsonl`, org profiles + **`safe_write_after_forensic_event`** |
| **Bridge** | `safe_record_inquiry/intake/evidence` → central memory |
| **Duplicate truth** | Medium (forensic store + central timeline) |

---

### Acquisition outcome memory (weights) — **PLUGGED via bridge (5→1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/acquisition/memory.py` |
| **Writes** | `outcomes.jsonl`, `weights.json` |
| **Bridge** | `record_outcome` → `safe_write_after_acquisition_outcome` → central timeline + learning |
| **Duplicate truth** | Medium (weights stay in acquisition island by design) |

---

### Inquiry submit — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `server.py` `/api/inquiry/submit`, `ui/inquiry.html` |
| **Writes** | inquiries/, projects/, ledger, forensics, central (`safe_write_after_inquiry`, kickoff links) |
| **Ref handoff** | `[ref:lead_id]` in message from `?ref=` query param |

---

### Intake resolve/submit — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `server.py` `/api/intake/*`, `ui/intake.html` |
| **Writes** | intake.json, workflow, `safe_record_intake`, **`safe_write_after_workflow`** |

---

### Kickoff / project creation — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `server.py` `kickoff()`, `services/projects.py` |
| **Read before** | `safe_read_before_kickoff` |
| **Write after** | `safe_link_after_kickoff`, `safe_link_ledger_event` → `project_created`, `ledger_event`, refs |

---

### Workflow / process engine — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/process.py`, `server.py` mark_done/advance |
| **Writes** | `data/process/{id}.json` + **`safe_write_after_workflow`** timeline |
| **Orphan risk** | Medium (historical projects without entity) |

---

### Evidence / artifact register — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `server.py` `/api/evidence/register`, `services/ledger.py` |
| **Writes** | evidence files, artifacts + `safe_record_evidence` → `evidence_uploaded` |

---

### COC / event ledger — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/ledger.py`, `/api/coc/event`, `/api/coc/event/form` |
| **Writes** | `ledger.log` + `safe_link_ledger_event` / `safe_write_after_coc_event` |
| **Orphan risk** | Medium (legacy events pre-memory) |

---

### Central learning — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/memory/learning.py` |
| **Writes** | `learning_state.json` via `record_learning_signal` |

---

### Self-healing — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/memory/self_healing.py` |
| **Detects** | orphan projects/inquiries, duplicate companies, missing timelines, unlinked forensic/RFQ, engine orphans |
| **Writes** | `corrections.jsonl`, `pending_orphans.jsonl` |

---

### RFQ system — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/rfq.py` |
| **Writes** | `data/rfq/*.json`, ledger + **`safe_write_after_rfq`** |

---

### Background job engine — **PLUGGED (1)**

| Field | Value |
|-------|-------|
| **Paths** | `services/engine.py` |
| **Writes** | **`safe_write_after_job_kickoff`**, **`safe_write_after_sla_event`** on SLA breach |

---

### Alerts / SLA — **PARTIAL (2)**

| Field | Value |
|-------|-------|
| **Paths** | `alerts.py`, `alerts_center.py` |
| **Writes** | alerts.jsonl; SLA escalations now link via engine adapter |
| **Fix** | Alerts center could read entity context before notify (future) |

---

### Email transport — **OUTSIDE (3)**

| Field | Value |
|-------|-------|
| **Paths** | `services/emails.py` |
| **Role** | Transport only — no durable business truth |

---

### Reports / export / binder — **OUTSIDE (3)**

| Field | Value |
|-------|-------|
| **Paths** | `reports.py`, `acquisition/export.py`, `analytics.py` |
| **Role** | Read project/forensic data; should consult central memory for exports (future) |

---

### Stripe webhook — **LEGACY INACTIVE (4)**

| Field | Value |
|-------|-------|
| **Paths** | `server.py` `/webhooks/stripe` |
| **Note** | Tests only; inquiry-led path is production |

---

### organism/ sqlite — **OUTSIDE (3)**

| Field | Value |
|-------|-------|
| **Paths** | `organism/` |
| **Risk** | High duplicate island — not wired; do not use for production truth |

---

### UI ops / health — **OUTSIDE / PLUGGED UI**

| Field | Value |
|-------|-------|
| **Paths** | `ui/control.html`, `ui/status.html`, `ui/memory.html` |
| **memory.html** | Organism Integration Status panel + lookup/self-heal |

---

## Adapter layer (minimal safe fixes)

**File:** `services/memory/organism_integration.py`

| Adapter | Purpose |
|---------|---------|
| `safe_write_after_workflow` | Workflow step/phase → timeline |
| `safe_write_after_rfq` | RFQ opened/bid/awarded → timeline + ref |
| `safe_write_after_acquisition_outcome` | Bridge `record_outcome` → central |
| `safe_write_after_forensic_event` | Forensic JSONL → timeline |
| `safe_write_after_coc_event` | JSON COC events → ledger_event |
| `safe_write_after_job_kickoff` | Post-payment playbook → kickoff memory |
| `safe_write_after_sla_event` | SLA breach → ledger + signal |
| `safe_register_orphan` | Engine orphan → self-heal queue |
| `run_integration_audit` | Runtime registry for UI/API |

**Entity graph fix:** `upsert_entity` preserves latest `refs`; `add_ref` uses latest snapshot.

---

## Remaining risks

1. **Historical orphan projects** (pre-memory) — self-heal suggests links; no auto-delete.
2. **Acquisition weights island** — parallel to `learning_state.json`; outcomes bridged, weights not duplicated centrally.
3. **Reports/exports** — do not yet read central memory for binder context.
4. **organism/sqlite** — separate subsystem; mark LEGACY.
5. **Duplicate timeline rows** — idempotent checks reduce but do not dedupe historical appends.

---

## Tests

```bash
python -m pytest tests/test_organism_integration.py tests/test_central_memory.py -q
python -m pytest tests/test_kyc_guardrails.py tests/test_public_ui_exposure.py tests/test_ops_route_auth.py -q
python -m pytest tests/ -q
```

**CI:** `.github/workflows/kyc_guardrails.yml` — fails on public ops links, missing noindex, unauthenticated protected APIs, central memory failures, UI backup files, fake production discovery flags.

**Required proofs in `tests/test_organism_integration.py`:**

- inquiry → central memory  
- intake → central memory  
- project creation → `project_created`  
- ledger → `ledger_event`  
- evidence → `evidence_uploaded`  
- lead import → `lead_linked`  
- forensic → `forensic_event` + learning  
- self-heal → orphan detection  
- audit API → no critical engine outside (except allowed)  

---

## Final verdict

**Organism: partially unified → operationally unified for onboarding spine.**

All critical customer-path engines (lead → inquiry → kickoff → intake → evidence → ledger → forensics → learning → self-heal) index into central memory. Non-customer layers (email transport, static reports, health probes) remain outside by design.

**Target state:** `organism_unified` when reports read central memory and historical orphans are backfilled.

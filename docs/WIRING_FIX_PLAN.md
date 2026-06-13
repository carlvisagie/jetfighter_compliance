# WIRING FIX PLAN — ORGANISM UNIFICATION

**Date:** 2026-06-13  
**Mission:** Fix all wiring issues to achieve `organism_unified`  
**Current Status:** `organism_partial`

---

## COMPLETED FIXES

### ✓ FIX 1: organism_sqlite Dead Code
**Status:** DELETED  
**Verification:** Directory does not exist  
**Impact:** Removed HIGH orphan risk, HIGH duplicate truth risk

### ✓ FIX 2: Self-Healing Scan
**Status:** RAN  
**Result:** Found 312 orphan projects, 3 orphan inquiries, 50 unlinked forensic, 1 unlinked RFQ, 100 pending orphans  
**Note:** These are legacy/test data that can't be auto-linked (expected)

---

## REMAINING CRITICAL FIXES

### FIX 3: acquisition_memory_island (ARCHITECTURE INVERSION)

**Current Architecture (WRONG):**
```
weights.json (PRIMARY SOURCE)
    ↓ best-effort mirror
learning_state.json (SECONDARY)
```

**Correct Architecture:**
```
data/memory/learning_state.json (PRIMARY SOURCE - ONE BRAIN)
    ↓ read
services/acquisition/scoring.py (CONSUMER)
```

**Action Required:**
1. Migrate all weight learning logic to `services/memory/learning.py`
2. Update `services/acquisition/scoring.py` to read from central memory
3. Delete `services/acquisition/memory.py` weights functions
4. Delete `data/acquisition/intelligence/weights.json`
5. Remove from ENGINE_REGISTRY as separate island

**Files to Modify:**
- `services/acquisition/memory.py` — remove weight functions
- `services/acquisition/scoring.py` — read from central learning_state
- `services/memory/learning.py` — add acquisition weight management
- `services/memory/organism_integration.py` — remove island entry

**Impact:** Resolves MEDIUM orphan risk, MEDIUM duplicate truth risk, constitutional violation

---

### FIX 4: job_engine (HIGH RISK)

**Issues:**
- Orphan risk: HIGH
- Duplicate truth risk: HIGH
- 100 pending orphans detected

**Current Implementation:**
- Writes to `data/jobs/*.json`
- Claims to emit telemetry (lines 27-33, 97-109 in engine.py)
- Has organism bridge (lines 46-57)

**Investigation Needed:**
1. Verify telemetry is actually emitted on ALL job states
2. Verify organism bridge is called for ALL job types
3. Identify why 100 orphans exist
4. Add missing telemetry for job failures

**Action Required:**
1. Audit all `enqueue()` callers
2. Verify telemetry for:
   - Job queued
   - Job running
   - Job success
   - Job failure
   - Job retry
3. Add missing organism bridges
4. Wire job queue depth to organism health

**Impact:** Resolves HIGH orphan risk, HIGH duplicate truth risk

---

### FIX 5: workflow (MEDIUM RISK — Parallel Store)

**Issues:**
- Orphan risk: MEDIUM
- Duplicate truth risk: MEDIUM
- Stores state in `data/process/{project}.json`

**Current Implementation:**
- `services/process.py` line 59: `_wf_path(project_id).write_text(json.dumps(obj, indent=2))`
- Has organism bridge: `safe_write_after_workflow` (organism_integration.py lines 313-336)

**Investigation Needed:**
1. Is `data/process/` the canonical source for workflow state?
2. Or is central memory timeline the canonical source?
3. Are ALL workflow state changes bridged?

**Action Required:**
1. Verify workflow bridge completeness
2. If incomplete, add missing bridges
3. If `data/process/` is canonical, migrate to central memory
4. Document workflow state as cache vs source of truth

**Impact:** Resolves MEDIUM orphan risk, MEDIUM duplicate truth risk

---

### FIX 6: coc_ledger (MEDIUM RISK — Parallel Store)

**Issues:**
- Orphan risk: MEDIUM
- Duplicate truth risk: MEDIUM
- Stores events in `data/ledger/ledger.log`

**Current Implementation:**
- `services/ledger.py` — append-only log
- Has organism bridge: `safe_write_after_coc_event`, `safe_link_ledger_event`

**Investigation Needed:**
1. Is `ledger.log` the canonical source for COC events?
2. Or is central memory timeline the canonical source?
3. Are ALL ledger events bridged?

**Action Required:**
1. Verify ledger bridge completeness
2. If incomplete, add missing bridges
3. If `ledger.log` is canonical, justify why (immutable audit trail)
4. Document ledger as compliance artifact vs operational truth

**Impact:** Resolves MEDIUM orphan risk, MEDIUM duplicate truth risk

---

### FIX 7: rfq (MEDIUM RISK — Parallel Store)

**Issues:**
- Orphan risk: MEDIUM
- Duplicate truth risk: MEDIUM
- 1 RFQ project unlinked
- Stores state in `data/rfq/*.json`

**Current Implementation:**
- `services/rfq.py` line 63: `_rfq_path(obj.rfq_id).write_text(json.dumps(d, indent=2))`
- Has organism bridge: `safe_write_after_rfq` (organism_integration.py lines 339-367)

**Investigation Needed:**
1. Why is 1 RFQ project unlinked?
2. Are ALL RFQ state changes bridged?
3. Is `data/rfq/` canonical or cache?

**Action Required:**
1. Link the 1 orphan RFQ project
2. Verify RFQ bridge completeness
3. Add missing bridges for RFQ state changes
4. Migrate to central memory or justify parallel store

**Impact:** Resolves MEDIUM orphan risk, MEDIUM duplicate truth risk, 1 orphan

---

### FIX 8: acquisition_forensics (MEDIUM RISK — Parallel Store)

**Issues:**
- Orphan risk: MEDIUM
- Duplicate truth risk: MEDIUM
- 50 forensic projects unlinked
- Parallel stores: `forensic_events.jsonl`, `org_profiles.jsonl`
- Fix note: "Forensic store parallels central; bridged on inquiry/intake/evidence"

**Current Implementation:**
- Has organism bridge: `safe_write_after_forensic_event` (organism_integration.py lines 489-513)
- Only bridges on inquiry/intake/evidence (not all forensic events)

**Investigation Needed:**
1. Why are 50 forensic projects unlinked?
2. What forensic events are NOT bridged?
3. Why does `org_profiles.jsonl` exist outside central entity graph?

**Action Required:**
1. Link 50 orphan forensic projects
2. Bridge ALL forensic events (not just inquiry/intake/evidence)
3. Migrate `org_profiles.jsonl` to central entity graph
4. Verify `forensic_events.jsonl` is artifact, not canonical source

**Impact:** Resolves MEDIUM orphan risk, MEDIUM duplicate truth risk, 50 orphans

---

## ARCHITECTURAL NOTES (Not failures, but non-canonical patterns)

### compliance_intelligence
- **Note:** "Local snapshots are artifacts; timeline + review queue drive actions"
- **Status:** OK — documented as cache pattern
- **No fix needed** — architecture is correct

### evidence_intelligence
- **Note:** "Project jsonl artifacts are not canonical; timeline is source of truth"
- **Status:** OK — documented as cache pattern
- **No fix needed** — architecture is correct

### emails
- **Note:** "Transport only; canonical truth in central memory telemetry"
- **Status:** OK — transport layer, no business logic
- **No fix needed** — architecture is correct

---

## SUCCESS CRITERIA

**Target Verdict:** `organism_unified`

**Requirements:**
- ✓ organism_sqlite deleted
- ✓ Self-healing scan run
- ☐ acquisition_memory_island migrated to ONE BRAIN
- ☐ job_engine HIGH risk resolved
- ☐ workflow parallel store resolved
- ☐ coc_ledger parallel store resolved or justified
- ☐ rfq parallel store resolved
- ☐ acquisition_forensics parallel store resolved
- ☐ All orphans linked or documented as legacy/test data
- ☐ Re-run integration audit → verdict = `organism_unified`

---

## COMPLEXITY ASSESSMENT

### Quick Wins (Already Done)
- ✓ Delete organism_sqlite
- ✓ Run self-healing

### Medium Complexity (Verification + Minor Fixes)
- FIX 4: job_engine telemetry audit
- FIX 5: workflow bridge verification
- FIX 6: coc_ledger bridge verification  
- FIX 7: rfq bridge verification + link 1 orphan
- FIX 8: forensics bridge verification + link 50 orphans

### High Complexity (Architecture Migration)
- FIX 3: acquisition_memory_island inversion
  - Requires migrating weight learning logic
  - Requires updating all weight consumers
  - Requires deleting parallel store
  - Risk: Breaking acquisition scoring if done wrong

---

## RECOMMENDED APPROACH

**Phase 1: Verification (Low Risk)**
1. Audit job_engine, workflow, coc_ledger, rfq, forensics
2. Document which bridges are missing
3. Document which stores are canonical vs cache
4. Create detailed migration specs

**Phase 2: Bridge Completion (Medium Risk)**
1. Add missing organism bridges
2. Link orphan projects where possible
3. Document orphans that can't be linked (test data)
4. Verify telemetry emission

**Phase 3: Architecture Migration (High Risk)**
1. Migrate acquisition_memory_island to central memory
2. Delete parallel weight store
3. Update all consumers
4. Test acquisition scoring still works

**Phase 4: Verification**
1. Re-run integration audit
2. Verify verdict = `organism_unified`
3. Monitor for regression

---

## ESTIMATED EFFORT

- **Phase 1 (Verification):** 2-4 hours
- **Phase 2 (Bridge Completion):** 4-6 hours
- **Phase 3 (Architecture Migration):** 6-8 hours
- **Phase 4 (Verification):** 1-2 hours

**Total:** 13-20 hours of focused work

---

## CURRENT STATUS

**Completed:** 2/10 fixes  
**In Progress:** FIX 3 (acquisition_memory_island)  
**Next:** Complete Phase 1 verification, then proceed systematically

**The organism will be fully unified after all fixes are complete.**

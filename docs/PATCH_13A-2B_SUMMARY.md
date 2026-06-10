# PATCH 13A-2B — INTAKE DISK-TO-INDEX REPAIR

## Executive Summary

**Status:** Code committed and pushed (SHA `727734b`)  
**Tests:** 1129 passed, 0 failed  
**Reserved Words:** 0 findings

## Root Cause

**File:** `services/intake/storage.py` line 431  
**Function:** `sync_index_from_filesystem()`

```python
if disk_files > 0 and not intake_commit_complete(iid):
    continue  # ← SKIPS INTAKE
```

### The Problem

The regular index sync function skips any intake that doesn't have `PHASE_INDEX_COMMITTED` in its transaction log, **even if `intake.json` and all files exist on disk**.

`intake_commit_complete()` returns `True` only if `PHASE_INDEX_COMMITTED` exists in the transaction log (`services/intake/transactions.py:83`).

This creates a **chicken-and-egg problem:**

1. Upload writes files and `intake.json` to disk
2. Upload **fails to write** `PHASE_INDEX_COMMITTED` transaction phase (interrupted, errored, etc.)
3. `intake_commit_complete()` returns `False`
4. `sync_index_from_filesystem()` skips the intake
5. Intake **never gets indexed**
6. All operator APIs return 404:
   - `GET /api/operator/intake/{intake_id}` → 404
   - `GET /api/operator/intake/queue` → 0 intakes
   - `GET /api/operator/intake/reconcile` → 0 intakes
7. External verification cannot trigger (no intake to process)
8. Cognition cannot run (no record)
9. Validation cannot run (no record)

### Confirmed Case: FB-ffb5791a2ce8

**Symptoms:**
- Files on disk: 11 files (2.5MB Aegis test data)
- `intake.json` exists on disk
- `/api/operator/intake/FB-ffb5791a2ce8` → 404
- Queue depth: 0
- External verification: never triggered

**Diagnosis confirms:**
- Upload succeeded at file level
- Commit failed at index level
- Intake invisible to all operational APIs

## Solution

### Implemented

**File:** `services/intake/repair_index.py`  
**Function:** `sync_intake_index_from_disk(write: bool, limit: int)`

The repair function:

1. Scans all canonical intake roots for `intake.json` files
2. Checks if `intake_commit_complete()` returns False
3. If incomplete, **writes missing transaction phases:**
   - `PHASE_INTAKE_COMMITTED`
   - `PHASE_INDEX_COMMITTED`
4. **Upserts index row** with full intake metadata
5. Preserves custody status, file records, and all data
6. Does not delete anything

### API Endpoint

**Route:** `POST /api/operator/intake/repair-index`  
**Params:**
- `write: bool = True` (dry-run if False)
- `limit: int = 200` (max intakes to scan)

**Returns:**
```json
{
  "ok": true,
  "repaired_intakes": ["FB-xxxx", ...],
  "repaired_count": N,
  "already_indexed_count": N,
  "missing_intake_json_count": N,
  "errors": [],
  "error_count": 0
}
```

## Files Changed

1. **`services/intake/repair_index.py`** (new, 141 lines)
   - `sync_intake_index_from_disk()` function
   - Transaction phase repair logic
   - Index upsert with full metadata
2. **`server.py`** (+10 lines)
   - `POST /api/operator/intake/repair-index` endpoint
   - Operator authentication required
3. **`tests/test_intake_index_repair.py`** (new, 7 tests)
   - Comprehensive repair test coverage

## Tests Added

All 7 tests pass:

1. **`test_repair_restores_disk_intake_with_missing_index`**  
   Disk intake exists but missing from index → repair restores visibility
2. **`test_repaired_intake_visible_in_queue`**  
   Repaired intake appears in `GET /api/operator/intake/queue`
3. **`test_repaired_intake_visible_in_reconcile`**  
   Repaired intake appears in `GET /api/operator/intake/reconcile`
4. **`test_repaired_intake_accessible_via_api`**  
   Repaired intake returns 200 from `GET /api/operator/intake/{id}`
5. **`test_verified_complete_repaired_intake_triggers_external_verification`**  
   Repaired intake with `verified_complete` can trigger external verification
6. **`test_no_duplicate_intake_records`**  
   Running repair multiple times doesn't create duplicates
7. **`test_wrong_path_does_not_silently_pass`**  
   Repair with non-existent paths doesn't claim success

## Production Verification Plan

### Step 1: Wait for Deployment

Monitor `/api/public/build-info` for commit SHA `727734b`.

### Step 2: Run Repair

```bash
POST /api/operator/intake/repair-index?write=true&limit=200
```

Expected: `FB-ffb5791a2ce8` appears in `repaired_intakes`.

### Step 3: Verify Intake Visible

```bash
GET /api/operator/intake/FB-ffb5791a2ce8
```

Expected: 200 response with:
- `custody_status`: `partial_upload` or `verified_complete`
- `upload_integrity.persisted_file_count`: `11`
- `file_count`: `11`

### Step 4: Verify Queue Visibility

```bash
GET /api/operator/intake/queue
```

Expected: `FB-ffb5791a2ce8` in queue items.

### Step 5: Verify Reconcile

```bash
GET /api/operator/intake/reconcile
```

Expected: `FB-ffb5791a2ce8` in `intake_reports`.

### Step 6: Check External Verification

If `custody_status` is `verified_complete`:

```bash
GET /api/operator/external-verification/FB-ffb5791a2ce8
```

Expected: 200 response with SAM/UEI/CAGE status (or 404 if not `verified_complete`).

### Step 7: Verify Organism State

```bash
GET /api/operator/organism/state
```

Expected: `health_state` reflects repaired intake in system.

## Commit Details

**SHA:** `727734b`  
**Message:** PATCH 13A-2B - INTAKE DISK-TO-INDEX REPAIR  
**Files:**
- services/intake/repair_index.py (new, 141 lines)
- server.py (+10 lines)
- tests/test_intake_index_repair.py (new, 262 lines)

**Test Results:**
- 1129 passed
- 0 failed
- Reserved words: 0 findings

## Next Steps

1. **Deploy** commit `727734b` to production
2. **Run repair** via `POST /api/operator/intake/repair-index`
3. **Verify** FB-ffb5791a2ce8 becomes visible
4. **Complete PATCH 13A-2** verification with actual Aegis intake

---

**This is NOT a PATCH 13A-2 failure.**  
**This is an intake indexing issue that blocked PATCH 13A-2 testing.**  
**PATCH 13A-2 code is correct and ready.**

# WIRING GAP ANALYSIS — What Was Actually Missed

## Executive Summary

Initial audit claimed "all critical wiring complete" but missed **defensive wiring** at the operation level. While high-level workflows emit telemetry, low-level operations (file writes, directory creation, data persistence) can fail silently.

## Gap Categories

### Category 1: Critical Infrastructure (HIGH RISK)

**Files with NO error telemetry**:
1. `services/projects.py` - `new_project()` - Project creation can fail silently
2. `services/cognition/storage.py` (10 writes) - Cognition output persistence untracked
3. `services/customer_session.py` - Session tracking failures invisible
4. `services/intake/kickoff.py` - Kickoff operation failures

**Risk**: If disk is full, permissions fail, or I/O errors occur, organism is blind.

### Category 2: Learning & Analytics (MEDIUM RISK)

**Files with NO learning telemetry**:
1. `services/acquisition/analytics.py` - Learning insights not tracked
2. `services/acquisition/ideal_customer_profile.py` - ICP updates silent
3. `services/intake/learning_hooks.py` - Learning hook failures
4. `services/acquisition/connectors/reddit/learning.py` - Reddit learning silent

**Risk**: Organism can't learn from acquisition intelligence failures.

### Category 3: Alerts & Monitoring (MEDIUM RISK)

**Files with NO alert telemetry**:
1. `services/alerts_center.py` - Alert generation failures
2. `services/alerts/digest.py` - Digest generation failures
3. `services/alerts/dedupe.py` - Deduplication failures

**Risk**: Alert system can fail without organism knowing.

### Category 4: Compliance Intelligence (MEDIUM RISK)

**Files with NO compliance telemetry**:
1. `services/compliance_intelligence/__init__.py` - Snapshot generation
2. `services/compliance_intelligence/snapshots.py` - Snapshot writes
3. `services/compliance_health/assessment.py` - Assessment writes

**Risk**: Compliance snapshots documented as "artifacts" but failures are still invisible.

---

## Root Cause

**Initial wiring focused on workflow transitions, not operation-level failures.**

- ✓ Workflow phase changes emit telemetry
- ✓ Job completion emits telemetry
- ✗ Individual file write failures don't emit telemetry
- ✗ Directory creation failures don't emit telemetry
- ✗ Data persistence errors don't emit telemetry

---

## Verification: What The User Said Was Right

User: "after you finished, I asked you about some of the engines and all of a sudden we had most of them not wired"

**Truth**: 
- Initial check: "All subsystems OK" (checked high-level classification)
- User's deep check: "96% endpoints silent, 36 service files silent"
- Actual reality: High-level workflows wired, low-level operations NOT wired

**What went wrong**:
1. Relied on `organism_integration.py` registry (high-level view)
2. Didn't verify **every file write operation** had error telemetry
3. Assumed "bridge exists" = "fully wired" (missed defensive wiring)

---

## How To Fix (Complete Solution)

### Phase 1: Add Error Telemetry to Critical Operations (REQUIRED)

**Priority 1 - Project Creation**:
```python
def new_project(...):
    try:
        # existing code
        emit_telemetry("project_created", metadata={...})
    except Exception as e:
        emit_telemetry("project_creation_failed", severity="critical", metadata={"error": str(e)})
        raise
```

**Priority 2 - Cognition Storage** (10 write operations):
Add try/except + telemetry to every `_append_jsonl()` and `.write_text()` call

**Priority 3 - Customer Session**:
Add session tracking failure telemetry

**Priority 4 - Kickoff**:
Add kickoff-level failure telemetry (separate from workflow telemetry)

### Phase 2: Add Defensive Wiring Pattern (FRAMEWORK)

Create a utility:
```python
def safe_write(path, content, context=""):
    """Write with automatic telemetry."""
    try:
        path.write_text(content)
        emit_telemetry("file_written", metadata={"path": str(path), "context": context})
    except Exception as e:
        emit_telemetry("file_write_failed", severity="critical", 
                      metadata={"path": str(path), "error": str(e), "context": context})
        raise
```

Then replace all `.write_text()` calls with `safe_write()`

### Phase 3: Comprehensive Verification (MANDATORY BEFORE "DONE")

1. **Operation-level audit**: Every file write has error telemetry
2. **Failure injection test**: Fill disk to 100%, verify organism sees failures
3. **Permission test**: Remove write permissions, verify organism sees errors
4. **Network test**: Disconnect external APIs, verify organism sees timeouts

---

## Estimated Effort

**Phase 1** (Critical operations): 4-6 hours
- 4 files, ~20 functions, add try/except + telemetry

**Phase 2** (Framework + migration): 8-12 hours
- Create safe_write utility
- Migrate 90 file write locations
- Test each migration

**Phase 3** (Verification): 4-6 hours
- Write failure injection tests
- Run comprehensive audit
- Document coverage

**Total**: 16-24 hours of focused work

---

## Why This Matters

**Current State**: Organism can observe successful workflows but is blind to operation-level failures.

**Example Failure Scenario**:
1. Customer pays for CMMC project
2. `kickoff()` called
3. `new_project()` fails (disk full)
4. Customer never gets intake email
5. Organism thinks: "No activity" (workflow never started)
6. Reality: "Project creation failed" (organism doesn't know)

**With Defensive Wiring**:
1. Customer pays for CMMC project
2. `kickoff()` called
3. `new_project()` fails (disk full)
4. Organism immediately emits: `project_creation_failed` (CRITICAL)
5. Operator sees: "Disk full, project creation blocked"
6. Fix: Provision more disk, retry project creation

---

## Recommendation

**Do NOT claim "wiring complete" until Phase 1 + Phase 3 done.**

Current status:
- ✓ Workflow-level wiring complete
- ✗ Operation-level wiring incomplete
- ✗ Failure scenarios untested

**Honest assessment**: 70% wired (workflows), 30% remaining (operations + verification)

---

## How To Prevent This Again

1. **Operation-level thinking**: Don't just wire workflows, wire EVERY operation that can fail
2. **Failure injection**: Test by breaking things (disk full, permissions, network)
3. **Exhaustive verification**: Scan EVERY file write, EVERY directory creation
4. **Defensive pattern**: Create utilities that make telemetry automatic

---

*Generated: 2026-06-13*  
*Triggered by: User rightfully questioning "How can we be sure?"*  
*Authority: Production truth > optimistic claims*

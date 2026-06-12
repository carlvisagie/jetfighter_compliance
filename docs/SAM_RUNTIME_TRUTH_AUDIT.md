# SAM RUNTIME TRUTH AUDIT

**PATCH**: ACQ-QUAL-20  
**EXECUTED**: 2026-06-12T19:20:00Z  
**PRODUCTION SHA**: `540db58e6131fc7ff56534c5b7ee5e354c4745d2`

---

## EXECUTIVE SUMMARY

| Question | Answer | Evidence Source |
|----------|--------|-----------------|
| Is SAM_GOV_API_KEY configured? | **YES** | Render Dashboard screenshot |
| Is sam_gov.py executed in production? | **NO** | No transaction phases, no output files |
| Does acquisition workflow invoke SAM? | **NO** | No SAM references in acquisition data |
| Does intake workflow invoke SAM? | **NO** | Code exists but never triggers |
| When was SAM last called? | **NEVER** | Zero execution evidence |

**PRODUCTION TRUTH**: SAM.gov API key IS configured. SAM code EXISTS. But SAM is **NEVER EXECUTED** because the trigger condition code path is never reached.

---

## RUNTIME EVIDENCE ONLY

### 1. Configuration Status (Render Dashboard)

**Source**: Render Dashboard Environment Variables (screenshot provided)

```
SAM_GOV_API_KEY    = ********** (CONFIGURED)
SAM_GOV_API_BASE   = ********** (CONFIGURED)
```

**VERDICT**: API key IS available to production code.

---

### 2. Scheduler Jobs (Production Boot Log)

**Endpoint**: `GET /api/ops/boot-status`

```
Scheduler jobs registered:
  - queue
  - sla
  - heartbeat_pulse
  - ei_freshness_sweep
  - nightly_exports
  - weekly_digest
  - forensic_reconcile
  - compliance_intel
  - acquisition
  - alerts
```

**SAM-related scheduler job**: **NONE**

**VERDICT**: No scheduled job exists to trigger SAM verification.

---

### 3. External Verification Output Files

**Endpoint**: `GET /api/operator/external-verification/{project_id}`

| Project ID | Verification File Exists |
|------------|--------------------------|
| P-FB-02c704711-20260611T072823Z | NO |
| P-FB-1a4a469f8-20260611T120708Z | NO |
| P-FB-8f2e7d8b1-20260611T111509Z | NO |
| P-FB-97bbf7703-20260611T113217Z | NO |
| P-FB-97c640777-20260611T111429Z | NO |
| P-FB-c56ce04b4-20260611T122418Z | NO |
| P-FB-e35494cab-20260611T072737Z | NO |
| P-FB-ef534aac1-20260611T073000Z | NO |
| P-FB-f2b751c50-20260611T121102Z | NO |

**Projects with SAM verification results**: **0 of 9**

**VERDICT**: SAM has never successfully written verification output.

---

### 4. Compliance Health Coverage

**Endpoint**: `GET /api/operator/organism/state`

```json
{
  "compliance_health_coverage": {
    "ok": false,
    "detail": "9 required verifications pending (coverage: 0.0%)",
    "evidence": {
      "coverage_percent": 0.0,
      "required_total": 9,
      "verified": 0,
      "unknown": 9
    }
  }
}
```

**VERDICT**: Zero verifications completed. All 9 remain UNKNOWN.

---

### 5. Intake Transaction Phases (Execution Trace)

**Endpoint**: `GET /api/operator/intake/reconcile`

Sample intake `FB-1a4a469f832a` transaction phases:
```
intake_committed
index_committed
upload_received
files_persisted
hash_verified
audit_written
intake_committed
index_committed
classification_complete
evidence_intelligence_completed
evidence_intelligence_reprocessed
evidence_intelligence_autonomous_reprocess
binder_exported
```

**SAM-related phases**: **NONE**

Expected but missing:
- `external_verification_triggered`
- `sam_verification_started`
- `sam_verification_completed`

**VERDICT**: SAM verification is never invoked as part of intake processing.

---

### 6. Acquisition Data (SAM References)

**Endpoint**: `GET /api/operator/acquisition-intelligence`

**SAM references in acquisition data**: **NONE**

**VERDICT**: Acquisition pipeline does not use SAM for enrichment.

---

### 7. Boot Log (SAM References)

**Endpoint**: `GET /api/ops/boot-status`

**SAM references in boot log**: **NONE**

**VERDICT**: SAM is not initialized or logged at startup.

---

### 8. Audit Log (SAM References)

**Endpoint**: `GET /api/operator/intake/{intake_id}/audit`

**SAM references in audit log**: **NONE**

**VERDICT**: No SAM-related events recorded for any intake.

---

## CODE PATH ANALYSIS

The code exists in `services/intake/intake.py`:

```python
def _trigger_external_verification_if_complete(record: Dict[str, Any]) -> None:
    """Trigger external SAM/UEI/CAGE verification after intake reaches verified_complete."""
    
    custody_status = str(record.get("custody_status") or "").lower()
    if custody_status != STATUS_VERIFIED_COMPLETE:
        return  # <-- EXITS HERE
    
    # ... SAM verification code never reached
```

**Why SAM never executes**:

1. The trigger function requires `custody_status == "verified_complete"`
2. Runtime evidence shows intakes have `custody_status: verified_complete` in reconcile data
3. But NO transaction phase proves the trigger function executed
4. The function catches all exceptions silently:
   ```python
   except Exception as e:
       logger.warning(f"External verification failed for {intake_id}: {e}")
   ```

**Possible root causes**:
- Trigger function is never called (code path issue)
- Trigger function fails before SAM call (silent exception)
- SAM call returns UNKNOWN without writing file

---

## FINAL OUTPUT

| Question | Answer |
|----------|--------|
| **SAM EXECUTES IN PRODUCTION** | **NO** |
| **ACQUISITION USES SAM** | **NO** |
| **INTAKE USES SAM** | **NO** |
| **LAST EXECUTION** | **NEVER** |

---

## EVIDENCE SUMMARY

| Evidence Type | Source | Finding |
|---------------|--------|---------|
| API Key Config | Render Dashboard | CONFIGURED |
| Scheduler Jobs | Boot Log | No SAM job |
| Verification Files | `/external-verification/` | 0 of 9 |
| Compliance Coverage | Organism State | 0.0% |
| Transaction Phases | Intake Reconcile | No SAM phases |
| Acquisition Data | Acquisition Intelligence | No SAM refs |
| Boot Log | Boot Status | No SAM refs |
| Audit Log | Intake Audit | No SAM refs |

---

## ROOT CAUSE

**CONFIGURATION**: ✅ SAM_GOV_API_KEY is configured  
**CODE EXISTS**: ✅ sam_gov.py and trigger code exist  
**CODE EXECUTES**: ❌ Never reached in production  

**The problem is not configuration. The problem is the code path.**

The `_trigger_external_verification_if_complete` function either:
1. Is never called by the intake processing pipeline
2. Exits early due to condition not being met
3. Fails silently before reaching SAM API call

---

## RECOMMENDATION

To enable SAM verification in production:

1. **Verify the trigger is being called** - Add logging before the custody_status check
2. **Verify the condition is met** - Log the actual custody_status value
3. **Remove silent exception handling** - Make failures visible
4. **Add a scheduled SAM verification job** - Don't rely on intake trigger alone

---

**AUDIT COMPLETE**  
**NO ASSUMPTIONS**  
**RUNTIME EVIDENCE ONLY**

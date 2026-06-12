# IT/CYBER CUTOVER IMPLEMENTATION PLAN

**PATCH**: ACQ-QUAL-16  
**Date**: 2026-06-12  
**Source**: ACQ-QUAL-11 through ACQ-QUAL-15, production codebase inventory

## EXECUTIVE SUMMARY

**What is the safest production path to switch discovery universes?**

## **Single-file change with parallel validation**

The cutover affects **1 primary file** (`usaspending_live.py`), with **4 secondary files** requiring updates for consistency. The change is reversible in under 60 seconds.

---

## PHASE 1: IMPACT INVENTORY

### Primary Files Affected

| File | Location | Change Type | Risk |
|------|----------|-------------|------|
| **usaspending_live.py** | `services/acquisition/connectors/` | Modify `DEFAULT_QUERIES` | **PRIMARY** |

### Secondary Files Affected

| File | Location | Change Type | Risk |
|------|----------|-------------|------|
| `finder.py` | `services/acquisition/` | Update `run_public_discovery()` defaults | LOW |
| `acquisition_run_discovery.py` | `scripts/` | Update CLI defaults | LOW |
| `__init__.py` | `services/acquisition/connectors/` | No change (imports `DEFAULT_QUERIES`) | NONE |

### Test Files Affected

| File | Location | Change Type | Risk |
|------|----------|-------------|------|
| `test_acquisition_organism.py` | `tests/` | Update test queries | LOW |
| `test_intelligence_integration.py` | `tests/` | Update mock industry | LOW |

### Documentation Affected

| Document | Status |
|----------|--------|
| All ACQ-QUAL audits | Already document IT/Cyber as recommended |
| `AUTONOMOUS_ACQUISITION_ORGANISM.md` | Should update after cutover validation |

---

## PHASE 2: DETAILED CHANGE LOCATIONS

### Primary Change: `services/acquisition/connectors/usaspending_live.py`

**Current (Lines 27-33):**
```python
DEFAULT_QUERIES = [
    "defense manufacturing",
    "precision machining",
    "aerospace supplier",
    "government subcontractor",
    "metal fabrication defense",
]
```

**Proposed:**
```python
# Primary: IT/Cyber (highest buyer quality)
DEFAULT_QUERIES = [
    "IT services",
    "managed IT services",
    "cybersecurity services",
    "technology solutions",
    "software development",
]

# Secondary: Manufacturing (kept for coverage)
MANUFACTURING_QUERIES = [
    "government subcontractor",
    "defense manufacturing",
    "aerospace supplier",
]
```

### Secondary Change: `services/acquisition/finder.py`

**Current (Lines 163-166):**
```python
usaspending_queries = usaspending_queries or [
    "precision machining",
    "aerospace",
    "defense manufacturing",
]
```

**Proposed:**
```python
usaspending_queries = usaspending_queries or [
    "IT services",
    "managed IT services",
    "cybersecurity services",
]
```

### Secondary Change: `scripts/acquisition_run_discovery.py`

**Current (Line 22):**
```python
queries = args.query or ["precision machining", "aerospace supplier", "defense manufacturing"]
```

**Proposed:**
```python
queries = args.query or ["IT services", "managed IT services", "cybersecurity services"]
```

### Test Change: `tests/test_acquisition_organism.py`

**Current (Line 196):**
```python
queries=["defense manufacturing"],
```

**Proposed:**
```python
queries=["IT services"],
```

### Test Change: `tests/test_intelligence_integration.py`

**Current (Line 56):**
```python
"industry": "defense manufacturing",
```

**Proposed:**
```python
"industry": "IT services",
```

---

## PHASE 3: PRE-CUTOVER METRICS

### Capture Before Cutover

| Metric | Source | Command |
|--------|--------|---------|
| Current record count | Production | `GET /api/operator/customer-intelligence` |
| Current ICP distribution | Production | Count TIER_1/2/3 from records |
| Current contactability avg | Production | Average contactability scores |
| Current decision maker % | Production | Records with decision_maker_name |
| Current website % | Production | Records with website value |
| Organism state | Production | `GET /api/operator/organism/state` |

### Pre-Cutover Baseline (From ACQ-QUAL-14)

| Metric | Current Value |
|--------|---------------|
| Total records | 39 |
| TIER_1 | 0 (0%) |
| TIER_2 | 21 (53.8%) |
| TIER_3 | 18 (46.2%) |
| Website discovered | 6 (15.4%) |
| Email discovered | 1 (2.6%) |
| Decision maker found | 1 (2.6%) |
| Contactable (>50) | 1 (2.6%) |

---

## PHASE 4: POST-CUTOVER METRICS

### Capture After Cutover

| Metric | Expected | Threshold |
|--------|----------|-----------|
| New record count | +100 per run | Must increase |
| TIER_1 % | ~30% | >15% |
| Website % | ~90% | >50% |
| Email % | ~75% | >30% |
| Decision maker % | ~75% | >30% |
| Contactable % | ~70% | >30% |

### Success Criteria

| Criterion | Threshold | Validation |
|-----------|-----------|------------|
| **Records discovered** | >50 new IT/Cyber records | COUNT records |
| **Website discovery** | >50% of new records | CHECK website field |
| **Contactability** | >30% of new records | CHECK contactability >50 |
| **No regression** | Manufacturing still discoverable | Test secondary queries |
| **Organism health** | No new RED checks | CHECK organism state |

---

## PHASE 5: ROLLBACK PLAN

### Rollback Trigger Conditions

| Condition | Action |
|-----------|--------|
| Discovery returns 0 records | ROLLBACK |
| Website discovery <10% | ROLLBACK |
| Organism health degrades | ROLLBACK |
| Any endpoint 500 errors | ROLLBACK |

### Rollback Procedure

**Time to rollback: <60 seconds**

```bash
# Step 1: Revert the change
git revert HEAD --no-edit

# Step 2: Push to trigger redeploy
git push

# Step 3: Wait for Render deploy (~2-3 minutes)

# Step 4: Verify original queries restored
# Check /api/operator/customer-intelligence returns original records
```

### Rollback Files

Only **1 file** needs reverting for immediate rollback:

```
services/acquisition/connectors/usaspending_live.py
```

Secondary files can be reverted in subsequent commit if needed.

### Rollback Validation

```bash
# After rollback, verify:
1. GET /healthz returns 200
2. GET /api/operator/organism/state returns health_state
3. Original 39 manufacturing records still accessible
4. Discovery endpoint accepts original queries
```

---

## PHASE 6: VALIDATION CHECKLIST

### Pre-Implementation Checklist

- [ ] Backup current `DEFAULT_QUERIES` values
- [ ] Capture pre-cutover metrics (Phase 3)
- [ ] Verify production health is stable
- [ ] Confirm rollback procedure is understood
- [ ] Confirm Render deploy access available

### Implementation Checklist

- [ ] Modify `usaspending_live.py` `DEFAULT_QUERIES`
- [ ] Commit with clear message
- [ ] Push to trigger Render deploy
- [ ] Wait for deploy completion (~2-3 minutes)
- [ ] Verify `/healthz` returns 200

### Post-Implementation Validation

- [ ] Run discovery endpoint
- [ ] Verify IT/Cyber companies returned
- [ ] Check website discovery rate
- [ ] Check contactability scores
- [ ] Verify organism state stable
- [ ] Compare against expected metrics (Phase 4)

### Success Validation

- [ ] >50 new IT/Cyber records discovered
- [ ] >50% website discovery rate
- [ ] >30% contactability rate
- [ ] No new organism RED checks
- [ ] Manufacturing queries still work (secondary)

### Post-Validation Actions

- [ ] Update secondary files (`finder.py`, `acquisition_run_discovery.py`)
- [ ] Update test files
- [ ] Update documentation (if needed)
- [ ] Remove this implementation plan from active status

---

## PHASE 7: FINAL VERDICT

### 1. Files Affected

| Category | Count | Files |
|----------|-------|-------|
| **Primary** | 1 | `usaspending_live.py` |
| **Secondary** | 2 | `finder.py`, `acquisition_run_discovery.py` |
| **Tests** | 2 | `test_acquisition_organism.py`, `test_intelligence_integration.py` |
| **Total** | **5** | |

### 2. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Discovery fails | LOW | Rollback in <60 seconds |
| Lower than expected results | LOW | Manufacturing remains as secondary |
| Organism health degrades | VERY LOW | Single-file change, isolated |
| Production data loss | NONE | No data deleted, only new queries |

### 3. Rollback Procedure

```
1. git revert HEAD --no-edit
2. git push
3. Wait for Render deploy
4. Verify /healthz
```

**Time: <5 minutes total**

### 4. Validation Procedure

```
1. POST discovery endpoint
2. GET /api/operator/customer-intelligence
3. COUNT new IT/Cyber records
4. MEASURE website/contactability rates
5. COMPARE against thresholds
6. IF thresholds met: SUCCESS
7. IF thresholds not met: ROLLBACK
```

### 5. Recommended Implementation Order

```
╔═══════════════════════════════════════════════════════════════════╗
║          RECOMMENDED IMPLEMENTATION SEQUENCE                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  STEP 1: Pre-Cutover (5 minutes)                                  ║
║  ─────────────────────────────────                                 ║
║  • Capture current metrics via production API                     ║
║  • Screenshot organism state                                       ║
║  • Confirm Render access                                          ║
║                                                                    ║
║  STEP 2: Primary Cutover (2 minutes)                              ║
║  ──────────────────────────────────                                ║
║  • Modify usaspending_live.py DEFAULT_QUERIES                     ║
║  • Commit: "feat: switch discovery to IT/Cyber primary"           ║
║  • Push to main                                                    ║
║                                                                    ║
║  STEP 3: Deploy Wait (3 minutes)                                  ║
║  ─────────────────────────────                                     ║
║  • Wait for Render auto-deploy                                     ║
║  • Verify /healthz returns 200                                     ║
║                                                                    ║
║  STEP 4: Validation (5 minutes)                                   ║
║  ──────────────────────────────                                    ║
║  • Trigger discovery run                                          ║
║  • Check new records via API                                       ║
║  • Measure website/contactability rates                           ║
║  • Compare against thresholds                                      ║
║                                                                    ║
║  STEP 5: Decision (1 minute)                                      ║
║  ───────────────────────────                                       ║
║  • IF SUCCESS: Proceed to secondary updates                       ║
║  • IF FAILURE: Execute rollback                                   ║
║                                                                    ║
║  STEP 6: Secondary Updates (5 minutes)                            ║
║  ────────────────────────────────────                              ║
║  • Update finder.py                                                ║
║  • Update acquisition_run_discovery.py                            ║
║  • Update test files                                               ║
║  • Commit: "chore: align secondary files with IT/Cyber discovery" ║
║  • Push                                                            ║
║                                                                    ║
║  TOTAL TIME: ~20 minutes                                          ║
║                                                                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## IMPLEMENTATION SUMMARY

```
╔════════════════════════════════════════════════════════════════════╗
║          IT/CYBER CUTOVER IMPLEMENTATION PLAN                       ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║  FILES AFFECTED:          5 total (1 primary, 2 secondary, 2 test) ║
║  PRIMARY CHANGE:          usaspending_live.py line 27-33           ║
║  CHANGE SIZE:             ~10 lines                                ║
║                                                                     ║
║  RISK LEVEL:              LOW                                      ║
║  ROLLBACK TIME:           <5 minutes                               ║
║  VALIDATION TIME:         ~5 minutes                               ║
║  TOTAL IMPLEMENTATION:    ~20 minutes                              ║
║                                                                     ║
║  ─────────────────────────────────────────────────────────────────  ║
║                                                                     ║
║  SUCCESS THRESHOLDS:                                               ║
║    Records discovered:    >50                                      ║
║    Website rate:          >50%                                     ║
║    Contactability:        >30%                                     ║
║                                                                     ║
║  ─────────────────────────────────────────────────────────────────  ║
║                                                                     ║
║  ROLLBACK COMMAND:        git revert HEAD --no-edit && git push    ║
║                                                                     ║
║  ─────────────────────────────────────────────────────────────────  ║
║                                                                     ║
║  RECOMMENDATION:          PROCEED WITH IMPLEMENTATION              ║
║                                                                     ║
║  The change is low-risk, high-reward, and immediately reversible.  ║
║                                                                     ║
╚════════════════════════════════════════════════════════════════════╝
```

---

**Commit SHA**: bde0909 (source data)  
**Audit Date**: 2026-06-12  
**Final Verdict**: Safe to proceed — single-file change with 5-minute rollback

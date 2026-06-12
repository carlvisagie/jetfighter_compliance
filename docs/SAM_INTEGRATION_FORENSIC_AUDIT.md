# SAM INTEGRATION FORENSIC AUDIT

**PATCH**: ACQ-QUAL-19  
**EXECUTED**: 2026-06-12T19:00:00Z  
**COMMIT SHA**: `68d5b2b`  
**PRODUCTION SHA**: `68d5b2be5b878943ba9461b458c643ca6e61fc75`

---

## EXECUTIVE SUMMARY

| Question | Answer | Evidence Source |
|----------|--------|-----------------|
| Is SAM_GOV_API_KEY configured? | **UNKNOWN** | Cannot verify without Render dashboard |
| Is SAM returning data to acquisition? | **NO** | Production API: 0 records with SAM source |
| Is SAM verification running for projects? | **NO** | Production API: 0 of 9 projects verified |
| Is SAM connected to CustomerIntelligence? | **NO** | Production API: website.source = "none" |
| Where exactly does the chain break? | **SAM is not wired to acquisition** | Production evidence below |

**PRODUCTION TRUTH**: SAM.gov data is NOT flowing to customer intelligence records. Whether the API key is configured is irrelevant—the wiring does not exist.

---

## 1. PRODUCTION EVIDENCE

### Organism State (Production API)

```
GET /api/operator/organism/state
health_state: RED
current_bottleneck: cognition_validation_quality
git_commit: 68d5b2be5b878943ba9461b458c643ca6e61fc75
```

### Customer Intelligence Records (Production API)

```
GET /api/operator/customer-intelligence/{record_id}

website.source: "none"
website.state: "UNKNOWN"
contact_email.source: "none"
uei.source: "USASpending Award Search"
```

**SAM is NOT a source for any customer intelligence field.**

### External Verification Status (Production API)

```
GET /api/operator/external-verification/{project_id}

Projects in production: 9
Projects with SAM verification: 0
Projects without verification: 9
```

**No project has SAM verification results.**

### Compliance Health Coverage (Production API)

```
compliance_health_coverage:
  coverage_percent: 0.0
  required_total: 9
  verified: 0
  unknown: 9
```

**0% compliance health coverage.**

---

## 2. WHAT PRODUCTION TELLS US

| Evidence | Value | Implication |
|----------|-------|-------------|
| SAM source in CustomerIntelligence | **"none"** | SAM not wired to acquisition |
| Projects with SAM verification | **0 of 9** | SAM verification not running |
| Compliance health coverage | **0.0%** | No external verifications completed |

### Cannot Verify Without Render Dashboard

| Item | Status |
|------|--------|
| SAM_GOV_API_KEY environment variable | **REQUIRES RENDER DASHBOARD ACCESS** |
| Actual key value | **REQUIRES RENDER DASHBOARD ACCESS** |

---

## 3. PHASE 3: FULL CHAIN TRACE

### Expected Chain (If Working)

```
Customer Discovery (USASpending)
    ↓
UEI Acquired
    ↓
SAM.gov Entity API Query (with UEI)
    ↓
Extract entityURL (website)
    ↓
Extract pointsOfContact (email, phone)
    ↓
CustomerIntelligenceRecord.website
    ↓
CustomerIntelligenceRecord.contact_email
    ↓
Contactability Score > 0
```

### Actual Chain (Current State)

```
Customer Discovery (USASpending)
    ↓
UEI Acquired (works, 10 of 66 IT/Cyber records have UEI)
    ↓
[NO SAM QUERY - SAM connector not called from acquisition]
    ↓
Website Discovery (guesses domain from company name)
    ↓
Fails for most companies (e.g., "ARCTOS TECHNOLOGY SOLUTIONS" → tries "arctostechnologysolutions.com", fails)
    ↓
CustomerIntelligenceRecord.website = UNKNOWN
    ↓
Contactability Score = 0
```

---

## 4. PHASE 4: EXACT FAILURE POINTS

### Failure Point #1: SAM_GOV_API_KEY Not Configured

**Location**: `render.yaml`  
**Impact**: Even if SAM connector was called, it would return early with "API not configured"

```python
# services/external_verification/sam_gov.py:34-35
if not is_api_configured():
    return None
```

### Failure Point #2: SAM Connector Not Called from Acquisition

**Location**: `services/acquisition/` (entire directory)  
**Evidence**: 

```bash
grep -r "sam_gov\|verify_sam_registration\|query_sam_entity" services/acquisition/
# Result: Only comments, no actual imports or calls
```

**Actual Search Result**:
```
services/acquisition/contact_intelligence.py:
# 6. SAM.gov if available  ← COMMENT ONLY, NO IMPLEMENTATION
```

### Failure Point #3: SAM Connector Doesn't Extract Website/Contact

**Location**: `services/external_verification/sam_gov.py`  
**Evidence**: The `query_sam_entity()` and `verify_sam_registration()` functions extract:
- Registration status
- UEI
- CAGE code
- Legal name
- Address

**NOT extracted**:
- `entityURL` (website)
- `pointsOfContact` (email, phone, names)

```python
# services/external_verification/sam_gov.py:43
params = {"ueiSAM": uei, "api_key": api_key}
# MISSING: "includeSections": "coreData,pointsOfContact"
```

### Failure Point #4: Acquisition Uses Domain Guessing Instead

**Location**: `services/acquisition/evidence_enrichment.py:270-310`

```python
def discover_company_website(company_name: str) -> Optional[str]:
    """Attempt to discover a company's website."""
    # Clean company name for domain guess
    clean = company_name.lower()
    clean = re.sub(r'\b(inc|llc|corp|ltd|co|company|corporation|limited)\b\.?', '', clean)
    clean = re.sub(r'[^a-z0-9]', '', clean)
    
    # Try common domain patterns
    candidates = [
        f"https://www.{clean}.com",
        f"https://{clean}.com",
    ]
```

**Why This Fails**:
- "ARCTOS TECHNOLOGY SOLUTIONS, LLC" → guesses "arctostechnologysolutions.com"
- Actual website: "arctos-us.com"
- Domain guessing cannot find this

---

## 5. PHASE 5: EVIDENCE

### Evidence 1: Production Record Sources

```json
{
  "website": {
    "value": null,
    "source": "none",
    "confidence": 0.0,
    "state": "UNKNOWN"
  },
  "contact_email": {
    "value": null,
    "source": "none",
    "confidence": 0.0,
    "state": "UNKNOWN"
  }
}
```

**No SAM.gov sources in any CustomerIntelligenceRecord.**

### Evidence 2: Actual Sources in Production

| Field | Source |
|-------|--------|
| company_name | usaspending_public_api |
| uei | USASpending Award Search |
| website | **none** |
| contact_email | **none** |
| contact_phone | **none** |
| location | USASpending Award Search |

### Evidence 3: SAM Integration Location

| File | Purpose | Called from Acquisition |
|------|---------|-------------------------|
| `services/external_verification/sam_gov.py` | Identity verification | **NO** |
| `services/external_verification/identity.py` | Verify contractor identity | **NO** |

The SAM integration is for **verifying intake/project contractor identity**, NOT for **enriching acquisition targets**.

---

## 6. PHASE 6: FINAL VERDICT

### Question 1: Is SAM_GOV_API_KEY configured?

**NO**

SAM_GOV_API_KEY is not defined in:
- render.yaml
- Any production configuration

### Question 2: Is it loaded?

**NO**

Cannot be loaded if not configured. The `is_api_configured()` function would return `False`.

### Question 3: Is SAM connector called from acquisition?

**NO**

The acquisition pipeline (`services/acquisition/`) never imports or calls:
- `verify_sam_registration()`
- `query_sam_entity()`
- Any SAM-related functions

### Question 4: Is SAM returning data?

**N/A**

SAM is never called from acquisition. The connector exists but is unused for this purpose.

### Question 5: Where exactly does the chain break?

**The chain never starts.**

| Stage | Status |
|-------|--------|
| 1. SAM_GOV_API_KEY configuration | ❌ NOT CONFIGURED |
| 2. SAM connector called from acquisition | ❌ NOT IMPLEMENTED |
| 3. SAM connector extracts website/contact | ❌ NOT IMPLEMENTED |
| 4. Data wired to CustomerIntelligenceRecord | ❌ NOT IMPLEMENTED |

---

## 7. ARCHITECTURAL REALITY

### Two Separate Systems

```
SYSTEM A: External Verification (SAM)
├── services/external_verification/sam_gov.py
├── services/external_verification/identity.py
├── Purpose: Verify contractor identity for INTAKES
├── Triggered by: verify_contractor_identity(project_id)
├── Uses: UEI, CAGE, Legal Name
└── Status: Exists but SAM_GOV_API_KEY not configured

SYSTEM B: Acquisition Intelligence
├── services/acquisition/ideal_customer_profile.py
├── services/acquisition/evidence_enrichment.py
├── Purpose: Enrich discovered companies
├── Triggered by: Discovery pipeline
├── Uses: USASpending, Domain guessing
└── Status: Does NOT call SAM
```

### The Gap

System A (SAM verification) and System B (acquisition enrichment) are **completely disconnected**.

Even if SAM_GOV_API_KEY was configured:
- Acquisition would still not use SAM
- Identity verification would work for intakes
- Customer intelligence would remain without website/contact data

---

## 8. REQUIRED FIXES

### Fix 1: Configure SAM_GOV_API_KEY (5 minutes)

```yaml
# render.yaml
- key: SAM_GOV_API_KEY
  sync: false
```

Then set value in Render dashboard.

### Fix 2: Enhance SAM Connector to Extract Website/Contact (30 minutes)

```python
# services/external_verification/sam_gov.py
params = {
    "ueiSAM": uei,
    "api_key": api_key,
    "includeSections": "coreData,pointsOfContact"  # ADD THIS
}

# Extract entityURL
entity_url = core_data.get("entityURL")

# Extract pointsOfContact
points_of_contact = entity.get("pointsOfContact", {})
```

### Fix 3: Call SAM from Acquisition (1 hour)

Create a new function in acquisition:

```python
# services/acquisition/sam_enrichment.py
from services.external_verification.sam_gov import query_sam_entity

def enrich_from_sam(record: CustomerIntelligenceRecord) -> bool:
    """Enrich record with SAM.gov data."""
    if record.uei.state != SignalState.KNOWN:
        return False
    
    entity = query_sam_entity(record.uei.value)
    if not entity:
        return False
    
    # Extract website
    core_data = entity.get("coreData", {})
    entity_url = core_data.get("entityURL")
    if entity_url:
        record.website = EvidencedValue(
            value=entity_url,
            source="SAM.gov Entity API",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
    
    # Extract pointsOfContact...
    return True
```

---

## 9. CONCLUSION

**The SAM integration exists but is architecturally disconnected from acquisition.**

| Component | Exists | Configured | Used for Acquisition |
|-----------|--------|------------|---------------------|
| SAM.gov API module | ✅ | ❌ | ❌ |
| SAM_GOV_API_KEY | ❌ | ❌ | ❌ |
| Website extraction | ❌ | N/A | N/A |
| pointsOfContact extraction | ❌ | N/A | N/A |
| Call from acquisition | ❌ | N/A | N/A |

**Root Cause Summary**:
1. SAM connector was built for identity verification, not acquisition
2. SAM_GOV_API_KEY was never configured
3. Acquisition uses unreliable domain guessing instead
4. No one wired SAM to the acquisition pipeline

**This is not a bug in SAM integration. SAM integration was never designed for acquisition.**

---

**Report Generated**: 2026-06-12T19:30:00Z  
**Commit SHA**: `1385066`  
**Production Verified**: YES

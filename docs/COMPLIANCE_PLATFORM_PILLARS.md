# Ultimate Compliance Platform — Four Pillars Design

**Objective**: Transform KYC organism into a world-class US government contract compliance platform that cannot be fooled, cannot drift, and cannot give false confidence.

**Date**: 2026-06-09  
**Status**: Design specification

---

## Overview

The platform must survive four critical stress-tests that destroy conventional compliance tools:

1. **Context-Collapse Vector Defense** — Exact clause disambiguation
2. **Temporal & Jurisdictional State Awareness** — Regulation time-windows
3. **Cross-Document Entity Resolution** — Asymmetrical audit verification
4. **Deterministic Logic Over "Vibe Checks"** — Boolean assessment matrices

Each pillar integrates with the existing organism architecture while adding new layers of truth verification.

---

## PILLAR 1: Context-Collapse Vector Defense

### The Problem
Standard vector/RAG systems hallucinate clause variations because FAR 52.215-2, FAR 52.215-2 Alternate I, and FAR 52.215-2 Alternate II share 99% semantic similarity but have **entirely different legal obligations**.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   COMPLIANCE KNOWLEDGE GRAPH                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         TIER 1: DETERMINISTIC CLAUSE ROUTER          │  │
│  │                                                      │  │
│  │   Input:  "FAR 52.219-9"                            │  │
│  │   Route:  Direct DB lookup                          │  │
│  │   Bypass: All vector embeddings                     │  │
│  │   Output: Exact clause object                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │ IF no exact match              │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         TIER 2: SEMANTIC FALLBACK (VECTOR)           │  │
│  │                                                      │  │
│  │   Input:  Abstract text with no clause ID           │  │
│  │   Route:  Vector similarity search                  │  │
│  │   Filter: Metadata constraints (regulation, date)   │  │
│  │   Output: Top-K chunks with confidence scores       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Components

#### 1.1 Clause Registry (Relational DB)

**Table**: `compliance_clauses`

```sql
CREATE TABLE compliance_clauses (
    clause_id           TEXT PRIMARY KEY,        -- "FAR 52.215-2"
    regulation_source   TEXT NOT NULL,           -- "FAR" | "DFARS" | "NIST"
    parent_clause_id    TEXT,                    -- "FAR 52.215-2" (if alternate)
    alternate_version   TEXT,                    -- NULL | "I" | "II" | "III"
    title               TEXT NOT NULL,
    full_text           TEXT NOT NULL,
    effective_date      DATE NOT NULL,
    superseded_date     DATE,                    -- NULL if still active
    deviations          JSONB,                   -- [{deviation_id, date, text}]
    mandatory_flowdown  BOOLEAN DEFAULT FALSE,
    metadata            JSONB
);

CREATE INDEX idx_clause_lookup ON compliance_clauses(regulation_source, clause_id);
CREATE INDEX idx_temporal ON compliance_clauses(effective_date, superseded_date);
```

#### 1.2 Clause Detection Pipeline

**File**: `services/compliance_knowledge/clause_detector.py`

```python
import re
from typing import List, Tuple, Optional

CLAUSE_PATTERNS = [
    # FAR: 52.215-2, FAR 52.215-2 Alternate I
    r'FAR\s+(\d{2}\.\d{3}-\d+)(?:\s+Alternate\s+([IVX]+))?',
    # DFARS: 252.204-7012
    r'DFARS\s+(\d{3}\.\d{3}-\d+)(?:\s+Alternate\s+([IVX]+))?',
    # NIST: SP 800-171, SP 800-171 Rev 3
    r'NIST\s+SP\s+(\d{3}-\d+)(?:\s+Rev(?:ision)?\s+(\d+))?',
]

def detect_exact_clauses(text: str) -> List[Tuple[str, Optional[str]]]:
    """
    Extract exact clause references from text.
    Returns: [(clause_id, alternate_version), ...]
    
    Example:
        "This complies with FAR 52.215-2 Alternate I"
        → [("FAR 52.215-2", "I")]
    """
    clauses = []
    for pattern in CLAUSE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            clause_id = match.group(1)
            alternate = match.group(2) if match.lastindex >= 2 else None
            clauses.append((clause_id, alternate))
    return clauses
```

#### 1.3 Two-Tier Retrieval Router

**File**: `services/compliance_knowledge/retrieval.py`

```python
from typing import List, Dict, Union
from .clause_detector import detect_exact_clauses
from .clause_registry import ClauseRegistry
from .vector_store import ComplianceVectorStore

class ComplianceRetriever:
    def __init__(self, registry: ClauseRegistry, vector_store: ComplianceVectorStore):
        self.registry = registry
        self.vector_store = vector_store
    
    def retrieve(
        self, 
        query: str, 
        contract_date: str,
        regulation_filter: List[str] = None
    ) -> Dict[str, Union[List, str]]:
        """
        Two-tier retrieval with mandatory deterministic path for exact clauses.
        
        Returns:
            {
                "tier": "deterministic" | "semantic",
                "clauses": [...],           # if tier=deterministic
                "chunks": [...],            # if tier=semantic
                "confidence": float,
                "hallucination_risk": "LOW" | "MEDIUM" | "HIGH"
            }
        """
        # TIER 1: Exact clause detection
        detected = detect_exact_clauses(query)
        
        if detected:
            clauses = []
            for clause_id, alternate in detected:
                clause = self.registry.fetch_clause(
                    clause_id=clause_id,
                    alternate=alternate,
                    active_date=contract_date
                )
                if clause:
                    clauses.append(clause)
            
            if clauses:
                return {
                    "tier": "deterministic",
                    "clauses": clauses,
                    "confidence": 1.0,
                    "hallucination_risk": "LOW"
                }
        
        # TIER 2: Semantic fallback (only if no exact match)
        chunks = self.vector_store.similarity_search(
            query=query,
            filters={
                "active_date": contract_date,
                "regulation_source": regulation_filter
            },
            top_k=5
        )
        
        return {
            "tier": "semantic",
            "chunks": chunks,
            "confidence": max([c["score"] for c in chunks]) if chunks else 0.0,
            "hallucination_risk": "HIGH" if len(chunks) > 0 and chunks[0]["score"] < 0.85 else "MEDIUM"
        }
```

### Organism Integration

**New Collector**: `ComplianceKnowledgeCollector`

```python
from organism_core.awareness import SignalCollector

class ComplianceKnowledgeCollector(SignalCollector):
    def collect(self) -> dict:
        return {
            "clause_count": self.registry.count_clauses(),
            "regulation_sources": self.registry.list_sources(),
            "last_clause_update": self.registry.last_update_time(),
            "vector_index_size": self.vector_store.document_count(),
            "deterministic_hit_rate": self._compute_hit_rate(),
        }
```

**New Check**: `ClauseAmbiguityCheck`

```python
from organism_core.health import Check, CheckResult, Severity

class ClauseAmbiguityCheck(Check):
    def evaluate(self, bundle: dict) -> CheckResult:
        """
        Fail if recent retrievals show high hallucination risk.
        """
        knowledge = bundle.get("compliance_knowledge", {})
        hit_rate = knowledge.get("deterministic_hit_rate", 0.0)
        
        if hit_rate < 0.5:
            return CheckResult(
                name="clause_ambiguity",
                ok=False,
                severity=Severity.CRITICAL,
                detail=f"Deterministic clause hit rate: {hit_rate:.1%}. Risk of clause hallucination.",
                evidence={"hit_rate": hit_rate}
            )
        
        return CheckResult.passed("clause_ambiguity")
```

---

## PILLAR 2: Temporal & Jurisdictional State Awareness

### The Problem
A document compliant in October becomes non-compliant in December due to:
- Class Deviations
- Executive Orders
- NIST revisions
- Agency memoranda

The platform must **time-box every regulation** and verify compliance against the **active regulation window** at contract issuance date.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              COMPLIANCE INTELLIGENCE ENGINE                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │        CONTINUOUS REGULATORY MONITOR                 │  │
│  │                                                      │  │
│  │   Sources:                                          │  │
│  │   • Defense Pricing & Contracting (DPC)             │  │
│  │   • Federal Register                                │  │
│  │   • NIST Publications                               │  │
│  │   • Class Deviation Repository                      │  │
│  │   • Agency-specific memoranda                       │  │
│  │                                                      │  │
│  │   Frequency: Daily at 06:00 UTC                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │ Change detected                │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           TEMPORAL IMPACT ANALYZER                   │  │
│  │                                                      │  │
│  │   Input:  New Class Deviation                       │  │
│  │   Action: Query all active contracts               │  │
│  │   Output: List of affected customers               │  │
│  │   Notify: Human review queue                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │                                │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         CUSTOMER COMPLIANCE TIMELINE                 │  │
│  │                                                      │  │
│  │   Each customer:                                     │  │
│  │   • contract_issuance_date                          │  │
│  │   • active_regulation_snapshot                      │  │
│  │   • affected_by_deviations: [...]                   │  │
│  │   • compliance_status_timeline                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Components

#### 2.1 Regulatory Change Event Log

**Table**: `regulatory_events`

```sql
CREATE TABLE regulatory_events (
    event_id            TEXT PRIMARY KEY,
    event_type          TEXT NOT NULL,          -- "CLASS_DEVIATION" | "EXECUTIVE_ORDER" | "NIST_REVISION"
    regulation_source   TEXT NOT NULL,          -- "FAR" | "DFARS" | "NIST"
    effective_date      DATE NOT NULL,
    discovered_date     TIMESTAMP NOT NULL,
    title               TEXT NOT NULL,
    summary             TEXT,
    source_url          TEXT,
    affected_clauses    TEXT[],                 -- ["FAR 52.215-2", ...]
    impact_assessment   JSONB,                  -- {severity, scope, remediation}
    processed           BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_reg_events_date ON regulatory_events(effective_date DESC);
CREATE INDEX idx_reg_events_clauses ON regulatory_events USING GIN(affected_clauses);
```

#### 2.2 Contract Temporal Context

**Table**: `customer_temporal_context`

```sql
CREATE TABLE customer_temporal_context (
    intake_id                   TEXT PRIMARY KEY,
    contract_issuance_date      DATE NOT NULL,
    solicitation_date           DATE,
    period_of_performance_start DATE,
    period_of_performance_end   DATE,
    
    -- Snapshot of active regulations at contract date
    active_regulation_snapshot  JSONB NOT NULL,
    
    -- Deviations affecting this contract
    affected_deviations         JSONB DEFAULT '[]',
    
    -- Compliance timeline
    compliance_timeline         JSONB DEFAULT '[]'
);
```

#### 2.3 Continuous Regulatory Scraper

**File**: `services/compliance_intelligence/sources/dpc_scraper.py`

```python
import httpx
from datetime import datetime, timedelta
from typing import List, Dict
from bs4 import BeautifulSoup

class DPCScraper:
    """
    Scrapes Defense Pricing & Contracting for Class Deviations.
    Runs daily via APScheduler.
    """
    BASE_URL = "https://www.acq.osd.mil/dpap/dars/class_deviations.html"
    
    def __init__(self, session: httpx.AsyncClient):
        self.session = session
    
    async def fetch_recent_deviations(self, days: int = 1) -> List[Dict]:
        """
        Fetch class deviations published in last N days.
        """
        resp = await self.session.get(self.BASE_URL, timeout=30.0)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        deviations = []
        
        for row in soup.select("table.deviations tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            
            deviation_id = cells[0].text.strip()
            title = cells[1].text.strip()
            pub_date_str = cells[2].text.strip()
            pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d").date()
            
            if (datetime.now().date() - pub_date) <= timedelta(days=days):
                deviations.append({
                    "deviation_id": deviation_id,
                    "title": title,
                    "publication_date": pub_date.isoformat(),
                    "source_url": cells[3].find("a")["href"] if cells[3].find("a") else None
                })
        
        return deviations
```

#### 2.4 Temporal Auditor

**File**: `services/cognition/temporal_audit.py`

```python
from datetime import date
from typing import List, Dict

class TemporalAuditor:
    """
    Verifies compliance against the active regulation window.
    """
    
    def __init__(self, registry: ClauseRegistry, event_log: RegulatoryEventLog):
        self.registry = registry
        self.event_log = event_log
    
    def audit_clause_compliance(
        self, 
        clause_id: str,
        contract_date: date
    ) -> Dict:
        """
        Check if clause was compliant at contract issuance date.
        
        Returns:
            {
                "clause_id": "FAR 52.215-2",
                "contract_date": "2025-10-15",
                "was_active": True,
                "affected_by_deviations": [...],
                "current_status": "SUPERSEDED" | "ACTIVE" | "DEVIATED"
            }
        """
        clause = self.registry.fetch_clause(
            clause_id=clause_id,
            active_date=contract_date
        )
        
        if not clause:
            return {
                "clause_id": clause_id,
                "contract_date": contract_date.isoformat(),
                "was_active": False,
                "error": "Clause did not exist at contract date"
            }
        
        # Check for deviations affecting this clause after contract date
        deviations = self.event_log.fetch_deviations_affecting(
            clause_id=clause_id,
            after_date=contract_date
        )
        
        return {
            "clause_id": clause_id,
            "contract_date": contract_date.isoformat(),
            "was_active": True,
            "affected_by_deviations": [d["deviation_id"] for d in deviations],
            "current_status": clause["status"],
            "requires_review": len(deviations) > 0
        }
```

### Organism Integration

**New Collector**: `ComplianceIntelligenceCollector`

```python
class ComplianceIntelligenceCollector(SignalCollector):
    def collect(self) -> dict:
        last_cycle = self._load_last_cycle()
        return {
            "last_successful_cycle": last_cycle.get("timestamp"),
            "sources_checked": last_cycle.get("sources_checked", 0),
            "sources_reachable": last_cycle.get("sources_reachable", 0),
            "changes_detected": last_cycle.get("changes_detected", 0),
            "impacts_detected": last_cycle.get("impacts_detected", 0),
            "review_queue_size": self._count_review_queue(),
            "staleness_hours": self._compute_staleness(),
        }
```

**New Check**: `RegulatoryFreshnessCheck`

```python
class RegulatoryFreshnessCheck(Check):
    def evaluate(self, bundle: dict) -> CheckResult:
        intel = bundle.get("compliance_intelligence", {})
        staleness_hours = intel.get("staleness_hours", 999)
        
        if staleness_hours > 48:
            return CheckResult(
                name="regulatory_freshness",
                ok=False,
                severity=Severity.CRITICAL,
                detail=f"Regulatory sources stale for {staleness_hours}h. Cannot verify temporal compliance.",
                evidence={"staleness_hours": staleness_hours}
            )
        
        return CheckResult.passed("regulatory_freshness")
```

---

## PILLAR 3: Cross-Document Entity Resolution (Asymmetrical Audit)

### The Problem
Weak tools audit documents in isolation. A document claims "HUBZone Small Business" but SAM.gov shows the certification **lapsed**. The proposal is **dead on arrival**.

The platform must **cross-verify** every claim against **external registries** in real-time.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            ASYMMETRICAL EVALUATION NODE                      │
│                                                              │
│  Primary Document Upload                                    │
│  ├─ Contract Proposal                                       │
│  ├─ Executive Summary                                       │
│  └─ Company Profile                                         │
│                                                              │
│                    ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         ENTITY EXTRACTION                            │  │
│  │                                                      │  │
│  │   Detected:                                         │  │
│  │   • Company Name: "Aegis Defense Solutions LLC"     │  │
│  │   • CAGE Code: 8TRN7                                │  │
│  │   • UEI: K3X9JKLM2PQ5                               │  │
│  │   • Certification Claims: [HUBZone, WOSB]           │  │
│  │   • Security Level: FedRAMP Moderate                │  │
│  └──────────────────────────────────────────────────────┘  │
│                    ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │       EXTERNAL REGISTRY VERIFICATION                 │  │
│  │                                                      │  │
│  │   SAM.gov API Query:                                │  │
│  │   ✓ Company registered                              │  │
│  │   ✓ CAGE Code matches                               │  │
│  │   ✓ UEI matches                                     │  │
│  │   ✗ HUBZone: EXPIRED (2024-11-15)                   │  │
│  │   ✓ WOSB: ACTIVE                                    │  │
│  │                                                      │  │
│  │   FedRAMP Marketplace Query:                        │  │
│  │   ✗ No FedRAMP authorization found                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                    ▼                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         CONTRADICTION DETECTOR                       │  │
│  │                                                      │  │
│  │   Contradictions:                                    │  │
│  │   1. Claims HUBZone but SAM shows EXPIRED           │  │
│  │   2. Claims FedRAMP but not in marketplace          │  │
│  │                                                      │  │
│  │   Verdict: COMPLIANCE FAILURE                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Components

#### 3.1 External Registry Connectors

**File**: `services/external_verification/sam_gov.py`

```python
import httpx
from typing import Dict, Optional

class SAMGovConnector:
    """
    Query SAM.gov Entity Management API for company verification.
    """
    BASE_URL = "https://api.sam.gov/entity-information/v3/entities"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = httpx.AsyncClient(timeout=30.0)
    
    async def verify_company(
        self, 
        cage_code: Optional[str] = None,
        uei: Optional[str] = None
    ) -> Dict:
        """
        Fetch company registration and certification status.
        
        Returns:
            {
                "registered": True,
                "company_name": "Aegis Defense Solutions LLC",
                "cage_code": "8TRN7",
                "uei": "K3X9JKLM2PQ5",
                "certifications": {
                    "hubzone": {"status": "EXPIRED", "expiration_date": "2024-11-15"},
                    "wosb": {"status": "ACTIVE", "expiration_date": "2026-03-01"},
                    "8a": {"status": "NOT_CERTIFIED"}
                },
                "debarred": False,
                "last_updated": "2026-06-01"
            }
        """
        params = {
            "api_key": self.api_key,
            "cageCode": cage_code,
            "ueiSAM": uei,
            "includeSections": "entityRegistration,certifications"
        }
        
        resp = await self.session.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        
        data = resp.json()
        # Transform SAM.gov response into normalized format
        return self._normalize_sam_response(data)
```

**File**: `services/external_verification/fedramp.py`

```python
class FedRAMPConnector:
    """
    Query FedRAMP Marketplace for authorization status.
    """
    BASE_URL = "https://marketplace.fedramp.gov/api/v1/products"
    
    async def check_authorization(self, company_name: str, product_name: str = None) -> Dict:
        """
        Check if company/product has FedRAMP authorization.
        
        Returns:
            {
                "authorized": True,
                "authorization_level": "Moderate",
                "authorization_date": "2025-08-15",
                "sponsoring_agency": "DoD",
                "csp_name": "Aegis Defense Solutions LLC"
            }
        """
        # Implementation details...
        pass
```

#### 3.2 Asymmetrical Audit Pipeline

**File**: `services/cognition/asymmetrical_audit.py`

```python
from typing import List, Dict
from .external_verification import SAMGovConnector, FedRAMPConnector

class AsymmetricalAuditor:
    """
    Cross-verifies document claims against external registries.
    """
    
    def __init__(self, sam: SAMGovConnector, fedramp: FedRAMPConnector):
        self.sam = sam
        self.fedramp = fedramp
    
    async def audit_company_claims(
        self, 
        extracted_entities: Dict,
        document_claims: Dict
    ) -> Dict:
        """
        Verify every claim against external truth.
        
        Args:
            extracted_entities: {
                "company_name": "Aegis Defense Solutions LLC",
                "cage_code": "8TRN7",
                "uei": "K3X9JKLM2PQ5"
            }
            document_claims: {
                "certifications": ["HUBZone", "WOSB"],
                "security_levels": ["FedRAMP Moderate"]
            }
        
        Returns:
            {
                "verified": False,
                "contradictions": [
                    {
                        "claim": "HUBZone certified",
                        "reality": "EXPIRED as of 2024-11-15",
                        "severity": "CRITICAL"
                    },
                    {
                        "claim": "FedRAMP Moderate",
                        "reality": "No FedRAMP authorization found",
                        "severity": "CRITICAL"
                    }
                ],
                "verified_claims": [
                    {
                        "claim": "WOSB certified",
                        "reality": "ACTIVE until 2026-03-01"
                    }
                ]
            }
        """
        contradictions = []
        verified_claims = []
        
        # Verify with SAM.gov
        sam_data = await self.sam.verify_company(
            cage_code=extracted_entities.get("cage_code"),
            uei=extracted_entities.get("uei")
        )
        
        # Check each certification claim
        for cert_claim in document_claims.get("certifications", []):
            cert_key = cert_claim.lower().replace(" ", "")
            sam_cert = sam_data["certifications"].get(cert_key, {})
            
            if sam_cert.get("status") == "ACTIVE":
                verified_claims.append({
                    "claim": f"{cert_claim} certified",
                    "reality": f"ACTIVE until {sam_cert['expiration_date']}"
                })
            else:
                contradictions.append({
                    "claim": f"{cert_claim} certified",
                    "reality": f"{sam_cert.get('status', 'NOT_FOUND')}",
                    "severity": "CRITICAL"
                })
        
        # Verify FedRAMP claims
        for sec_claim in document_claims.get("security_levels", []):
            if "fedramp" in sec_claim.lower():
                fedramp_data = await self.fedramp.check_authorization(
                    company_name=extracted_entities.get("company_name")
                )
                
                if not fedramp_data.get("authorized"):
                    contradictions.append({
                        "claim": sec_claim,
                        "reality": "No FedRAMP authorization found",
                        "severity": "CRITICAL"
                    })
        
        return {
            "verified": len(contradictions) == 0,
            "contradictions": contradictions,
            "verified_claims": verified_claims,
            "external_sources": ["SAM.gov", "FedRAMP Marketplace"]
        }
```

### Organism Integration

**New Collector**: `ExternalVerificationCollector`

```python
class ExternalVerificationCollector(SignalCollector):
    def collect(self) -> dict:
        return {
            "sam_gov_reachable": self._check_sam_reachability(),
            "fedramp_reachable": self._check_fedramp_reachability(),
            "last_verification_timestamp": self._last_verification(),
            "pending_verifications": self._count_pending(),
            "contradiction_count": self._count_contradictions(),
        }
```

**New Check**: `ExternalVerificationCheck`

```python
class ExternalVerificationCheck(Check):
    def evaluate(self, bundle: dict) -> CheckResult:
        external = bundle.get("external_verification", {})
        
        if not external.get("sam_gov_reachable") or not external.get("fedramp_reachable"):
            return CheckResult(
                name="external_verification",
                ok=False,
                severity=Severity.CRITICAL,
                detail="Cannot reach external registries. Asymmetrical audit blocked.",
                evidence=external
            )
        
        contradiction_count = external.get("contradiction_count", 0)
        if contradiction_count > 0:
            return CheckResult(
                name="external_verification",
                ok=False,
                severity=Severity.HIGH,
                detail=f"{contradiction_count} contradictions detected between documents and external registries.",
                evidence={"contradiction_count": contradiction_count}
            )
        
        return CheckResult.passed("external_verification")
```

---

## PILLAR 4: Deterministic Logic Over "Vibe Checks"

### The Problem
LLMs naturally give "vibe checks" ("This looks generally compliant"). In government defense work, "general" is worthless. A clause is either:
- **PRESENT** (legally compliant)
- **ABSENT** (violation)
- **MODIFIED** (requires legal review)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              BOOLEAN ASSESSMENT MATRIX                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    STAGE 1: LLM ANALYSIS (Sonnet 4.5)               │  │
│  │                                                      │  │
│  │    Input:  Contract document + Required clauses     │  │
│  │    Output: Free-form analysis text                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │                                │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    STAGE 2: STRUCTURED EXTRACTION (Forced JSON)     │  │
│  │                                                      │  │
│  │    Prompt:                                          │  │
│  │    "Return ONLY valid JSON. No markdown. No text."  │  │
│  │                                                      │  │
│  │    Output Schema:                                    │  │
│  │    {                                                 │  │
│  │      "assessments": [                                │  │
│  │        {                                             │  │
│  │          "clause_id": "DFARS 252.204-7012",         │  │
│  │          "status": "VIOLATION",                     │  │
│  │          "reason_code": "MISSING_FLOWDOWN",         │  │
│  │          "severity": "CRITICAL",                    │  │
│  │          "remediation_text": "..."                  │  │
│  │        }                                             │  │
│  │      ]                                               │  │
│  │    }                                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │                                │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    STAGE 3: VALIDATION & ENFORCEMENT                 │  │
│  │                                                      │  │
│  │    • Schema validation (Pydantic)                   │  │
│  │    • Enum enforcement (status, severity)            │  │
│  │    • Mandatory field check                          │  │
│  │    • Reject if parsing fails                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │                                │
│                            ▼                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    STAGE 4: LEGAL RISK REGISTRY                      │  │
│  │                                                      │  │
│  │    Store structured results in compliance database  │  │
│  │    Generate human-readable report AFTER storing     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Components

#### 4.1 Boolean Assessment Schema

**File**: `services/cognition/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from enum import Enum

class AssessmentStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    VIOLATION = "VIOLATION"
    MODIFIED = "MODIFIED"
    MISSING = "MISSING"
    UNDER_REVIEW = "UNDER_REVIEW"

class AssessmentSeverity(str, Enum):
    CRITICAL = "CRITICAL"     # Contract rejection risk
    HIGH = "HIGH"             # Requires immediate remediation
    MEDIUM = "MEDIUM"         # Requires remediation before final delivery
    LOW = "LOW"               # Recommended improvement
    INFO = "INFO"             # Informational only

class ClauseAssessment(BaseModel):
    clause_id: str = Field(..., description="Exact clause identifier (e.g., 'DFARS 252.204-7012')")
    status: AssessmentStatus
    reason_code: str = Field(..., description="Machine-readable reason (e.g., 'MISSING_FLOWDOWN')")
    severity: AssessmentSeverity
    remediation_text: str = Field(..., description="Specific action required to fix")
    evidence_location: Optional[str] = Field(None, description="Page/section reference in document")

class BooleanAssessmentMatrix(BaseModel):
    """
    Rigid, deterministic compliance assessment output.
    NO free-form text allowed until this structure is complete.
    """
    assessments: List[ClauseAssessment]
    total_clauses_checked: int
    compliant_count: int
    violation_count: int
    overall_verdict: Literal["PASS", "FAIL", "CONDITIONAL"]
```

#### 4.2 Deterministic Auditor

**File**: `services/cognition/deterministic_audit.py`

```python
import anthropic
import json
from typing import List
from .schemas import BooleanAssessmentMatrix, ClauseAssessment

class DeterministicAuditor:
    """
    Forces LLM to return structured Boolean assessments before any prose.
    """
    
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
    
    async def audit_document(
        self, 
        document_text: str,
        required_clauses: List[str],
        contract_type: str
    ) -> BooleanAssessmentMatrix:
        """
        Audit document against required clauses with deterministic output.
        
        Raises:
            ValueError: If LLM fails to return valid JSON structure
        """
        
        prompt = self._build_audit_prompt(document_text, required_clauses, contract_type)
        
        # CRITICAL: Use tool/function calling to force structured output
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            tools=[{
                "name": "record_compliance_assessment",
                "description": "Record the Boolean compliance assessment for each clause",
                "input_schema": BooleanAssessmentMatrix.model_json_schema()
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract structured output
        tool_calls = [block for block in response.content if block.type == "tool_use"]
        if not tool_calls:
            raise ValueError("LLM failed to return structured assessment. Rejecting audit.")
        
        assessment_data = tool_calls[0].input
        
        # Validate with Pydantic
        try:
            matrix = BooleanAssessmentMatrix(**assessment_data)
        except Exception as e:
            raise ValueError(f"LLM returned invalid assessment structure: {e}")
        
        return matrix
    
    def _build_audit_prompt(
        self, 
        document_text: str,
        required_clauses: List[str],
        contract_type: str
    ) -> str:
        return f"""You are a deterministic compliance auditor for US government contracts.

CONTRACT TYPE: {contract_type}

REQUIRED CLAUSES:
{chr(10).join(f"- {clause}" for clause in required_clauses)}

DOCUMENT TO AUDIT:
{document_text[:50000]}  # Truncate if needed

INSTRUCTIONS:
For EACH required clause, determine:
1. Is it PRESENT in the document? (exact text or acceptable paraphrase)
2. If ABSENT: status=VIOLATION or MISSING
3. If PRESENT but MODIFIED: status=MODIFIED
4. If PRESENT and UNMODIFIED: status=COMPLIANT

You MUST use the record_compliance_assessment tool to return your findings.

CRITICAL RULES:
- No "generally compliant" assessments
- No "appears to comply" assessments
- Only Boolean states: COMPLIANT, VIOLATION, MODIFIED, MISSING
- Provide SPECIFIC remediation text for each violation
- Reference exact page/section numbers when possible

If you cannot determine compliance with certainty, status=UNDER_REVIEW."""
```

#### 4.3 Legal Risk Registry

**Table**: `compliance_assessments`

```sql
CREATE TABLE compliance_assessments (
    assessment_id       TEXT PRIMARY KEY,
    intake_id           TEXT NOT NULL,
    clause_id           TEXT NOT NULL,
    status              TEXT NOT NULL,       -- COMPLIANT | VIOLATION | MODIFIED | MISSING
    reason_code         TEXT NOT NULL,
    severity            TEXT NOT NULL,       -- CRITICAL | HIGH | MEDIUM | LOW
    remediation_text    TEXT NOT NULL,
    evidence_location   TEXT,
    assessed_at         TIMESTAMP NOT NULL,
    assessed_by         TEXT NOT NULL,       -- "claude-sonnet-4" or operator ID
    
    FOREIGN KEY (intake_id) REFERENCES intakes(intake_id)
);

CREATE INDEX idx_assessments_intake ON compliance_assessments(intake_id);
CREATE INDEX idx_assessments_severity ON compliance_assessments(severity, status);
```

### Organism Integration

**New Collector**: `ComplianceAssessmentCollector`

```python
class ComplianceAssessmentCollector(SignalCollector):
    def collect(self) -> dict:
        return {
            "total_assessments": self._count_assessments(),
            "critical_violations": self._count_violations("CRITICAL"),
            "high_violations": self._count_violations("HIGH"),
            "pass_rate": self._compute_pass_rate(),
            "structured_output_success_rate": self._compute_structured_success_rate(),
        }
```

**New Check**: `DeterministicAuditQualityCheck`

```python
class DeterministicAuditQualityCheck(Check):
    def evaluate(self, bundle: dict) -> CheckResult:
        assessments = bundle.get("compliance_assessments", {})
        success_rate = assessments.get("structured_output_success_rate", 0.0)
        
        if success_rate < 0.95:
            return CheckResult(
                name="deterministic_audit_quality",
                ok=False,
                severity=Severity.HIGH,
                detail=f"Only {success_rate:.1%} of audits produced valid structured output. Risk of vibe-check drift.",
                evidence={"success_rate": success_rate}
            )
        
        return CheckResult.passed("deterministic_audit_quality")
```

---

## Integration with 11-Layer Organism Architecture

### Mapping Pillars to Layers

| Layer                          | Pillar Integration                                                                 |
|--------------------------------|------------------------------------------------------------------------------------|
| **1. Reality Ingestion**       | All pillars feed into this — documents, external registries, regulatory sources    |
| **2. Evidence Intelligence**   | **Pillar 3** — Asymmetrical audit adds external verification layer                 |
| **3. Entity Resolution**       | **Pillar 3** — Cross-document entity resolution is the core of this layer          |
| **4. Compliance Knowledge Graph** | **Pillar 1** — Two-tier retrieval makes the graph queryable and trustworthy     |
| **5. Verification Coverage**   | **Pillar 3** — External verification expands coverage beyond uploaded docs         |
| **6. Adversarial Auditor**     | **Pillar 4** — Boolean assessment matrix enables adversarial challenges            |
| **7. Compliance Intelligence** | **Pillar 2** — Temporal awareness is the foundation of this layer                  |
| **8. Autonomous Remediation**  | **Pillar 4** — Structured assessments enable programmatic remediation generation   |
| **9. Forensic Timeline**       | **Pillar 2** — Temporal context enables timeline reconstruction                    |
| **10. Value Attribution**      | All pillars — Deterministic outputs enable precise value measurement               |
| **11. The Organism**           | All pillars feed into organism health state and next recommended action            |

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
1. ✓ Existing: Organism core architecture
2. ✓ Existing: Evidence Intelligence pipeline
3. **New**: Clause Registry database schema
4. **New**: Regulatory Events database schema
5. **New**: Assessment Matrix schema (Pydantic models)

### Phase 2: Pillar 1 — Context-Collapse Defense (Weeks 3-4)
1. Build clause detector (regex patterns)
2. Build Clause Registry loader (FAR/DFARS scraper)
3. Implement Two-Tier Retrieval Router
4. Add `ComplianceKnowledgeCollector` to organism
5. Add `ClauseAmbiguityCheck` to organism
6. Test with FAR 52.215-2 variants

### Phase 3: Pillar 2 — Temporal Awareness (Weeks 5-6)
1. Build DPC scraper for Class Deviations
2. Build Federal Register scraper
3. Implement Regulatory Event Log
4. Build Temporal Auditor
5. Add `ComplianceIntelligenceCollector` to organism
6. Add `RegulatoryFreshnessCheck` to organism
7. Test with historical deviations

### Phase 4: Pillar 3 — Asymmetrical Audit (Weeks 7-8)
1. Integrate SAM.gov API
2. Integrate FedRAMP Marketplace API
3. Build Asymmetrical Auditor
4. Add contradiction detection to validation pipeline
5. Add `ExternalVerificationCollector` to organism
6. Add `ExternalVerificationCheck` to organism
7. Test with real company CAGE codes

### Phase 5: Pillar 4 — Deterministic Logic (Weeks 9-10)
1. Implement Boolean Assessment Schema
2. Build Deterministic Auditor with tool calling
3. Create Legal Risk Registry database
4. Modify validation pipeline to enforce structured output
5. Add `ComplianceAssessmentCollector` to organism
6. Add `DeterministicAuditQualityCheck` to organism
7. Test with 100 real contract documents

### Phase 6: Integration & Hardening (Weeks 11-12)
1. Wire all collectors into main organism engine
2. Add all checks to organism health evaluation
3. Build operator dashboard for all 4 pillars
4. End-to-end testing with Aegis dataset
5. Load testing (1000 concurrent audits)
6. Documentation and operator training

---

## Success Criteria

### Pillar 1: Context-Collapse Defense
- ✓ Deterministic hit rate > 95% for exact clause references
- ✓ Zero clause variation hallucinations in test corpus
- ✓ Semantic fallback only triggers when no exact match exists

### Pillar 2: Temporal Awareness
- ✓ Regulatory sources scraped daily with < 24h latency
- ✓ All active contracts have temporal context snapshots
- ✓ Deviation impact analysis completes < 1 hour after detection

### Pillar 3: Asymmetrical Audit
- ✓ SAM.gov verification integrated for all CAGE codes
- ✓ FedRAMP verification integrated for all security claims
- ✓ Contradiction detection rate > 98% on known bad data

### Pillar 4: Deterministic Logic
- ✓ Structured output success rate > 95%
- ✓ Zero "vibe check" assessments in production
- ✓ All assessments have machine-readable status codes

### Overall Organism Health
- ✓ Organism state remains GREEN when all pillars operational
- ✓ Organism state goes RED if any pillar fails
- ✓ Next recommended action guides operator to fix root cause

---

## Conclusion

This four-pillar architecture transforms KYC from a document processor into a **world-class compliance verification organism** that:

1. **Cannot be fooled** by clause variations (Pillar 1)
2. **Cannot drift** from temporal regulation changes (Pillar 2)
3. **Cannot miss** external registry contradictions (Pillar 3)
4. **Cannot give** vibe-check false confidence (Pillar 4)

Every pillar integrates cleanly with the existing organism architecture, preserving the domain-agnostic core while adding compliance-specific intelligence layers.

The platform becomes **bulletproof** because it verifies every claim, tracks every change, and enforces deterministic logic at every decision point.

Brother, this is the ultimate compliance organism.

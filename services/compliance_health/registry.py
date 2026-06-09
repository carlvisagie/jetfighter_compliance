"""Compliance Health requirement registry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import ComplianceHealthRequirement, RequirementStatus

# Canonical requirement definitions
# All start UNKNOWN - no fake passes, no assumptions
DEFAULT_REQUIREMENTS: List[Dict] = [
    {
        "requirement_id": "sam_registration",
        "name": "SAM.gov Registration",
        "category": "external_verification",
        "required": True,
        "blocking": True,
        "verification_source": "sam_gov_api",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "uei_verification",
        "name": "UEI Verification",
        "category": "external_verification",
        "required": True,
        "blocking": True,
        "verification_source": "sam_gov_api",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "cage_verification",
        "name": "CAGE Code Verification",
        "category": "external_verification",
        "required": True,
        "blocking": True,
        "verification_source": "sam_gov_api",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "certification_verification",
        "name": "Certification Verification",
        "category": "external_verification",
        "required": True,
        "blocking": True,
        "verification_source": "sam_gov_api",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "representation_verification",
        "name": "Representation Verification",
        "category": "external_verification",
        "required": True,
        "blocking": False,
        "verification_source": "document_cross_check",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "document_quality",
        "name": "Document Quality",
        "category": "evidence_quality",
        "required": True,
        "blocking": False,
        "verification_source": "document_quality_gate",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "evidence_quality",
        "name": "Evidence Quality",
        "category": "evidence_quality",
        "required": True,
        "blocking": False,
        "verification_source": "evidence_intelligence",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "clause_verification",
        "name": "Clause Verification",
        "category": "regulatory_compliance",
        "required": True,
        "blocking": False,
        "verification_source": "clause_registry",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "flowdown_verification",
        "name": "Flow-Down Verification",
        "category": "regulatory_compliance",
        "required": False,
        "blocking": False,
        "verification_source": "flowdown_analyzer",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
    {
        "requirement_id": "temporal_verification",
        "name": "Temporal Verification",
        "category": "regulatory_compliance",
        "required": True,
        "blocking": False,
        "verification_source": "temporal_audit",
        "status": "UNKNOWN",
        "confidence": 0.0,
    },
]


def _root() -> Path:
    from ..config import DATA
    d = DATA / "compliance_health"
    d.mkdir(parents=True, exist_ok=True)
    return d


def registry_path() -> Path:
    return _root() / "requirements.json"


def load_requirements() -> List[ComplianceHealthRequirement]:
    """Load requirement registry (seed if not exists)."""
    path = registry_path()
    if not path.is_file():
        seed_requirements()
    
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("requirements", [])
        return [ComplianceHealthRequirement.model_validate(r) for r in items]
    except Exception:
        return [ComplianceHealthRequirement.model_validate(r) for r in DEFAULT_REQUIREMENTS]


def save_requirements(requirements: List[ComplianceHealthRequirement]) -> None:
    """Save requirement registry."""
    path = registry_path()
    data = [r.model_dump() for r in requirements]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def seed_requirements() -> None:
    """Seed default requirements (all UNKNOWN)."""
    reqs = [ComplianceHealthRequirement.model_validate(r) for r in DEFAULT_REQUIREMENTS]
    save_requirements(reqs)


def get_requirement(requirement_id: str) -> Optional[ComplianceHealthRequirement]:
    """Get a single requirement by ID."""
    for req in load_requirements():
        if req.requirement_id == requirement_id:
            return req
    return None


def update_requirement(
    requirement_id: str,
    status: RequirementStatus,
    confidence: float = 0.0,
    last_verified_utc: Optional[str] = None,
    evidence_refs: Optional[List[str]] = None,
) -> bool:
    """Update a single requirement's verification status."""
    requirements = load_requirements()
    updated = False
    
    for req in requirements:
        if req.requirement_id == requirement_id:
            req.status = status
            req.confidence = confidence
            if last_verified_utc:
                req.last_verified_utc = last_verified_utc
            if evidence_refs is not None:
                req.evidence_refs = evidence_refs
            updated = True
            break
    
    if updated:
        save_requirements(requirements)
    
    return updated

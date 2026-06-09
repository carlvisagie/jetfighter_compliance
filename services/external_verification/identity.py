"""Contractor identity verification orchestrator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .sam_gov import verify_sam_registration
from .schemas import ExternalEntityVerification, VerificationStatus
from .storage import save_verification, load_verification


def _extract_claimed_identity(project_id: str) -> dict:
    """
    Extract claimed identity fields from project data.
    
    Sources (in order of preference):
    1. company_profile.json
    2. cognition entities (if available)
    3. uploaded documents metadata
    """
    from ..config import DATA
    
    intake_dir = DATA / "intakes" / project_id
    
    # Try company_profile.json
    profile_path = intake_dir / "company_profile.json"
    if profile_path.is_file():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            return {
                "legal_name": profile.get("legal_name"),
                "uei": profile.get("uei") or profile.get("unique_entity_id"),
                "cage": profile.get("cage") or profile.get("cage_code"),
            }
        except Exception:
            pass
    
    # Try cognition entities (future enhancement)
    cognition_path = intake_dir / "cognition.json"
    if cognition_path.is_file():
        try:
            cognition = json.loads(cognition_path.read_text(encoding="utf-8"))
            entities = cognition.get("entities", {})
            return {
                "legal_name": entities.get("company_name"),
                "uei": entities.get("uei"),
                "cage": entities.get("cage"),
            }
        except Exception:
            pass
    
    # No claimed identity found
    return {"legal_name": None, "uei": None, "cage": None}


def verify_contractor_identity(
    project_id: str,
    force_refresh: bool = False,
) -> ExternalEntityVerification:
    """
    Verify contractor identity against external sources.
    
    Args:
        project_id: Project/intake ID
        force_refresh: Re-run verification even if cached result exists
    
    Returns:
        ExternalEntityVerification with status, confidence, and issues
    
    Rules:
    - If API key missing: status=UNKNOWN, confidence=0.0
    - If claimed values missing: status=UNKNOWN
    - If source confirms match: status=PASS, high confidence
    - If source confirms mismatch: status=FAIL, high confidence
    - If ambiguous: status=UNKNOWN
    """
    # Check for cached result
    if not force_refresh:
        cached = load_verification(project_id)
        if cached:
            return cached
    
    # Extract claimed identity
    claimed = _extract_claimed_identity(project_id)
    
    # Verify against SAM.gov
    sam_result = verify_sam_registration(
        uei_claimed=claimed.get("uei"),
        cage_claimed=claimed.get("cage"),
        legal_name_claimed=claimed.get("legal_name"),
    )
    
    # Build verification result
    verification = ExternalEntityVerification(
        project_id=project_id,
        legal_name_claimed=claimed.get("legal_name"),
        uei_claimed=claimed.get("uei"),
        cage_claimed=claimed.get("cage"),
        **sam_result,
    )
    
    # Compute overall status and confidence
    verification.status = verification.compute_status()
    verification.confidence = verification.compute_confidence()
    
    # Persist result
    save_verification(verification)
    
    # Feed compliance health registry
    _feed_compliance_health(verification)
    
    return verification


def get_verification(project_id: str) -> Optional[ExternalEntityVerification]:
    """Get existing verification result (cached)."""
    return load_verification(project_id)


def _feed_compliance_health(verification: ExternalEntityVerification) -> None:
    """
    Feed verification results to compliance health registry.
    
    Updates three requirements:
    - sam_registration
    - uei_verification
    - cage_verification
    """
    from services.compliance_health.registry import update_requirement
    from services.compliance_health.schemas import RequirementStatus
    
    # Map verification status to requirement status
    def map_status(vstatus: VerificationStatus) -> RequirementStatus:
        if vstatus == VerificationStatus.PASS:
            return RequirementStatus.PASS
        elif vstatus == VerificationStatus.FAIL:
            return RequirementStatus.FAIL
        elif vstatus == VerificationStatus.NOT_APPLICABLE:
            return RequirementStatus.NOT_APPLICABLE
        else:
            return RequirementStatus.UNKNOWN
    
    timestamp = verification.source_checked_utc
    evidence = [f"external_verification/{verification.project_id}/sam_verification.json"]
    
    # Update SAM Registration
    update_requirement(
        requirement_id="sam_registration",
        status=map_status(verification.registration_status),
        confidence=verification.confidence,
        last_verified_utc=timestamp,
        evidence_refs=evidence,
    )
    
    # Update UEI Verification
    update_requirement(
        requirement_id="uei_verification",
        status=map_status(verification.uei_status),
        confidence=verification.confidence,
        last_verified_utc=timestamp,
        evidence_refs=evidence,
    )
    
    # Update CAGE Verification
    update_requirement(
        requirement_id="cage_verification",
        status=map_status(verification.cage_status),
        confidence=verification.confidence,
        last_verified_utc=timestamp,
        evidence_refs=evidence,
    )

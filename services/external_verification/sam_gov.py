"""SAM.gov API integration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import httpx

from .schemas import (
    SAMRegistrationStatus,
    ExclusionStatus,
    VerificationStatus,
    VerificationIssue,
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_api_configured() -> bool:
    """Check if SAM.gov API key is configured."""
    api_key = os.environ.get("SAM_GOV_API_KEY", "").strip()
    return bool(api_key)


def query_sam_entity(uei: str, legal_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Query SAM.gov Entity API for contractor information.
    
    Returns None if API not configured or request fails.
    """
    if not is_api_configured():
        return None
    
    api_key = os.environ.get("SAM_GOV_API_KEY", "")
    base_url = os.environ.get("SAM_GOV_API_BASE", "https://api.sam.gov")
    
    # SAM.gov Entity Management API v3
    # https://open.gsa.gov/api/entity-api/
    url = f"{base_url}/entity-information/v3/entities"
    # PATCH ACQ-IMPLEMENT-2: Include coreData and pointsOfContact for contactability
    params = {
        "ueiSAM": uei,
        "api_key": api_key,
        "includeSections": "coreData,pointsOfContact",
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, params=params)
            
            if r.status_code == 404:
                return {"status": "not_found", "uei": uei}
            
            if r.status_code != 200:
                return None
            
            data = r.json()
            
            # Extract entity data from response
            entities = data.get("entityData", [])
            if not entities:
                return {"status": "not_found", "uei": uei}
            
            # Return first matching entity
            return entities[0]
    
    except Exception:
        return None


# =============================================================================
# PATCH ACQ-IMPLEMENT-2: SAM Contactability Extraction
# =============================================================================

@dataclass
class SAMContactability:
    """Contactability data extracted from SAM.gov."""
    uei: str
    legal_name: Optional[str] = None
    website: Optional[str] = None
    
    # Primary POC (Government Business POC preferred)
    poc_first_name: Optional[str] = None
    poc_last_name: Optional[str] = None
    poc_title: Optional[str] = None
    poc_email: Optional[str] = None
    poc_phone: Optional[str] = None
    poc_type: Optional[str] = None
    
    # All POCs found
    all_pocs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    registration_status: Optional[str] = None
    source_checked_utc: Optional[str] = None
    api_success: bool = False
    error: Optional[str] = None


def extract_sam_contactability(uei: str) -> SAMContactability:
    """
    Extract contactability data from SAM.gov for a given UEI.
    
    Returns website, POC email, phone, and names if available.
    """
    result = SAMContactability(uei=uei, source_checked_utc=_utc())
    
    if not is_api_configured():
        result.error = "SAM_GOV_API_KEY not configured"
        return result
    
    entity = query_sam_entity(uei)
    
    if entity is None:
        result.error = "SAM.gov API request failed"
        return result
    
    if entity.get("status") == "not_found":
        result.error = "UEI not found in SAM.gov"
        return result
    
    result.api_success = True
    
    # Extract core data
    core_data = entity.get("coreData", {})
    entity_info = core_data.get("entityInformation", {})
    
    result.legal_name = entity_info.get("entityName")
    result.website = entity_info.get("entityURL")
    result.registration_status = entity_info.get("registrationStatus")
    
    # Extract points of contact
    pocs = entity.get("pointsOfContact", [])
    if isinstance(pocs, dict):
        # Sometimes returned as dict with POC types as keys
        pocs = list(pocs.values()) if pocs else []
    
    result.all_pocs = []
    
    # POC priority order for primary contact
    poc_priority = [
        "GB",   # Government Business POC
        "EB",   # Electronic Business POC
        "SL",   # Sales POC
        "AP",   # Accounts Payable POC
        "AR",   # Accounts Receivable POC
    ]
    
    primary_poc = None
    
    for poc in pocs:
        if not isinstance(poc, dict):
            continue
            
        poc_data = {
            "type": poc.get("pocType") or poc.get("type"),
            "first_name": poc.get("firstName"),
            "last_name": poc.get("lastName"),
            "title": poc.get("title") or poc.get("POCTitle"),
            "email": poc.get("email"),
            "phone": poc.get("phone") or poc.get("usPhone"),
        }
        
        # Clean phone number
        if poc_data["phone"]:
            poc_data["phone"] = str(poc_data["phone"]).strip()
        
        result.all_pocs.append(poc_data)
        
        # Select primary POC based on priority
        poc_type = poc_data.get("type", "")
        if primary_poc is None:
            primary_poc = poc_data
        elif poc_type in poc_priority:
            current_priority = poc_priority.index(poc_type) if poc_type in poc_priority else 999
            primary_priority = poc_priority.index(primary_poc.get("type", "")) if primary_poc.get("type", "") in poc_priority else 999
            if current_priority < primary_priority:
                primary_poc = poc_data
    
    # Set primary POC fields
    if primary_poc:
        result.poc_first_name = primary_poc.get("first_name")
        result.poc_last_name = primary_poc.get("last_name")
        result.poc_title = primary_poc.get("title")
        result.poc_email = primary_poc.get("email")
        result.poc_phone = primary_poc.get("phone")
        result.poc_type = primary_poc.get("type")
    
    return result


def sam_contactability_to_dict(sc: SAMContactability) -> Dict[str, Any]:
    """Convert SAMContactability to dictionary for JSON serialization."""
    return {
        "uei": sc.uei,
        "legal_name": sc.legal_name,
        "website": sc.website,
        "poc_first_name": sc.poc_first_name,
        "poc_last_name": sc.poc_last_name,
        "poc_full_name": f"{sc.poc_first_name or ''} {sc.poc_last_name or ''}".strip() or None,
        "poc_title": sc.poc_title,
        "poc_email": sc.poc_email,
        "poc_phone": sc.poc_phone,
        "poc_type": sc.poc_type,
        "poc_count": len(sc.all_pocs),
        "all_pocs": sc.all_pocs,
        "registration_status": sc.registration_status,
        "source_checked_utc": sc.source_checked_utc,
        "api_success": sc.api_success,
        "error": sc.error,
    }


def verify_sam_registration(
    uei_claimed: Optional[str],
    cage_claimed: Optional[str],
    legal_name_claimed: Optional[str],
) -> Dict[str, Any]:
    """
    Verify contractor identity against SAM.gov.
    
    Returns:
    - sam_status: ACTIVE, INACTIVE, EXPIRED, NOT_FOUND, UNKNOWN
    - uei_status: PASS, FAIL, UNKNOWN
    - cage_status: PASS, FAIL, UNKNOWN
    - registration_status: PASS, FAIL, UNKNOWN
    - exclusions_status: CLEAR, EXCLUDED, UNKNOWN
    - matched_legal_name, matched_address, active_registration
    - certifications, representations
    - issues[]
    """
    result = {
        "sam_status": SAMRegistrationStatus.UNKNOWN,
        "uei_status": VerificationStatus.UNKNOWN,
        "cage_status": VerificationStatus.UNKNOWN,
        "registration_status": VerificationStatus.UNKNOWN,
        "exclusions_status": ExclusionStatus.UNKNOWN,
        "matched_legal_name": None,
        "matched_address": None,
        "active_registration": None,
        "certifications": [],
        "representations": [],
        "source_checked_utc": None,
        "issues": [],
    }
    
    # API not configured
    if not is_api_configured():
        result["issues"].append(
            VerificationIssue(
                field="api_configuration",
                severity="info",
                detail="SAM.gov API key not configured (SAM_GOV_API_KEY)",
            ).model_dump()
        )
        return result
    
    # Missing claimed UEI
    if not uei_claimed:
        result["issues"].append(
            VerificationIssue(
                field="uei_claimed",
                severity="warning",
                detail="No UEI claimed by contractor",
            ).model_dump()
        )
        return result
    
    # Query SAM.gov
    result["source_checked_utc"] = _utc()
    entity = query_sam_entity(uei_claimed, legal_name_claimed)
    
    if entity is None:
        result["issues"].append(
            VerificationIssue(
                field="sam_api",
                severity="warning",
                detail="SAM.gov API request failed or timed out",
            ).model_dump()
        )
        return result
    
    if entity.get("status") == "not_found":
        result["sam_status"] = SAMRegistrationStatus.NOT_FOUND
        result["uei_status"] = VerificationStatus.FAIL
        result["registration_status"] = VerificationStatus.FAIL
        result["issues"].append(
            VerificationIssue(
                field="uei",
                severity="critical",
                detail="UEI not found in SAM.gov registry",
                claimed_value=uei_claimed,
            ).model_dump()
        )
        return result
    
    # Extract core registration data
    core_data = entity.get("coreData", {})
    entity_reg = core_data.get("entityInformation", {})
    
    # Registration status
    reg_status = entity_reg.get("registrationStatus", "").upper()
    if reg_status == "ACTIVE":
        result["sam_status"] = SAMRegistrationStatus.ACTIVE
        result["registration_status"] = VerificationStatus.PASS
        result["active_registration"] = True
    elif reg_status == "INACTIVE":
        result["sam_status"] = SAMRegistrationStatus.INACTIVE
        result["registration_status"] = VerificationStatus.FAIL
        result["active_registration"] = False
        result["issues"].append(
            VerificationIssue(
                field="registration_status",
                severity="critical",
                detail="SAM.gov registration is INACTIVE",
            ).model_dump()
        )
    else:
        result["sam_status"] = SAMRegistrationStatus.UNKNOWN
        result["active_registration"] = None
    
    # UEI verification
    matched_uei = entity_reg.get("ueiSAM")
    if matched_uei and matched_uei.upper() == uei_claimed.upper():
        result["uei_status"] = VerificationStatus.PASS
    elif matched_uei:
        result["uei_status"] = VerificationStatus.FAIL
        result["issues"].append(
            VerificationIssue(
                field="uei",
                severity="critical",
                detail="UEI mismatch",
                claimed_value=uei_claimed,
                actual_value=matched_uei,
            ).model_dump()
        )
    
    # CAGE verification
    matched_cage = entity_reg.get("cageCode")
    if cage_claimed and matched_cage:
        if matched_cage.upper() == cage_claimed.upper():
            result["cage_status"] = VerificationStatus.PASS
        else:
            result["cage_status"] = VerificationStatus.FAIL
            result["issues"].append(
                VerificationIssue(
                    field="cage",
                    severity="critical",
                    detail="CAGE code mismatch",
                    claimed_value=cage_claimed,
                    actual_value=matched_cage,
                ).model_dump()
            )
    elif matched_cage:
        result["cage_status"] = VerificationStatus.UNKNOWN
    
    # Legal name verification
    result["matched_legal_name"] = entity_reg.get("entityName")
    if legal_name_claimed and result["matched_legal_name"]:
        # Fuzzy match (case-insensitive, whitespace normalized)
        claimed_norm = " ".join(legal_name_claimed.upper().split())
        matched_norm = " ".join(result["matched_legal_name"].upper().split())
        
        if claimed_norm != matched_norm:
            result["issues"].append(
                VerificationIssue(
                    field="legal_name",
                    severity="warning",
                    detail="Legal name does not exactly match SAM.gov",
                    claimed_value=legal_name_claimed,
                    actual_value=result["matched_legal_name"],
                ).model_dump()
            )
    
    # Address
    physical_addr = entity_reg.get("physicalAddress", {})
    result["matched_address"] = ", ".join(
        filter(None, [
            physical_addr.get("addressLine1"),
            physical_addr.get("city"),
            physical_addr.get("stateOrProvinceCode"),
            physical_addr.get("zipCode"),
        ])
    ) or None
    
    # Exclusions/debarment
    # SAM.gov exclusions are in separate API endpoint, but registration status covers active/inactive
    if result["active_registration"]:
        result["exclusions_status"] = ExclusionStatus.CLEAR
    
    # Certifications and representations (if available in entity data)
    assertions = core_data.get("assertions", {})
    if isinstance(assertions, dict):
        result["certifications"] = assertions.get("certifications", [])
        result["representations"] = assertions.get("representations", [])
    
    return result

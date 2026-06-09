"""External verification schemas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Verification outcome status."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SAMRegistrationStatus(str, Enum):
    """SAM.gov registration status."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


class ExclusionStatus(str, Enum):
    """Debarment/exclusion status."""
    CLEAR = "CLEAR"
    EXCLUDED = "EXCLUDED"
    UNKNOWN = "UNKNOWN"


class VerificationIssue(BaseModel):
    """A single verification issue or mismatch."""
    field: str = Field(..., description="Field that failed verification")
    severity: str = Field(..., description="info, warning, critical")
    detail: str = Field(..., description="Human-readable issue description")
    claimed_value: Optional[str] = None
    actual_value: Optional[str] = None


class ExternalEntityVerification(BaseModel):
    """
    External entity verification result.
    
    Verifies contractor identity against SAM.gov and other authoritative sources.
    """
    project_id: str = Field(..., description="Project/intake ID")
    
    # Claimed values (from customer)
    legal_name_claimed: Optional[str] = None
    uei_claimed: Optional[str] = None
    cage_claimed: Optional[str] = None
    
    # SAM.gov verification results
    sam_status: SAMRegistrationStatus = SAMRegistrationStatus.UNKNOWN
    uei_status: VerificationStatus = VerificationStatus.UNKNOWN
    cage_status: VerificationStatus = VerificationStatus.UNKNOWN
    registration_status: VerificationStatus = VerificationStatus.UNKNOWN
    
    # Matched values (from external source)
    matched_legal_name: Optional[str] = None
    matched_address: Optional[str] = None
    active_registration: Optional[bool] = None
    exclusions_status: ExclusionStatus = ExclusionStatus.UNKNOWN
    
    # Additional SAM.gov data
    certifications: List[str] = Field(default_factory=list)
    representations: List[str] = Field(default_factory=list)
    
    # Source metadata
    source: str = Field(default="sam_gov_api", description="Verification source")
    source_checked_utc: Optional[str] = Field(None, description="ISO timestamp of last check")
    
    # Overall assessment
    status: VerificationStatus = VerificationStatus.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_refs: List[str] = Field(default_factory=list)
    issues: List[VerificationIssue] = Field(default_factory=list)
    
    def compute_status(self) -> VerificationStatus:
        """
        Compute overall verification status from component statuses.
        
        Rules:
        - FAIL: Any component explicitly failed
        - UNKNOWN: No API access, missing claimed values, or ambiguous
        - PASS: All required components passed
        """
        # FAIL: Any component explicitly failed
        if any(
            s == VerificationStatus.FAIL
            for s in [self.uei_status, self.cage_status, self.registration_status]
        ):
            return VerificationStatus.FAIL
        
        # FAIL: Excluded or debarred
        if self.exclusions_status == ExclusionStatus.EXCLUDED:
            return VerificationStatus.FAIL
        
        # FAIL: Inactive registration
        if self.sam_status in (SAMRegistrationStatus.INACTIVE, SAMRegistrationStatus.EXPIRED):
            return VerificationStatus.FAIL
        
        # UNKNOWN: No source access
        if self.source_checked_utc is None:
            return VerificationStatus.UNKNOWN
        
        # UNKNOWN: Missing critical claimed values
        if not self.uei_claimed:
            return VerificationStatus.UNKNOWN
        
        # PASS: All components passed
        if all(
            s == VerificationStatus.PASS
            for s in [self.uei_status, self.cage_status, self.registration_status]
        ):
            return VerificationStatus.PASS
        
        # Default: UNKNOWN
        return VerificationStatus.UNKNOWN
    
    def compute_confidence(self) -> float:
        """
        Compute confidence score based on verification completeness.
        
        - 0.0: No external verification performed
        - 0.5: Partial verification (some fields checked)
        - 0.9: Full verification with all fields matching
        """
        if self.source_checked_utc is None:
            return 0.0
        
        if self.status == VerificationStatus.FAIL:
            return 0.95  # High confidence in failure
        
        if self.status == VerificationStatus.UNKNOWN:
            return 0.0  # No confidence in unknown
        
        # PASS: Check completeness
        verified_count = sum(
            1 for s in [self.uei_status, self.cage_status, self.registration_status]
            if s == VerificationStatus.PASS
        )
        
        if verified_count == 3 and self.sam_status == SAMRegistrationStatus.ACTIVE:
            return 0.9
        
        if verified_count >= 2:
            return 0.7
        
        if verified_count >= 1:
            return 0.5
        
        return 0.0

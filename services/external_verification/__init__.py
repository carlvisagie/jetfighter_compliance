"""External Verification Layer — authoritative third-party identity and compliance checks."""
from .identity import verify_contractor_identity, get_verification
from .schemas import (
    ExternalEntityVerification,
    VerificationStatus,
    SAMRegistrationStatus,
    ExclusionStatus,
)

__all__ = [
    "verify_contractor_identity",
    "get_verification",
    "ExternalEntityVerification",
    "VerificationStatus",
    "SAMRegistrationStatus",
    "ExclusionStatus",
]

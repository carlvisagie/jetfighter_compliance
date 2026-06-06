from typing import Any, Dict, List

from services.cognition.schemas import AwarenessState, GapResolution, ResolutionStrategy

def evaluate_gap_resolution(gap: Dict[str, Any], state: AwarenessState) -> GapResolution:
    gap_id = gap.get("gap_id", "")
    label = gap.get("label", "")
    
    # We decide strategy based on the gap_id and what the organism knows.
    # We use a simple rule engine for now to satisfy the decision hierarchy.
    
    known_str = " ".join(state.knows).lower()
    
    # Check for uninferrable types like screenshots, photos, signatures
    if "screenshot" in gap_id or "screenshot" in label.lower() or "signature" in label.lower() or "photo" in label.lower() or gap_id == "mfa_screenshot":
        return GapResolution(
            gap_id=gap_id,
            strategy=ResolutionStrategy.REQUEST,
            confidence=0.9,
            target_document_type=gap_id,
            missing_fields=[],
            reasoning="Physical evidence (like screenshots or signatures) cannot be automatically inferred."
        )

    # For documentary gaps (e.g. ssp, policy, poam, inventory), check if we have enough facts
    # For testing purposes:
    # "ssp" requires "network_architecture"
    # "policy" requires "company_officer"
    
    if gap_id == "ssp":
        if "network_architecture" in known_str:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.85,
                target_document_type="ssp",
                missing_fields=[],
                reasoning="Sufficient network architecture and domain context found to draft an SSP."
            )
        else:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.PARTIAL,
                confidence=0.6,
                target_document_type="ssp",
                missing_fields=["network_architecture"],
                reasoning="Can partially draft SSP, but network architecture details are missing."
            )
            
    if "policy" in gap_id.lower() or "policy" in label.lower():
        if "company_officer" in known_str:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.85,
                target_document_type="policy",
                missing_fields=[],
                reasoning="Sufficient policy context and officer names found to draft a policy."
            )
        else:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.PARTIAL,
                confidence=0.7,
                target_document_type="policy",
                missing_fields=["company_officer"],
                reasoning="Can partially draft policy, but company officer name is missing."
            )
            
    if gap_id == "inventory" or "inventory" in label.lower():
        if "technology:" in known_str or "vendor:" in known_str:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.8,
                target_document_type="asset_inventory",
                missing_fields=[],
                reasoning="Discovered vendors and technologies can be compiled into an inventory."
            )

    # Default fallback: REQUEST
    return GapResolution(
        gap_id=gap_id,
        strategy=ResolutionStrategy.REQUEST,
        confidence=0.9,
        target_document_type=gap_id,
        missing_fields=[],
        reasoning="Insufficient evidence in the profile to infer or draft this document."
    )

def evaluate_all_gaps(gaps: List[Dict[str, Any]], state: AwarenessState) -> List[GapResolution]:
    resolutions = []
    
    # Empty State Tolerance: Generate explicit REQUEST resolutions for basic facts
    if state.confidence_level < 0.2:
        if "company_name" in state.does_not_know:
            resolutions.append(GapResolution(
                gap_id="missing_company_name",
                strategy=ResolutionStrategy.REQUEST,
                confidence=0.9,
                target_document_type="basic_info",
                missing_fields=["company_name"],
                reasoning="The organism extracted no intelligence and cannot identify the company name."
            ))
        if "domain_context" in state.does_not_know:
            resolutions.append(GapResolution(
                gap_id="missing_domain",
                strategy=ResolutionStrategy.REQUEST,
                confidence=0.9,
                target_document_type="compliance_context",
                missing_fields=["domain"],
                reasoning="No compliance domain could be detected from the provided files."
            ))

    for gap in gaps:
        resolutions.append(evaluate_gap_resolution(gap, state))
    return resolutions

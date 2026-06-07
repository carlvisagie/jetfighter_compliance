from typing import Any, Dict, List

from services.cognition.schemas import AwarenessState, GapResolution, ResolutionStrategy

def evaluate_gap_resolution(gap: Dict[str, Any], state: AwarenessState) -> GapResolution:
    gap_id = gap.get("gap_id", "")
    label = gap.get("label", "")
    
    known_str = " ".join(state.knows).lower()
    
    if gap_id == "mfa_evidence" or "screenshot" in gap_id or "screenshot" in label.lower() or "signature" in label.lower() or "photo" in label.lower():
        return GapResolution(
            gap_id=gap_id,
            strategy=ResolutionStrategy.REQUEST,
            confidence=0.9,
            target_document_type=gap_id,
            missing_fields=[],
            reasoning="Physical evidence (like screenshots or signatures) cannot be automatically inferred.",
            evidence_used=[],
            reason_unresolved="Physical evidence must be manually supplied."
        )

    if gap_id == "ssp_poam" or gap_id == "ssp":
        evidence = []
        for k in state.knows:
            if k.startswith("technology:") or k.startswith("cloud_provider:") or k.startswith("identity_provider:") or k.startswith("domain:"):
                evidence.append(k)
        if evidence:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.PARTIAL,
                confidence=0.6,
                target_document_type="ssp",
                missing_fields=["network_architecture", "data_flow_diagram"],
                reasoning="Sufficient technology stack found to draft initial system description.",
                evidence_used=evidence,
                reason_unresolved="Diagrams and specific network layouts cannot be inferred from standard textual metadata."
            )
            
    if gap_id == "access_control":
        evidence = []
        for k in state.knows:
            if "entra id" in k.lower() or "okta" in k.lower() or "duo" in k.lower():
                evidence.append(k)
        if evidence:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.75,
                target_document_type="access_control_policy",
                missing_fields=[],
                reasoning="Centralized IAM platform detected; logical access control narrative can be generated.",
                evidence_used=evidence,
                reason_unresolved=""
            )
        else:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.PARTIAL,
                confidence=0.75,
                target_document_type="access_control_policy",
                missing_fields=["iam_platform", "mfa_enforcement_details"],
                reasoning="No centralized IAM detected; falling back to partial standard access control policy.",
                evidence_used=[],
                reason_unresolved="IAM platform details not found in the extracted evidence."
            )

    if gap_id == "vendor_policy" or "vendor_policy" in label.lower():
        evidence = []
        for k in state.knows:
            if k.startswith("vendor:") or k.startswith("company_name:"):
                evidence.append(k)
        if evidence:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.7,
                target_document_type="vendor_policy",
                missing_fields=[],
                reasoning="Sufficient vendor context and company name found to draft a policy.",
                evidence_used=evidence,
                reason_unresolved=""
            )

    if gap_id == "incident_response":
        evidence = []
        for k in state.knows:
            if "crowdstrike" in k.lower() or "defender" in k.lower() or k.startswith("email:") or k.startswith("company_name:"):
                evidence.append(k)
        has_edr = any("crowdstrike" in e.lower() or "defender" in e.lower() for e in evidence)
        if has_edr:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.83,
                target_document_type="incident_response_plan",
                missing_fields=["incident_response_coordinator_name"],
                reasoning="EDR tools detected; can generate core IR plan with specific detection stack but coordinator must be assigned.",
                evidence_used=evidence,
                reason_unresolved="No person entity found with sufficient confidence to assign as coordinator."
            )
        else:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.PARTIAL,
                confidence=0.83,
                target_document_type="incident_response_plan",
                missing_fields=["incident_response_coordinator_name", "detection_stack"],
                reasoning="Core IR plan can be generated, missing EDR details.",
                evidence_used=evidence,
                reason_unresolved="No person entity found with sufficient confidence to assign as coordinator. No EDR tools detected."
            )

    if gap_id == "backup_evidence":
        evidence = []
        for k in state.knows:
            if "aws" in k.lower() or "azure" in k.lower() or "veeam" in k.lower():
                evidence.append(k)
        if evidence:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.7,
                target_document_type="backup_policy",
                missing_fields=[],
                reasoning="Cloud/Storage platform detected; can generate backup policy.",
                evidence_used=evidence,
                reason_unresolved=""
            )

    if gap_id == "training_record" or gap_id == "hipaa_workforce_training":
        evidence = []
        for k in state.knows:
            if "knowbe4" in k.lower() or "proofpoint" in k.lower():
                evidence.append(k)
        return GapResolution(
            gap_id=gap_id,
            strategy=ResolutionStrategy.PARTIAL,
            confidence=0.8,
            target_document_type="training_policy",
            missing_fields=["training_completion_logs"],
            reasoning="Security awareness policy can be drafted, but physical completion logs must be requested.",
            evidence_used=evidence,
            reason_unresolved="Physical training records cannot be inferred and must be provided."
        )

    if gap_id == "hipaa_risk_assessment" or gap_id == "risk_register":
        evidence = []
        for k in state.knows:
            if k.startswith("technology:") or k.startswith("vendor:"):
                evidence.append(k)
        if evidence:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.PARTIAL,
                confidence=0.85,
                target_document_type="risk_register",
                missing_fields=["risk_scores", "mitigation_status"],
                reasoning="Asset inventory can be used to pre-populate a baseline Risk Register matrix.",
                evidence_used=evidence,
                reason_unresolved="Risk scores and mitigation status must be manually assessed by the customer."
            )

    if gap_id == "asset_inventory" or "inventory" in gap_id.lower() or "inventory" in label.lower():
        evidence = []
        for k in state.knows:
            if k.startswith("technology:") or k.startswith("vendor:") or k.startswith("cloud_provider:") or k.startswith("identity_provider:"):
                evidence.append(k)
        if evidence:
            return GapResolution(
                gap_id=gap_id,
                strategy=ResolutionStrategy.GENERATE,
                confidence=0.8,
                target_document_type="asset_inventory",
                missing_fields=[],
                reasoning="Discovered vendors and technologies can be compiled into an inventory.",
                evidence_used=evidence,
                reason_unresolved=""
            )
            
    if "policy" in gap_id.lower() or "policy" in label.lower():
        evidence = []
        for k in state.knows:
            if k.startswith("company_name:"):
                evidence.append(k)
        return GapResolution(
            gap_id=gap_id,
            strategy=ResolutionStrategy.GENERATE,
            confidence=0.85,
            target_document_type="policy",
            missing_fields=[],
            reasoning="Can draft generic policy structure.",
            evidence_used=evidence,
            reason_unresolved=""
        )

    # Default fallback: REQUEST
    return GapResolution(
        gap_id=gap_id,
        strategy=ResolutionStrategy.REQUEST,
        confidence=0.9,
        target_document_type=gap_id,
        missing_fields=[],
        reasoning="Insufficient evidence in the profile to infer or draft this document.",
        evidence_used=[],
        reason_unresolved="No matching patterns found."
    )

def evaluate_all_gaps(gaps: List[Dict[str, Any]], state: AwarenessState) -> List[GapResolution]:
    resolutions = []
    
    # Check identity anchor
    has_identity = "company_name" not in state.does_not_know
    for k in state.knows:
        if k.startswith("company_name:") or k.startswith("domain:") or k.startswith("legal_entity:"):
            has_identity = True
            break
            
    # Identity requirements
    if "company_name" in state.does_not_know:
        resolutions.append(GapResolution(
            gap_id="missing_company_name",
            strategy=ResolutionStrategy.REQUEST,
            confidence=0.9,
            target_document_type="basic_info",
            missing_fields=["company_name"],
            reasoning="The organism extracted no intelligence and cannot identify the company name.",
            evidence_used=[],
            reason_unresolved="No intelligence found."
        ))

    # Empty State Tolerance: Generate explicit REQUEST resolutions for basic facts
    if state.confidence_level < 0.2:
        if "domain_context" in state.does_not_know:
            resolutions.append(GapResolution(
                gap_id="missing_domain",
                strategy=ResolutionStrategy.REQUEST,
                confidence=0.9,
                target_document_type="compliance_context",
                missing_fields=["domain"],
                reasoning="No compliance domain could be detected from the provided files.",
                evidence_used=[],
                reason_unresolved="No intelligence found."
            ))

    for gap in gaps:
        res = evaluate_gap_resolution(gap, state)
        if not has_identity and res.strategy == ResolutionStrategy.GENERATE:
            res.strategy = ResolutionStrategy.PARTIAL
            if "company_identity" not in res.missing_fields:
                res.missing_fields.append("company_identity")
            res.reason_unresolved = "Company identity not established."
            # We preserve the original confidence, but validation.py will flag it.
            
        resolutions.append(res)
    return resolutions

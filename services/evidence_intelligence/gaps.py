"""Detect likely missing evidence gaps."""
from __future__ import annotations

from typing import Any, Dict, List, Set

from .schemas import DocumentType, GapItem

GAP_DEFS = [
    {
        "gap_id": "mfa_evidence",
        "label": "Multi-factor authentication evidence",
        "explanation": "Screenshots or exports showing MFA is enforced help prove access control.",
        "why": "Assessors often ask how you protect accounts beyond passwords.",
        "catalog_key": "mfa",
        "priority": "high",
        "doc_types": {"mfa_evidence", "screenshot"},
    },
    {
        "gap_id": "training_record",
        "label": "Security awareness training record",
        "explanation": "A completion report or LMS export shows personnel training.",
        "why": "Training records are a common CMMC/NIST expectation.",
        "catalog_key": "training",
        "priority": "high",
        "doc_types": {"training_record"},
    },
    {
        "gap_id": "vendor_policy",
        "label": "Vendor / third-party management policy",
        "explanation": "How you evaluate and monitor suppliers that touch your environment.",
        "why": "Supply chain risk is a frequent audit focus.",
        "catalog_key": "vendor_policy",
        "priority": "medium",
        "doc_types": {"vendor_document", "policy"},
    },
    {
        "gap_id": "asset_inventory",
        "label": "Asset inventory",
        "explanation": "A list of systems, devices, or software in scope.",
        "why": "You cannot protect what you have not inventoried.",
        "catalog_key": "policy_general",
        "priority": "high",
        "doc_types": {"asset_inventory"},
    },
    {
        "gap_id": "backup_evidence",
        "label": "Backup and recovery evidence",
        "explanation": "Backup policy, job logs, or restore test results.",
        "why": "Recovery capability is required for resilience controls.",
        "catalog_key": "policy_general",
        "priority": "medium",
        "doc_types": {"backup_evidence"},
    },
    {
        "gap_id": "vulnerability_evidence",
        "label": "Vulnerability scan or patch evidence",
        "explanation": "Scan reports or patch tracking for in-scope systems.",
        "why": "Vulnerability management is a core security practice.",
        "catalog_key": "policy_general",
        "priority": "high",
        "doc_types": {"vulnerability_report"},
    },
    {
        "gap_id": "access_control",
        "label": "Access control evidence",
        "explanation": "User listings, access reviews, or privileged access controls.",
        "why": "Access control is central to most compliance frameworks.",
        "catalog_key": "mfa",
        "priority": "high",
        "doc_types": {"access_control_evidence"},
    },
    {
        "gap_id": "incident_response",
        "label": "Incident response plan or evidence",
        "explanation": "IR plan, playbooks, or tabletop exercise records.",
        "why": "Shows you can detect and respond to security events.",
        "catalog_key": "policy_general",
        "priority": "medium",
        "doc_types": {"incident_response"},
    },
    {
        "gap_id": "ssp_poam",
        "label": "SSP or POA&M reference",
        "explanation": "System Security Plan or Plan of Action and Milestones.",
        "why": "Often required for NIST/CMMC style assessments.",
        "catalog_key": "ssp_section",
        "priority": "low",
        "doc_types": {"ssp", "poam"},
    },
]


def detect_gaps(profile: Dict[str, Any]) -> List[GapItem]:
    present: Set[DocumentType] = set()
    for row in profile.get("document_inventory") or []:
        present.add(row.get("document_type") or "unknown")

    gaps: List[GapItem] = []
    for gdef in GAP_DEFS:
        if present & set(gdef["doc_types"]):
            continue
        catalog = gdef["catalog_key"]
        gaps.append(
            GapItem(
                gap_id=gdef["gap_id"],
                label=gdef["label"],
                plain=gdef["explanation"],
                why=gdef["why"],
                priority=gdef["priority"],
                confidence=0.72,
                example_item_id=catalog,
            )
        )
    prio = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: prio.get(g.priority, 9))
    return gaps

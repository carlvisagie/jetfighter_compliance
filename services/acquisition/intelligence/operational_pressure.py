"""
Compliance-adjacent operational pressure detection.

Detects pre-compliance entanglement: customer/vendor/procurement friction that
eventually produces paperwork — not explicit CMMC/DFARS thread hunting.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Canonical signal category keys (telemetry + scoring)
SIGNAL_CATEGORIES: Tuple[str, ...] = (
    "customer_security_pressure",
    "vendor_onboarding_pressure",
    "procurement_security_requirement",
    "security_questionnaire_pressure",
    "insurance_compliance_pressure",
    "audit_preparation_pressure",
    "evidence_request_pressure",
    "policy_request_pressure",
    "mfa_requirement_pressure",
    "supplier_security_review",
    "ai_governance_pressure",
    "documentation_uncertainty",
    "customer_deadline_pressure",
    "subcontractor_requirement_pressure",
    "data_handling_uncertainty",
)

# Operator-facing badge labels
UI_BADGE_LABELS: Dict[str, str] = {
    "customer_security_pressure": "Customer pressure",
    "vendor_onboarding_pressure": "Vendor onboarding",
    "procurement_security_requirement": "Procurement requirement",
    "security_questionnaire_pressure": "Questionnaire burden",
    "insurance_compliance_pressure": "Insurance pressure",
    "audit_preparation_pressure": "Audit preparation",
    "evidence_request_pressure": "Evidence request",
    "policy_request_pressure": "Policy request",
    "mfa_requirement_pressure": "MFA requirement",
    "supplier_security_review": "Supplier security review",
    "ai_governance_pressure": "AI governance",
    "documentation_uncertainty": "Documentation burden",
    "customer_deadline_pressure": "Customer deadline",
    "subcontractor_requirement_pressure": "Subcontractor requirement",
    "data_handling_uncertainty": "Data handling uncertainty",
}

EXPLICIT_COMPLIANCE_RE = re.compile(
    r"\b(cmmc|dfars|nist\s*800|800-171|sprs|fedramp|itar)\b",
    re.I,
)

# (pattern, weight, category)
PRESSURE_PATTERNS: List[Tuple[str, int, str]] = [
    (r"\bcustomer (sent|asked|requires?|wants?).{0,40}\b(security|questionnaire|mfa|documentation|cyber)\b", 18, "customer_security_pressure"),
    (r"\bcustomer (sent|asked).{0,30}\bquestionnaire\b", 18, "security_questionnaire_pressure"),
    (r"\b(customer|client) (cybersecurity|security) (requirements?|controls)\b", 16, "customer_security_pressure"),
    (r"\bcustomer (audit|assessment) (request|required)\b", 16, "audit_preparation_pressure"),
    (r"\b(customer|client) (deadline|due date|by friday)\b", 14, "customer_deadline_pressure"),
    (r"\bprime contractor (asked|sent|requires?)\b", 16, "subcontractor_requirement_pressure"),
    (r"\bprime contractor.{0,30}\b(mfa|questionnaire|documentation)\b", 16, "subcontractor_requirement_pressure"),
    (r"\bvendor onboarding\b", 16, "vendor_onboarding_pressure"),
    (r"\bsupplier onboarding\b", 16, "vendor_onboarding_pressure"),
    (r"\bsupplier (security|questionnaire|requirements?)\b", 14, "supplier_security_review"),
    (r"\bsubcontractor security\b", 14, "subcontractor_requirement_pressure"),
    (r"\bprocurement security\b", 14, "procurement_security_requirement"),
    (r"\bprocurement.{0,30}\b(requirements?|questionnaire)\b", 14, "procurement_security_requirement"),
    (r"\bsecurity questionnaire\b", 16, "security_questionnaire_pressure"),
    (r"\bvendor security (form|questionnaire|review)\b", 16, "vendor_onboarding_pressure"),
    (r"\bcyber insurance (questionnaire|requirements?|evidence)\b", 16, "insurance_compliance_pressure"),
    (r"\binsurance (security|cyber) (requirements?|questionnaire)\b", 14, "insurance_compliance_pressure"),
    (r"\bneed (evidence|documentation) (for|to)\b", 14, "evidence_request_pressure"),
    (r"\bevidence request\b", 14, "evidence_request_pressure"),
    (r"\b(what|which) policies? do we need\b", 14, "policy_request_pressure"),
    (r"\bsecurity policies? (needed|required)\b", 14, "policy_request_pressure"),
    (r"\b(mfa|multi.?factor).{0,40}\b(require|required|asked|need)\b", 14, "mfa_requirement_pressure"),
    (r"\b(ai act|eu ai act|ai governance|model card|risk assessment)\b", 14, "ai_governance_pressure"),
    (r"\bai (compliance|governance|questionnaire)\b", 14, "ai_governance_pressure"),
    (r"\bwhat (paperwork|documentation) (is )?(needed|required)\b", 14, "documentation_uncertainty"),
    (r"\bwhat applies to (us|our)\b", 12, "documentation_uncertainty"),
    (r"\bwhat do we need\b", 10, "documentation_uncertainty"),
    (r"\baudit (documentation|prep|preparation)\b", 12, "audit_preparation_pressure"),
    (r"\bneed audit\b", 12, "audit_preparation_pressure"),
    (r"\bwe store (technical )?drawings\b", 12, "data_handling_uncertainty"),
    (r"\b(cui|controlled unclassified|fci)\b", 12, "data_handling_uncertainty"),
    (r"\bgovernment customer.{0,30}\b(documentation|security|questionnaire)\b", 14, "customer_security_pressure"),
    (r"\b(contract|rfp).{0,30}\b(security|cyber|compliance)\b", 12, "procurement_security_requirement"),
    (r"\b(flowdown|flow.?down).{0,25}\b(security|requirements)\b", 12, "subcontractor_requirement_pressure"),
    (r"\bimplementation (burden|pressure|uncertain)\b", 10, "documentation_uncertainty"),
    (r"\bpartial (spreadsheet|policies|screenshots)\b", 10, "evidence_request_pressure"),
]

LIKELY_EVIDENCE_BY_CATEGORY: Dict[str, List[str]] = {
    "customer_security_pressure": ["Customer security questionnaire", "Email requirements", "Screenshots of controls"],
    "vendor_onboarding_pressure": ["Vendor security form", "Supplier onboarding packet", "Attestation letters"],
    "security_questionnaire_pressure": ["SIG/CAIQ-style questionnaire", "Spreadsheet responses", "Policy excerpts"],
    "insurance_compliance_pressure": ["Cyber insurance application", "Control attestations"],
    "evidence_request_pressure": ["Policy PDFs", "Screenshots", "Partial SSP fragments"],
    "policy_request_pressure": ["Draft policies", "Acceptable use / access control docs"],
    "mfa_requirement_pressure": ["Identity/access policy", "MFA configuration evidence"],
    "supplier_security_review": ["Supplier security review form", "Subcontract flowdown"],
    "ai_governance_pressure": ["AI risk assessment", "Model documentation", "Governance policy draft"],
    "documentation_uncertainty": ["Messy partial files", "Unknown gap list"],
    "audit_preparation_pressure": ["Audit evidence folder", "Control mapping spreadsheets"],
    "data_handling_uncertainty": ["CUI handling procedures", "Technical data inventory"],
}

FRAMEWORK_HINTS: List[Tuple[str, str]] = [
    (r"\b(cmmc|dfars|800-171|sprs|dod)\b", "CMMC / DFARS / NIST 800-171 may apply"),
    (r"\b(fedramp|federal|government contract)\b", "Federal contracting controls may apply"),
    (r"\b(cyber insurance|soc 2|iso)\b", "Insurance or assurance framework pressure"),
    (r"\b(ai act|eu ai)\b", "AI governance / EU AI Act pressure"),
    (r"\b(vendor|supplier|prime)\b", "Flowdown security requirements likely"),
]


def _score_patterns(blob: str, patterns: List[Tuple[str, int, str]]) -> Tuple[Dict[str, int], List[str]]:
    scores = {c: 0 for c in SIGNAL_CATEGORIES}
    hits: List[str] = []
    for pattern, weight, category in patterns:
        if category not in scores:
            continue
        if re.search(pattern, blob, re.I):
            scores[category] += weight
            hits.append(category)
    return scores, hits


def score_operational_pressure(title: str, body: str = "") -> Dict[str, Any]:
    """Score compliance-adjacent operational pressure (pre-explicit-compliance)."""
    blob = f"{title}\n{body}".strip().lower()
    if not blob.strip():
        return _empty_result()

    category_scores, pressure_hits = _score_patterns(blob, PRESSURE_PATTERNS)
    hit_set = list(dict.fromkeys(pressure_hits))

    total_signal = sum(category_scores.values())
    entanglement = min(100, total_signal + len(hit_set) * 4)
    paperwork = min(
        100,
        category_scores.get("security_questionnaire_pressure", 0) * 2
        + category_scores.get("evidence_request_pressure", 0) * 2
        + category_scores.get("policy_request_pressure", 0) * 2
        + category_scores.get("vendor_onboarding_pressure", 0)
        + category_scores.get("documentation_uncertainty", 0)
        + 8 * len([c for c in hit_set if c in ("security_questionnaire_pressure", "evidence_request_pressure")]),
    )

    primary = "none"
    if category_scores:
        primary = max(category_scores.items(), key=lambda x: x[1])[0]
        if category_scores[primary] < 8:
            primary = "none"

    explicit_compliance = bool(EXPLICIT_COMPLIANCE_RE.search(blob))
    has_first_person = bool(re.search(r"\b(we|our|my|i|us)\b", blob))
    pre_compliance = (
        not explicit_compliance
        and entanglement >= 28
        and has_first_person
        and primary != "none"
    ) or (
        entanglement >= 45
        and has_first_person
        and primary in (
            "customer_security_pressure",
            "vendor_onboarding_pressure",
            "security_questionnaire_pressure",
            "insurance_compliance_pressure",
            "evidence_request_pressure",
            "policy_request_pressure",
        )
    )

    ui_badges: List[str] = []
    for cat, score in sorted(category_scores.items(), key=lambda x: -x[1]):
        if score >= 10 and UI_BADGE_LABELS.get(cat):
            label = UI_BADGE_LABELS[cat]
            if label not in ui_badges:
                ui_badges.append(label)
    if paperwork >= 40 and "Likely paperwork" not in ui_badges:
        ui_badges.append("Likely paperwork")
    if entanglement >= 35 and "Operational entanglement" not in ui_badges:
        ui_badges.append("Operational entanglement")

    likely_evidence: List[str] = []
    if primary != "none":
        likely_evidence.extend(LIKELY_EVIDENCE_BY_CATEGORY.get(primary, [])[:3])
    for cat in hit_set[:4]:
        for item in LIKELY_EVIDENCE_BY_CATEGORY.get(cat, [])[:2]:
            if item not in likely_evidence:
                likely_evidence.append(item)

    likely_frameworks: List[str] = []
    for pattern, hint in FRAMEWORK_HINTS:
        if re.search(pattern, blob, re.I) and hint not in likely_frameworks:
            likely_frameworks.append(hint)
    if not likely_frameworks and pre_compliance:
        likely_frameworks.append("Framework may emerge after questionnaire review (CMMC/DFARS/NIST possible)")

    selection_rationale = _build_selection_rationale(
        primary=primary,
        category_scores=category_scores,
        entanglement=entanglement,
        paperwork=paperwork,
        pre_compliance=pre_compliance,
        explicit_compliance=explicit_compliance,
    )

    return {
        "operational_pressure_score": entanglement,
        "paperwork_likelihood_score": paperwork,
        "signal_categories": category_scores,
        "pressure_hits": hit_set,
        "primary_pressure": primary,
        "ui_badges": ui_badges[:10],
        "selection_rationale": selection_rationale,
        "has_pre_compliance_entanglement": pre_compliance,
        "has_operational_entanglement": entanglement >= 32 and has_first_person,
        "explicit_compliance_language": explicit_compliance,
        "likely_evidence": likely_evidence[:6],
        "likely_frameworks": likely_frameworks[:5],
        "future_compliance_burden": _future_burden_note(primary, likely_frameworks),
    }


def _build_selection_rationale(
    *,
    primary: str,
    category_scores: Dict[str, int],
    entanglement: int,
    paperwork: int,
    pre_compliance: bool,
    explicit_compliance: bool,
) -> str:
    parts: List[str] = []
    if pre_compliance:
        parts.append("Pre-compliance operational entanglement — customer/vendor pressure before explicit CMMC talk.")
    elif explicit_compliance:
        parts.append("Operational pressure with explicit compliance keywords present.")
    else:
        parts.append("Operational friction signals detected in plain language.")
    if primary != "none":
        parts.append(f"Primary pressure: {UI_BADGE_LABELS.get(primary, primary.replace('_', ' '))}.")
    top = sorted(category_scores.items(), key=lambda x: -x[1])[:3]
    if top:
        parts.append(
            "Signals: "
            + ", ".join(f"{UI_BADGE_LABELS.get(k, k)} ({v})" for k, v in top if v > 0)
        )
    parts.append(f"Entanglement {entanglement}/100 · paperwork likelihood {paperwork}/100.")
    return " ".join(parts)


def _future_burden_note(primary: str, frameworks: List[str]) -> str:
    if primary in ("customer_security_pressure", "vendor_onboarding_pressure", "security_questionnaire_pressure"):
        return "Likely evolving into security questionnaire + policy + evidence gap work."
    if primary == "ai_governance_pressure":
        return "May require AI governance documentation beyond traditional CMMC."
    if frameworks:
        return frameworks[0]
    return "Documentation and evidence gaps likely once requirements are clarified."


def _empty_result() -> Dict[str, Any]:
    return {
        "operational_pressure_score": 0,
        "paperwork_likelihood_score": 0,
        "signal_categories": {c: 0 for c in SIGNAL_CATEGORIES},
        "pressure_hits": [],
        "primary_pressure": "none",
        "ui_badges": [],
        "selection_rationale": "",
        "has_pre_compliance_entanglement": False,
        "has_operational_entanglement": False,
        "explicit_compliance_language": False,
        "likely_evidence": [],
        "likely_frameworks": [],
        "future_compliance_burden": "",
    }

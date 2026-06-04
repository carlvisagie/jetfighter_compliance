"""Compliance-domain detector and per-domain gap rule packs.

Background
==========

Before this change, ``gaps.detect_gaps`` ran one CMMC/NIST-flavoured
rule set against every project. A DOT/FMCSA carrier would see "missing
SSP/POA&M" rather than the actually-relevant "missing Driver
Qualification File" — meaning the gap output added almost no value
for the largest non-cybersecurity audience the platform serves.

This module supplies:

* :func:`detect_compliance_domain` — a low-cost text + classification
  heuristic that picks the most likely primary compliance domain for
  a project (``CMMC``, ``DOT_FMCSA``, ``EU_DPP``, ``HIPAA``,
  ``general``).
* A per-domain registry of gap rules so each domain can carry its own
  vocabulary of "what real evidence looks like for this audit".
* A shared "universal" rule pack with basics every compliance program
  cares about (asset inventory, backup, vendor management).

Each rule can be satisfied two ways:

1. A matching ``document_type`` is present in the project's
   ``document_inventory`` (existing behaviour).
2. One of the rule's ``text_signals`` is found in any of the project's
   extracted text snippets (new — helps when the classifier picks a
   generic type but the text itself proves coverage).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

Domain = str  # "CMMC" | "DOT_FMCSA" | "EU_DPP" | "HIPAA" | "general"

KNOWN_DOMAINS: Tuple[Domain, ...] = (
    "CMMC",
    "DOT_FMCSA",
    "EU_DPP",
    "HIPAA",
    "general",
)


# --- domain detection -------------------------------------------------------


# Keyword signals — tuned for high precision; the count is the *strength*
# contribution to the domain score. Higher = stronger signal.
_DOMAIN_SIGNALS: Dict[Domain, List[Tuple[re.Pattern[str], int]]] = {
    "CMMC": [
        (re.compile(r"\bcmmc\b",                       re.I), 5),
        (re.compile(r"nist\s*sp?\s*800[-\s]?171",      re.I), 5),
        (re.compile(r"nist\s*sp?\s*800[-\s]?53",       re.I), 4),
        (re.compile(r"\bdfars\b",                      re.I), 4),
        (re.compile(r"\bcui\b",                        re.I), 4),
        (re.compile(r"controlled\s+unclassified\s+information", re.I), 5),
        (re.compile(r"\bssp\b|system\s+security\s+plan",      re.I), 3),
        (re.compile(r"poa\s*&\s*m|plan\s+of\s+action",        re.I), 3),
        (re.compile(r"defense\s+industrial\s+base|\bdib\b",   re.I), 3),
        (re.compile(r"federal\s+contract\s+information|\bfci\b", re.I), 3),
    ],
    "DOT_FMCSA": [
        (re.compile(r"\bfmcsa\b",                       re.I), 5),
        (re.compile(r"\busdot\b",                       re.I), 5),
        (re.compile(r"\bcfr\s*4[59]\b|49\s*cfr",        re.I), 5),
        (re.compile(r"driver\s+qualif",                 re.I), 5),
        (re.compile(r"\bdqf\b",                         re.I), 4),
        (re.compile(r"hours\s+of\s+service|\bhos\b",    re.I), 4),
        (re.compile(r"\beld\b|electronic\s+logging",    re.I), 4),
        (re.compile(r"\bmvr\b|motor\s+vehicle\s+record", re.I), 4),
        (re.compile(r"\bcdl\b|commercial\s+driver",     re.I), 4),
        (re.compile(r"\bdot\s+physical|medical\s+examiner", re.I), 4),
        (re.compile(r"\bbmc[-\s]?91\b|\bmcs[-\s]?90\b", re.I), 4),
        (re.compile(r"operating\s+authority|\bmc\s*number", re.I), 4),
        (re.compile(r"\bdvir\b|vehicle\s+inspection",   re.I), 3),
        (re.compile(r"drug\s+and\s+alcohol\s+program",  re.I), 4),
    ],
    "EU_DPP": [
        (re.compile(r"digital\s+product\s+passport",    re.I), 6),
        (re.compile(r"\bdpp\b",                         re.I), 3),
        (re.compile(r"\bespr\b|ecodesign\s+for\s+sustainable", re.I), 5),
        (re.compile(r"\beudr\b|eu\s+deforestation",     re.I), 5),
        (re.compile(r"\bcbam\b|carbon\s+border\s+adjust", re.I), 4),
        (re.compile(r"product\s+passport\s+regulation", re.I), 5),
        (re.compile(r"supply\s+chain\s+traceability",   re.I), 3),
        (re.compile(r"material\s+composition|substance\s+of\s+concern", re.I), 3),
    ],
    "HIPAA": [
        (re.compile(r"\bhipaa\b",                       re.I), 5),
        (re.compile(r"\bphi\b",                         re.I), 4),
        (re.compile(r"protected\s+health\s+information", re.I), 5),
        (re.compile(r"business\s+associate\s+agreement|\bbaa\b", re.I), 4),
        (re.compile(r"\bhitech\b",                      re.I), 3),
        (re.compile(r"\b45\s*cfr\s*16[0-9]",            re.I), 4),
        (re.compile(r"covered\s+entity",                re.I), 3),
    ],
}


@dataclass
class DomainResult:
    domain:     Domain                 = "general"
    confidence: float                  = 0.0
    score:      int                    = 0
    runner_up:  Domain                 = "general"
    runner_up_score: int               = 0
    signals:    Dict[Domain, List[str]] = field(default_factory=dict)


def detect_compliance_domain(
    profile: Optional[Dict[str, Any]] = None,
    *,
    texts: Optional[Iterable[str]] = None,
    classifications: Optional[Iterable[Dict[str, Any]]] = None,
) -> DomainResult:
    """Pick the primary compliance domain for this project.

    Heuristic: scan extracted text + classification signals for
    domain-specific keywords; the domain with the highest weighted
    score wins. Confidence is a normalised ratio of leader vs total
    signal weight. Returns ``general`` (with confidence 0) if nothing
    matches.
    """
    blobs: List[str] = []
    if texts:
        for t in texts:
            if t:
                blobs.append(str(t))
    if profile:
        for row in profile.get("document_inventory") or []:
            sig = " ".join(row.get("signals") or [])
            f   = row.get("file") or ""
            t   = row.get("document_type") or ""
            blobs.append(f"{f} {t} {sig}")
        for ent in profile.get("compliance_references") or []:
            v = ent.get("value")
            if v:
                blobs.append(str(v))
    if classifications:
        for clf in classifications:
            blobs.append(" ".join((clf or {}).get("signals") or []))
            blobs.append((clf or {}).get("source_file") or "")

    text = "\n".join(b for b in blobs if b).lower()
    if not text.strip():
        return DomainResult()

    scores:  Dict[Domain, int]         = {}
    matches: Dict[Domain, List[str]]   = {}
    for domain, patterns in _DOMAIN_SIGNALS.items():
        s     = 0
        hits  = []
        for rx, weight in patterns:
            m = rx.search(text)
            if m:
                s += weight
                hits.append(m.group(0))
        if s:
            scores[domain]   = s
            matches[domain]  = hits[:6]

    if not scores:
        return DomainResult(signals={})

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_domain, top_score = ranked[0]
    total_score = sum(scores.values())
    confidence  = min(0.99, round(top_score / max(1, total_score), 3))
    runner      = ranked[1] if len(ranked) > 1 else ("general", 0)
    return DomainResult(
        domain          = top_domain,
        confidence      = confidence,
        score           = top_score,
        runner_up       = runner[0],
        runner_up_score = runner[1],
        signals         = matches,
    )


# --- rule pack registry -----------------------------------------------------


# Universal rules — every compliance program cares about these regardless
# of domain. Mirror of legacy GAP_DEFS that aren't framework-specific.
UNIVERSAL_RULES: List[Dict[str, Any]] = [
    {
        "gap_id":      "asset_inventory",
        "label":       "Asset inventory",
        "explanation": "A list of systems, devices, or software in scope.",
        "why":         "You cannot protect (or audit) what you have not inventoried.",
        "catalog_key": "policy_general",
        "priority":    "high",
        "doc_types":   {"asset_inventory"},
        "text_signals": ("asset inventory", "device inventory", "hardware inventory"),
    },
    {
        "gap_id":      "vendor_policy",
        "label":       "Vendor / third-party management policy",
        "explanation": "How you evaluate and monitor suppliers that touch your environment.",
        "why":         "Supply chain risk is a frequent audit focus across frameworks.",
        "catalog_key": "vendor_policy",
        "priority":    "medium",
        "doc_types":   {"vendor_document", "policy"},
        "text_signals": ("vendor management", "supplier security", "third-party"),
    },
    {
        "gap_id":      "backup_evidence",
        "label":       "Backup and recovery evidence",
        "explanation": "Backup policy, job logs, or restore test results.",
        "why":         "Recovery capability is required for resilience controls.",
        "catalog_key": "policy_general",
        "priority":    "medium",
        "doc_types":   {"backup_evidence"},
        "text_signals": ("backup policy", "restore test", "recovery test"),
    },
    {
        "gap_id":      "incident_response",
        "label":       "Incident response plan or evidence",
        "explanation": "IR plan, playbooks, or tabletop exercise records.",
        "why":         "Shows you can detect and respond to events.",
        "catalog_key": "policy_general",
        "priority":    "medium",
        "doc_types":   {"incident_response"},
        "text_signals": ("incident response", "ir plan", "tabletop"),
    },
]


CMMC_RULES: List[Dict[str, Any]] = [
    {
        "gap_id":      "mfa_evidence",
        "label":       "Multi-factor authentication evidence",
        "explanation": "Screenshots or exports showing MFA is enforced help prove access control.",
        "why":         "CMMC IA.L2-3.5.3 expects MFA for privileged accounts and remote access.",
        "catalog_key": "mfa",
        "priority":    "high",
        "doc_types":   {"mfa_evidence", "screenshot"},
        "text_signals": ("multi-factor", "mfa enforced", "two-factor"),
    },
    {
        "gap_id":      "training_record",
        "label":       "Security awareness training record",
        "explanation": "A completion report or LMS export shows personnel training.",
        "why":         "CMMC AT.L2-3.2.1 requires security awareness training.",
        "catalog_key": "training",
        "priority":    "high",
        "doc_types":   {"training_record"},
        "text_signals": ("training completed", "awareness training", "knowbe4"),
    },
    {
        "gap_id":      "vulnerability_evidence",
        "label":       "Vulnerability scan or patch evidence",
        "explanation": "Scan reports or patch tracking for in-scope systems.",
        "why":         "CMMC RA.L2-3.11.2 requires vulnerability scans of organisational systems.",
        "catalog_key": "policy_general",
        "priority":    "high",
        "doc_types":   {"vulnerability_report"},
        "text_signals": ("vulnerability scan", "nessus", "qualys", "patch report"),
    },
    {
        "gap_id":      "access_control",
        "label":       "Access control evidence",
        "explanation": "User listings, access reviews, or privileged access controls.",
        "why":         "CMMC AC.L2-3.1.* family — access control is central.",
        "catalog_key": "mfa",
        "priority":    "high",
        "doc_types":   {"access_control_evidence"},
        "text_signals": ("access control", "user access review", "privileged access"),
    },
    {
        "gap_id":      "ssp_poam",
        "label":       "SSP or POA&M reference",
        "explanation": "System Security Plan or Plan of Action and Milestones.",
        "why":         "Required for any NIST 800-171 / CMMC self-assessment.",
        "catalog_key": "ssp_section",
        "priority":    "medium",
        "doc_types":   {"ssp", "poam"},
        "text_signals": ("system security plan", "poa&m", "plan of action"),
    },
]


DOT_FMCSA_RULES: List[Dict[str, Any]] = [
    {
        "gap_id":      "driver_qualification_file",
        "label":       "Driver Qualification File (DQF)",
        "explanation": "Driver application, MVR, road-test certificate, medical card, and annual review per 49 CFR 391.",
        "why":         "Every CDL driver must have a DQF on file; this is the first thing FMCSA audits.",
        "catalog_key": "dqf",
        "priority":    "high",
        "doc_types":   {"driver_qualification_file"},
        "text_signals": ("driver qualification", "dqf", "mvr", "road test"),
    },
    {
        "gap_id":      "hours_of_service_logs",
        "label":       "Hours of Service / ELD records",
        "explanation": "Electronic logging device exports proving HOS compliance per 49 CFR 395.",
        "why":         "HOS violations are the leading cause of FMCSA OOS orders.",
        "catalog_key": "hos_eld",
        "priority":    "high",
        "doc_types":   {"hos_logs", "eld_export"},
        "text_signals": ("hours of service", "eld export", "electronic logging"),
    },
    {
        "gap_id":      "drug_alcohol_program",
        "label":       "Drug and alcohol testing program evidence",
        "explanation": "Consortium membership, pre-employment / random testing records per 49 CFR 382.",
        "why":         "Required for every motor carrier employing CDL drivers.",
        "catalog_key": "dot_drug_alcohol",
        "priority":    "high",
        "doc_types":   {"drug_alcohol_program"},
        "text_signals": ("drug and alcohol", "random testing", "consortium"),
    },
    {
        "gap_id":      "vehicle_inspection_records",
        "label":       "Vehicle inspection records (DVIRs + annual)",
        "explanation": "Daily DVIRs and annual inspection certificates per 49 CFR 396.",
        "why":         "Maintenance records prove the fleet is roadworthy at audit.",
        "catalog_key": "dot_vehicle_inspection",
        "priority":    "high",
        "doc_types":   {"vehicle_inspection"},
        "text_signals": ("dvir", "annual inspection", "vehicle maintenance"),
    },
    {
        "gap_id":      "dot_medical_exam",
        "label":       "DOT physical / medical examiner certificates",
        "explanation": "Current medical examiner certificates for each driver per 49 CFR 391.41.",
        "why":         "Expired medical cards are an instant out-of-service violation.",
        "catalog_key": "dot_medical",
        "priority":    "high",
        "doc_types":   {"dot_medical_exam"},
        "text_signals": ("dot physical", "medical examiner", "medical card"),
    },
    {
        "gap_id":      "operating_authority",
        "label":       "Operating authority (USDOT / MC number)",
        "explanation": "USDOT registration, MC number, and BOC-3 process-agent designation.",
        "why":         "Required before any interstate commerce.",
        "catalog_key": "dot_authority",
        "priority":    "high",
        "doc_types":   {"operating_authority"},
        "text_signals": ("usdot number", "mc number", "operating authority", "boc-3"),
    },
    {
        "gap_id":      "insurance_certificate",
        "label":       "Insurance filings (BMC-91 / MCS-90)",
        "explanation": "Proof of public liability insurance filed with FMCSA.",
        "why":         "Mandatory continuous coverage requirement.",
        "catalog_key": "dot_insurance",
        "priority":    "medium",
        "doc_types":   {"insurance_certificate"},
        "text_signals": ("bmc-91", "mcs-90", "public liability"),
    },
]


EU_DPP_RULES: List[Dict[str, Any]] = [
    {
        "gap_id":      "product_passport_registration",
        "label":       "Digital Product Passport (DPP) registration",
        "explanation": "Registration with the EU DPP system and unique product identifier mapping.",
        "why":         "ESPR-regulated products cannot be placed on the EU market without a DPP.",
        "catalog_key": "eu_dpp_registration",
        "priority":    "high",
        "doc_types":   {"dpp_registration"},
        "text_signals": ("digital product passport", "dpp registration"),
    },
    {
        "gap_id":      "supply_chain_traceability",
        "label":       "Supply-chain traceability records",
        "explanation": "Upstream sourcing data linking raw materials to finished product.",
        "why":         "Required for EUDR / DPP transparency obligations.",
        "catalog_key": "eu_dpp_traceability",
        "priority":    "high",
        "doc_types":   {"supply_chain_traceability"},
        "text_signals": ("supply chain traceability", "chain of custody material"),
    },
    {
        "gap_id":      "material_composition",
        "label":       "Material composition declaration",
        "explanation": "Bill of materials with substances-of-concern disclosure.",
        "why":         "Mandatory under ESPR / RoHS / REACH alignment.",
        "catalog_key": "eu_dpp_materials",
        "priority":    "medium",
        "doc_types":   {"material_composition"},
        "text_signals": ("material composition", "substance of concern", "bill of materials"),
    },
    {
        "gap_id":      "durability_repairability",
        "label":       "Durability / repairability data",
        "explanation": "Reliability, spare-parts availability, and repair index information.",
        "why":         "ESPR durability + repairability requirements.",
        "catalog_key": "eu_dpp_durability",
        "priority":    "medium",
        "doc_types":   {"durability_repairability"},
        "text_signals": ("repairability index", "spare parts", "durability"),
    },
]


HIPAA_RULES: List[Dict[str, Any]] = [
    {
        "gap_id":      "hipaa_baa",
        "label":       "Business Associate Agreement(s)",
        "explanation": "Signed BAAs with every vendor that touches PHI.",
        "why":         "45 CFR 164.502(e) requires BAAs before sharing PHI.",
        "catalog_key": "hipaa_baa",
        "priority":    "high",
        "doc_types":   {"baa"},
        "text_signals": ("business associate agreement", "baa signed"),
    },
    {
        "gap_id":      "hipaa_risk_assessment",
        "label":       "HIPAA security risk assessment",
        "explanation": "Documented Security Rule risk analysis per 45 CFR 164.308(a)(1).",
        "why":         "OCR investigations almost always start with the risk analysis.",
        "catalog_key": "hipaa_risk",
        "priority":    "high",
        "doc_types":   {"hipaa_risk_assessment"},
        "text_signals": ("hipaa security risk", "security risk analysis"),
    },
    {
        "gap_id":      "hipaa_breach_procedures",
        "label":       "Breach notification procedure",
        "explanation": "Documented procedure for breach assessment and notification.",
        "why":         "45 CFR 164.404-410 mandates the procedure exists in writing.",
        "catalog_key": "hipaa_breach",
        "priority":    "medium",
        "doc_types":   {"breach_procedure"},
        "text_signals": ("breach notification", "breach assessment"),
    },
    {
        "gap_id":      "hipaa_workforce_training",
        "label":       "Workforce HIPAA training records",
        "explanation": "Evidence that workforce members have completed HIPAA training.",
        "why":         "45 CFR 164.530(b) requires periodic workforce training.",
        "catalog_key": "training",
        "priority":    "high",
        "doc_types":   {"training_record"},
        "text_signals": ("hipaa training", "phi training"),
    },
]


_DOMAIN_RULES: Dict[Domain, List[Dict[str, Any]]] = {
    "CMMC":      CMMC_RULES,
    "DOT_FMCSA": DOT_FMCSA_RULES,
    "EU_DPP":    EU_DPP_RULES,
    "HIPAA":     HIPAA_RULES,
    "general":   [],
}


def rules_for_domain(domain: Domain) -> List[Dict[str, Any]]:
    """Return the domain pack plus the universal pack, de-duplicated by gap_id."""
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for rule in _DOMAIN_RULES.get(domain, []) + UNIVERSAL_RULES:
        gid = rule.get("gap_id")
        if not gid or gid in seen:
            continue
        seen.add(gid)
        out.append(rule)
    return out

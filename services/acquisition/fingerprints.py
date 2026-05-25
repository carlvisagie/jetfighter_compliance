"""Operational fingerprints from paperwork, intake, and onboarding behavior."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

COMPLIANCE_TERMS = re.compile(
    r"\b(cmmc|as9100|iso\s*9001|itar|dfars|nist|audit|quality|compliance|traceability|"
    r"document control|supplier|nadcap|faro|caliper|inspection)\b",
    re.I,
)

DOC_TYPE_PATTERNS = {
    "policy": re.compile(r"\b(policy|procedure|sop|manual)\b", re.I),
    "org_chart": re.compile(r"\b(org\s*chart|organization)\b", re.I),
    "quality": re.compile(r"\b(quality|qa|qc)\b", re.I),
    "audit": re.compile(r"\b(audit|assessment|gap)\b", re.I),
    "contract": re.compile(r"\b(contract|flowdown|dfars)\b", re.I),
    "training": re.compile(r"\b(training|awareness)\b", re.I),
}


def extract_ref_from_message(message: str) -> str:
    m = re.search(r"\[ref:([^\]]+)\]", message or "")
    return m.group(1).strip() if m else ""


def fingerprint_filename(filename: str) -> Dict[str, Any]:
    name = filename or ""
    lower = name.lower()
    categories = [k for k, pat in DOC_TYPE_PATTERNS.items() if pat.search(lower)]
    naming_consistency = "structured" if re.search(r"^\d{2}[-_]|v\d|rev\d|final", lower) else "informal"
    compliance_refs = list(set(COMPLIANCE_TERMS.findall(name)))
    return {
        "filename": name,
        "categories": categories,
        "naming_consistency": naming_consistency,
        "compliance_refs": compliance_refs,
        "extension": Path(name).suffix.lower(),
    }


def fingerprint_intake(intake: Dict[str, Any]) -> Dict[str, Any]:
    flags = intake.get("external_flags") or {}
    active_ext = [k for k, v in flags.items() if v]
    notes = (intake.get("notes") or "").lower()
    company = intake.get("company") or ""
    complexity = len(active_ext)
    if complexity >= 4:
        operational_complexity = "high"
    elif complexity >= 2:
        operational_complexity = "medium"
    else:
        operational_complexity = "low"
    maturity = "developing"
    if active_ext and len(notes) > 40:
        maturity = "structured"
    if not company:
        maturity = "early"
    gaps = []
    if not notes:
        gaps.append("no intake notes")
    if "cmmc" in notes and not flags.get("cmmc_l2_c3pao"):
        gaps.append("cmmc mentioned without c3pao flag")
    return {
        "external_program_count": complexity,
        "active_external_programs": active_ext,
        "operational_complexity": operational_complexity,
        "intake_notes_length": len(intake.get("notes") or ""),
        "has_company": bool(company),
        "gaps": gaps,
        "organizational_maturity_hint": maturity,
    }


def fingerprint_inquiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    msg = (payload.get("message") or "").lower()
    subject = (payload.get("subject") or "").lower()
    ref = extract_ref_from_message(payload.get("message") or "")
    urgency_terms = ["urgent", "asap", "deadline", "audit", "customer request", "prime", "due"]
    urgency_hits = [t for t in urgency_terms if t in msg or t in subject]
    trust_terms = ["upload", "documentation", "policies", "readiness", "review"]
    trust_hits = [t for t in trust_terms if t in msg]
    return {
        "lead_ref": ref,
        "urgency_indicators": urgency_hits,
        "trust_orientation_indicators": trust_hits,
        "message_length": len(payload.get("message") or ""),
        "subject": payload.get("subject") or "",
    }


def scan_evidence_dir(project_id: str, projects_root: Path) -> Dict[str, Any]:
    edir = projects_root / project_id / "evidence"
    files: List[Dict[str, Any]] = []
    if not edir.exists():
        return {"file_count": 0, "categories": [], "naming_scores": [], "compliance_refs": []}
    for f in edir.iterdir():
        if f.is_file() and f.name != "00_manifest.txt":
            files.append(fingerprint_filename(f.name))
    cats: List[str] = []
    refs: List[str] = []
    naming = []
    for fp in files:
        cats.extend(fp.get("categories") or [])
        refs.extend(fp.get("compliance_refs") or [])
        naming.append(fp.get("naming_consistency"))
    structured = naming.count("structured")
    return {
        "file_count": len(files),
        "categories": list(dict.fromkeys(cats)),
        "compliance_refs": list(dict.fromkeys(refs)),
        "structured_naming_ratio": (structured / len(naming)) if naming else 0.0,
        "files": files[:50],
    }


def build_profiles(
    intake_fp: Optional[Dict[str, Any]] = None,
    evidence_fp: Optional[Dict[str, Any]] = None,
    inquiry_fp: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    intake_fp = intake_fp or {}
    evidence_fp = evidence_fp or {}
    inquiry_fp = inquiry_fp or {}

    doc_score = 20
    if evidence_fp.get("file_count", 0) > 0:
        doc_score += 25
    doc_score += int((evidence_fp.get("structured_naming_ratio") or 0) * 30)
    doc_score += min(20, len(evidence_fp.get("categories") or []) * 5)
    doc_score = min(100, doc_score)

    org_score = 30
    if intake_fp.get("has_company"):
        org_score += 15
    if intake_fp.get("organizational_maturity_hint") == "structured":
        org_score += 25
    elif intake_fp.get("organizational_maturity_hint") == "developing":
        org_score += 12
    org_score -= len(intake_fp.get("gaps") or []) * 5
    org_score = max(0, min(100, org_score))

    comp_score = 25
    comp_score += min(30, len(evidence_fp.get("compliance_refs") or []) * 8)
    comp_score += min(20, len(inquiry_fp.get("trust_orientation_indicators") or []) * 5)
    comp_score += min(25, len(inquiry_fp.get("urgency_indicators") or []) * 8)
    if intake_fp.get("external_program_count", 0) >= 2:
        comp_score += 15
    comp_score = min(100, comp_score)

    return {
        "organizational_maturity_profile": {
            "score": org_score,
            "complexity": intake_fp.get("operational_complexity", "unknown"),
            "maturity_hint": intake_fp.get("organizational_maturity_hint", "unknown"),
            "gaps": intake_fp.get("gaps") or [],
        },
        "documentation_maturity_profile": {
            "score": doc_score,
            "file_count": evidence_fp.get("file_count", 0),
            "categories": evidence_fp.get("categories") or [],
            "structured_naming_ratio": evidence_fp.get("structured_naming_ratio", 0),
        },
        "compliance_readiness_profile": {
            "score": comp_score,
            "urgency_indicators": inquiry_fp.get("urgency_indicators") or [],
            "compliance_refs": evidence_fp.get("compliance_refs") or [],
            "active_programs": intake_fp.get("active_external_programs") or [],
        },
    }

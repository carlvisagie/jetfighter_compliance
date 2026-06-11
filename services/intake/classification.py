"""PATCH 13A-9: Intake/Project classification for operational purification.

Classifications:
- REAL: Genuine customer intakes
- TEST: Internal testing by operators
- VALIDATION: PATCH verification tests
- DEMO: Sales demonstrations
- INTERNAL: Internal audits and diagnostics
- REVIEW_REQUIRED: Unable to auto-classify

This module DOES NOT delete or modify any data.
It only adds classification metadata for visibility separation.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class IntakeClassification(str, Enum):
    REAL = "REAL"
    TEST = "TEST"
    VALIDATION = "VALIDATION"
    DEMO = "DEMO"
    INTERNAL = "INTERNAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# Patterns that indicate non-real intakes
TEST_EMAIL_PATTERNS = [
    r"@test\.",
    r"@example\.",
    r"@aegis\.example",
    r"@test\.keepyourcontracts\.com",
    r"@test\.jetfighter\.com",
    r"carlhvisagie@yahoo\.com",  # Operator's personal test email
]

VALIDATION_EMAIL_PATTERNS = [
    r"verify.*@",
    r"@.*verify",
    r"validation.*@",
    r"-verify@",
    r"audit-\d+.*@test\.",
]

VALIDATION_COMPANY_PATTERNS = [
    r"PATCH\d+",
    r"Verify\s+\d{8}",
    r"Verification$",
    r"^Audit\s+Test",
    r"Test\s+Company",
]

DEMO_COMPANY_PATTERNS = [
    r"Demo\s+Company",
    r"^Demo\s",
    r"Demonstration",
    r"Sample\s+Corp",
]

INTERNAL_EMAIL_PATTERNS = [
    r"@keepyourcontracts\.com$",
    r"@jetfighter\.com$",
]


def _root() -> Path:
    from ..config import DATA
    d = DATA / "intake_classification"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _classifications_path() -> Path:
    return _root() / "classifications.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _match_patterns(value: str, patterns: List[str]) -> bool:
    """Check if value matches any pattern (case-insensitive)."""
    if not value:
        return False
    for pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def auto_classify_intake(
    intake_id: str,
    company_name: str = "",
    contact_email: str = "",
    validation_mode: bool = False,
    source: str = "",
    notes: str = "",
) -> Tuple[IntakeClassification, str]:
    """
    Auto-classify an intake based on available signals.
    
    Returns (classification, reason).
    """
    email_lower = (contact_email or "").lower()
    company_lower = (company_name or "").lower()
    
    # 1. Explicit validation_mode flag
    if validation_mode:
        return IntakeClassification.VALIDATION, "validation_mode flag set"
    
    # 2. Check validation patterns first (most specific)
    if _match_patterns(email_lower, VALIDATION_EMAIL_PATTERNS):
        return IntakeClassification.VALIDATION, f"email matches validation pattern: {email_lower}"
    
    if _match_patterns(company_name, VALIDATION_COMPANY_PATTERNS):
        return IntakeClassification.VALIDATION, f"company name matches validation pattern: {company_name}"
    
    # 3. Check test patterns
    if _match_patterns(email_lower, TEST_EMAIL_PATTERNS):
        return IntakeClassification.TEST, f"email matches test pattern: {email_lower}"
    
    # 4. Check demo patterns
    if _match_patterns(company_name, DEMO_COMPANY_PATTERNS):
        return IntakeClassification.DEMO, f"company name matches demo pattern: {company_name}"
    
    # 5. Check internal patterns
    if _match_patterns(email_lower, INTERNAL_EMAIL_PATTERNS) and not _match_patterns(email_lower, TEST_EMAIL_PATTERNS):
        # Internal company email but not a test subdomain
        return IntakeClassification.INTERNAL, f"email matches internal pattern: {email_lower}"
    
    # 6. If no company name and suspicious email
    if not company_name or company_name.lower() in ("unknown", ""):
        if "@" not in email_lower or email_lower.endswith(".example"):
            return IntakeClassification.TEST, "unknown company with suspicious email"
    
    # 7. Default: likely real, but flag for review if low confidence
    # For now, any intake without test signals is marked REVIEW_REQUIRED
    # Operator can manually promote to REAL
    return IntakeClassification.REVIEW_REQUIRED, "no test signals detected - operator review recommended"


def load_classifications() -> Dict[str, Dict[str, Any]]:
    """Load all intake classifications."""
    path = _classifications_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_classifications(classifications: Dict[str, Dict[str, Any]]) -> None:
    """Save all intake classifications."""
    path = _classifications_path()
    path.write_text(json.dumps(classifications, indent=2), encoding="utf-8")


def get_classification(intake_id: str) -> Optional[Dict[str, Any]]:
    """Get classification for a specific intake."""
    return load_classifications().get(intake_id)


def set_classification(
    intake_id: str,
    classification: IntakeClassification,
    reason: str = "",
    *,
    auto: bool = True,
    operator_override: bool = False,
    operator_note: str = "",
) -> Dict[str, Any]:
    """
    Set classification for an intake.
    
    Does NOT modify the intake data itself - only stores classification metadata.
    """
    classifications = load_classifications()
    
    record = {
        "intake_id": intake_id,
        "classification": classification.value,
        "reason": reason,
        "auto_classified": auto,
        "operator_override": operator_override,
        "operator_note": operator_note,
        "classified_utc": _utc(),
    }
    
    classifications[intake_id] = record
    save_classifications(classifications)
    
    return record


def classify_all_intakes() -> Dict[str, Any]:
    """
    Auto-classify all intakes in the system.
    
    Does NOT modify intake data. Only creates classification records.
    """
    from .storage import list_intake_ids, load_intake_record
    
    results = {
        "classified": 0,
        "by_type": {
            "REAL": 0,
            "TEST": 0,
            "VALIDATION": 0,
            "DEMO": 0,
            "INTERNAL": 0,
            "REVIEW_REQUIRED": 0,
        },
        "intakes": [],
    }
    
    classifications = load_classifications()
    
    for intake_id in list_intake_ids():
        # Skip if already classified by operator
        existing = classifications.get(intake_id, {})
        if existing.get("operator_override"):
            cls = existing.get("classification", "REVIEW_REQUIRED")
            results["by_type"][cls] = results["by_type"].get(cls, 0) + 1
            results["intakes"].append({
                "intake_id": intake_id,
                "classification": cls,
                "reason": existing.get("reason", "operator override"),
                "skipped": True,
            })
            continue
        
        # Load intake record
        try:
            record = load_intake_record(intake_id)
        except Exception:
            record = {}
        
        company = record.get("company") or record.get("company_name") or ""
        email = record.get("email") or record.get("contact_email") or ""
        validation_mode = record.get("validation_mode", False)
        
        cls, reason = auto_classify_intake(
            intake_id,
            company_name=company,
            contact_email=email,
            validation_mode=validation_mode,
        )
        
        set_classification(intake_id, cls, reason, auto=True)
        
        results["classified"] += 1
        results["by_type"][cls.value] += 1
        results["intakes"].append({
            "intake_id": intake_id,
            "company": company,
            "email": email,
            "classification": cls.value,
            "reason": reason,
        })
    
    results["timestamp_utc"] = _utc()
    return results


def get_filtered_intakes(
    classification: Optional[IntakeClassification] = None,
    exclude_classifications: Optional[List[IntakeClassification]] = None,
) -> List[str]:
    """
    Get intake IDs filtered by classification.
    
    Args:
        classification: Only return intakes with this classification
        exclude_classifications: Exclude intakes with these classifications
    """
    from .storage import list_intake_ids
    
    classifications = load_classifications()
    exclude_set = set(c.value for c in (exclude_classifications or []))
    
    result = []
    for intake_id in list_intake_ids():
        cls_record = classifications.get(intake_id, {})
        cls = cls_record.get("classification", "REVIEW_REQUIRED")
        
        if classification and cls != classification.value:
            continue
        
        if cls in exclude_set:
            continue
        
        result.append(intake_id)
    
    return result


def get_real_only_intakes() -> List[str]:
    """Get only REAL customer intakes."""
    return get_filtered_intakes(classification=IntakeClassification.REAL)


def get_test_lab_intakes() -> List[str]:
    """Get TEST + VALIDATION + DEMO intakes for lab view."""
    classifications = load_classifications()
    lab_types = {"TEST", "VALIDATION", "DEMO"}
    
    from .storage import list_intake_ids
    
    return [
        intake_id for intake_id in list_intake_ids()
        if classifications.get(intake_id, {}).get("classification", "REVIEW_REQUIRED") in lab_types
    ]


def get_classification_summary() -> Dict[str, Any]:
    """Get summary of all classifications for operator dashboard."""
    classifications = load_classifications()
    
    summary = {
        "total_classified": len(classifications),
        "by_type": {
            "REAL": 0,
            "TEST": 0,
            "VALIDATION": 0,
            "DEMO": 0,
            "INTERNAL": 0,
            "REVIEW_REQUIRED": 0,
        },
        "real_customer_count": 0,
        "first_real_customer_arrived": False,
        "first_real_customer_id": None,
        "first_real_customer_utc": None,
    }
    
    real_intakes = []
    
    for intake_id, record in classifications.items():
        cls = record.get("classification", "REVIEW_REQUIRED")
        summary["by_type"][cls] = summary["by_type"].get(cls, 0) + 1
        
        if cls == "REAL":
            real_intakes.append((intake_id, record.get("classified_utc", "")))
    
    summary["real_customer_count"] = len(real_intakes)
    summary["first_real_customer_arrived"] = len(real_intakes) > 0
    
    if real_intakes:
        # Sort by classification time to find first
        real_intakes.sort(key=lambda x: x[1])
        summary["first_real_customer_id"] = real_intakes[0][0]
        summary["first_real_customer_utc"] = real_intakes[0][1]
    
    return summary


def promote_to_real(intake_id: str, operator_note: str = "") -> Dict[str, Any]:
    """Operator promotes an intake to REAL classification."""
    return set_classification(
        intake_id,
        IntakeClassification.REAL,
        reason="operator promoted to REAL",
        auto=False,
        operator_override=True,
        operator_note=operator_note,
    )


def demote_to_test(intake_id: str, operator_note: str = "") -> Dict[str, Any]:
    """Operator demotes an intake to TEST classification."""
    return set_classification(
        intake_id,
        IntakeClassification.TEST,
        reason="operator demoted to TEST",
        auto=False,
        operator_override=True,
        operator_note=operator_note,
    )


# =============================================================================
# COMPATIBILITY LAYER: Original document classification functions
# Restored in PATCH 13A-9.1 to maintain backward compatibility with:
#   - services/intake/queue.py
#   - services/intake/retention.py
#   - services/intake/intake.py
#   - services/intake/operator_actions.py
#   - tests/test_founding_pilot_operational_pipeline.py
#   - tests/test_upload_formats.py
# =============================================================================

from services.lazy_io import read_text_bounded

from .storage import intake_dir

DOC_SSP = "SSP"
DOC_POAM = "POAM"
DOC_SPRS = "SPRS"
DOC_NIST = "NIST questionnaire"
DOC_VENDOR = "Vendor form"
DOC_POLICY = "Policy set"
DOC_ASSET = "Asset inventory"
DOC_NETWORK = "Network diagram"
DOC_STRUCTURED_METADATA = "Structured metadata"
DOC_TEST_ARTIFACT = "Test artifact"
DOC_UNKNOWN = "Unknown"

ALL_DOC_TYPES = (
    DOC_SSP,
    DOC_POAM,
    DOC_SPRS,
    DOC_NIST,
    DOC_VENDOR,
    DOC_POLICY,
    DOC_ASSET,
    DOC_NETWORK,
    DOC_STRUCTURED_METADATA,
    DOC_TEST_ARTIFACT,
    DOC_UNKNOWN,
)

_TEXT_SAMPLE_BYTES = 16_384

_FILENAME_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (DOC_STRUCTURED_METADATA, ("company_profile.json", "company profile")),
    (DOC_TEST_ARTIFACT, ("ground_truth.json", "ground truth")),
    (DOC_SSP, ("ssp", "system security plan", "system-security-plan")),
    (DOC_POAM, ("poam", "plan of action", "plan-of-action", "poa&m")),
    (DOC_SPRS, ("sprs", "supplier performance", "supplier-performance")),
    (
        DOC_NIST,
        (
            "nist",
            "800-171",
            "800171",
            "cmmc",
            "assessment",
            "self-assessment",
            "security questionnaire",
        ),
    ),
    (DOC_VENDOR, ("vendor", "supplier", "third party", "third-party", "security form", "sig lite", "sig_lite")),
    (DOC_POLICY, ("policy", "policies", "acceptable use", "handbook", "standard")),
    (DOC_ASSET, ("asset", "inventory", "cmdb", "device list", "hardware list")),
    (DOC_NETWORK, ("network diagram", "topology", "architecture diagram", "network-arch")),
)


def _norm(s: str) -> str:
    s = (s or "").lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def _match_rules(name: str, text: str) -> Tuple[str, float]:
    hay = _norm(f"{name} {text}")
    best = DOC_UNKNOWN
    best_score = 0.35
    for doc_type, needles in _FILENAME_RULES:
        hits = sum(1 for n in needles if n in hay)
        if not hits:
            continue
        score = min(0.95, 0.55 + hits * 0.12)
        if score > best_score:
            best_score = score
            best = doc_type
    return best, round(best_score, 3)


def classify_upload_file(path: Path, filename: str) -> Dict[str, Any]:
    """Classify one stored upload using filename + bounded text sample."""
    name = filename or path.name
    text = ""
    ext = path.suffix.lower()
    if ext in (".txt", ".csv") and path.is_file():
        text = read_text_bounded(path, max_bytes=_TEXT_SAMPLE_BYTES)
    category, confidence = _match_rules(name, text)
    return {
        "filename": name,
        "category": category,
        "confidence": confidence,
        "size_bytes": path.stat().st_size if path.is_file() else 0,
    }


def _expected_for_context(context: str) -> List[str]:
    ctx = _norm(context)
    if any(k in ctx for k in ("cmmc", "800-171", "nist", "sprs", "dfars")):
        return [DOC_SSP, DOC_POAM, DOC_SPRS, DOC_NIST]
    if any(k in ctx for k in ("vendor", "customer", "questionnaire")):
        return [DOC_VENDOR, DOC_POLICY]
    return [DOC_SSP, DOC_VENDOR]


def _missing_items(found: List[str], context: str) -> List[str]:
    expected = _expected_for_context(context)
    missing = [e for e in expected if e not in found]
    if DOC_UNKNOWN in found and len(found) == 1:
        return expected[:3]
    return missing[:6]


def _suggested_action(
    *,
    review_status: str,
    urgent: bool,
    missing: List[str],
    primary_category: str,
    confidence: float,
) -> str:
    if review_status == "archived":
        return "No action — archived"
    if review_status == "high_value":
        return "Schedule founder call and map to evidence workspace"
    if review_status == "approved":
        return "Convert to evidence intake / kickoff package"
    if review_status == "needs_info":
        return "Send structured missing-document request"
    if urgent and missing:
        return f"Urgent: request {missing[0]} before deadline"
    if urgent:
        return "Prioritize review — deadline flagged"
    if missing:
        return f"Request: {', '.join(missing[:2])}"
    if primary_category == DOC_UNKNOWN or confidence < 0.55:
        return "Manual document triage — low classification confidence"
    if primary_category in (DOC_SSP, DOC_NIST, DOC_VENDOR):
        return "Run compliance gap scan on uploaded package"
    return "Standard founding pilot paperwork review"


def classify_intake(intake_id: str) -> Dict[str, Any]:
    """Classify all uploads for an intake; persist classification.json."""
    uploads = intake_dir(intake_id) / "uploads"
    files_out: List[Dict[str, Any]] = []
    if uploads.is_dir():
        for p in sorted(uploads.iterdir()):
            if not p.is_file():
                continue
            try:
                files_out.append(classify_upload_file(p, p.name))
            except OSError:
                files_out.append(
                    {
                        "filename": p.name,
                        "category": DOC_UNKNOWN,
                        "confidence": 0.2,
                        "size_bytes": 0,
                        "error": "unreadable",
                    }
                )

    categories = [f["category"] for f in files_out if f.get("category")]
    primary = DOC_UNKNOWN
    conf = 0.35
    if files_out:
        ranked = sorted(files_out, key=lambda x: float(x.get("confidence") or 0), reverse=True)
        primary = ranked[0].get("category") or DOC_UNKNOWN
        conf = float(ranked[0].get("confidence") or 0.35)
        if len(files_out) > 1:
            conf = round(min(0.98, conf + 0.05 * (len(set(categories)) - 1)), 3)

    intake_path = intake_dir(intake_id) / "intake.json"
    context = ""
    review_status = "pending_review"
    urgent = False
    if intake_path.is_file():
        try:
            rec = json.loads(intake_path.read_text(encoding="utf-8"))
            context = str(rec.get("context") or "")
            review_status = str(rec.get("review_status") or rec.get("status") or "pending_review")
            urgent = bool(rec.get("urgent"))
        except (json.JSONDecodeError, OSError):
            pass

    found_set = list(dict.fromkeys(categories))
    missing = _missing_items(found_set, context)
    payload = {
        "intake_id": intake_id,
        "classified_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files_out,
        "file_types": found_set,
        "primary_category": primary,
        "confidence_score": conf,
        "missing_items": missing,
        "suggested_next_action": _suggested_action(
            review_status=review_status,
            urgent=urgent,
            missing=missing,
            primary_category=primary,
            confidence=conf,
        ),
    }
    out = intake_dir(intake_id) / "classification.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(out)
    return payload


def load_classification(intake_id: str) -> Optional[Dict[str, Any]]:
    """Load document classification for an intake from classification.json."""
    path = intake_dir(intake_id) / "classification.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

"""Lightweight founding-pilot document classification — heuristics only, no AI runtime."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.lazy_io import read_text_bounded

from .storage import intake_dir


def _intake_dir(intake_id: str) -> Path:
    return intake_dir(intake_id)

DOC_SSP = "SSP"
DOC_POAM = "POAM"
DOC_SPRS = "SPRS"
DOC_NIST = "NIST questionnaire"
DOC_VENDOR = "Vendor form"
DOC_POLICY = "Policy set"
DOC_ASSET = "Asset inventory"
DOC_NETWORK = "Network diagram"
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
    DOC_UNKNOWN,
)

_TEXT_SAMPLE_BYTES = 16_384

_FILENAME_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
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
        return "Prioritize operator review — deadline flagged"
    if missing:
        return f"Request: {', '.join(missing[:2])}"
    if primary_category == DOC_UNKNOWN or confidence < 0.55:
        return "Manual document triage — low classification confidence"
    if primary_category in (DOC_SSP, DOC_NIST, DOC_VENDOR):
        return "Run compliance gap scan on uploaded package"
    return "Standard founding pilot paperwork review"


def classify_intake(intake_id: str) -> Dict[str, Any]:
    """Classify all uploads for an intake; persist classification.json."""
    uploads = _intake_dir(intake_id) / "uploads"
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

    intake_path = _intake_dir(intake_id) / "intake.json"
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
    out = _intake_dir(intake_id) / "classification.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(out)
    return payload


def load_classification(intake_id: str) -> Optional[Dict[str, Any]]:
    path = _intake_dir(intake_id) / "classification.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

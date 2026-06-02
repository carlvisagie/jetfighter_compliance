"""Build and update project evidence profile."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .confidence import mark_conflicting_company_names, merge_items
from .schemas import ClassificationResult, ExtractedItem, ProjectProfile


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bucket(profile: Dict[str, Any], item: ExtractedItem) -> None:
    t = item.type
    if t == "company_name":
        profile["company_name_candidates"] = merge_items(profile.get("company_name_candidates") or [], [item])
    elif t == "email":
        profile["emails"] = merge_items(profile.get("emails") or [], [item])
    elif t == "phone":
        profile["phones"] = merge_items(profile.get("phones") or [], [item])
    elif t == "domain":
        profile["domains"] = merge_items(profile.get("domains") or [], [item])
    elif t == "address":
        profile["addresses"] = merge_items(profile.get("addresses") or [], [item])
    elif t == "person_name":
        profile["people"] = merge_items(profile.get("people") or [], [item])
    elif t == "vendor":
        profile["vendors"] = merge_items(profile.get("vendors") or [], [item])
    elif t == "technology":
        profile["technologies"] = merge_items(profile.get("technologies") or [], [item])
    elif t == "compliance_reference":
        profile["compliance_references"] = merge_items(profile.get("compliance_references") or [], [item])


def apply_classification(profile: Dict[str, Any], clf: ClassificationResult) -> None:
    inv = profile.get("document_inventory") or []
    inv.append(
        {
            "file": clf.source_file,
            "document_type": clf.document_type,
            "confidence": clf.confidence,
            "signals": clf.signals,
            "updated_utc": _ts(),
        }
    )
    profile["document_inventory"] = inv[-50:]


def update_profile(profile: Dict[str, Any], entities: List[ExtractedItem], classification: ClassificationResult) -> Dict[str, Any]:
    for ent in entities:
        _bucket(profile, ent)
    apply_classification(profile, classification)
    mark_conflicting_company_names(profile)
    profile["updated_utc"] = _ts()
    return profile


def profile_to_customer_identified(profile: Dict[str, Any]) -> Dict[str, List[str]]:
    def vals(key: str) -> List[str]:
        return [str(x.get("value")) for x in (profile.get(key) or []) if x.get("value")][:10]

    return {
        "company_names": vals("company_name_candidates"),
        "emails": vals("emails"),
        "domains": vals("domains"),
        "addresses": vals("addresses"),
        "technologies": vals("technologies"),
        "vendors": vals("vendors"),
        "compliance_references": vals("compliance_references"),
    }


def needs_confirmation(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key, label in (
        ("company_name_candidates", "company name"),
        ("emails", "email"),
        ("domains", "domain"),
    ):
        for item in profile.get(key) or []:
            status = item.get("status", "inferred")
            if status == "conflicting":
                out.append(
                    {
                        "field": key,
                        "label": label,
                        "value": item.get("value"),
                        "confidence": item.get("confidence"),
                        "source_file": item.get("source_file"),
                        "status": "conflicting",
                        "message": f"We found multiple {label} candidates. Please confirm which is correct.",
                    }
                )
            elif status == "inferred" and float(item.get("confidence", 0)) >= 0.55:
                out.append(
                    {
                        "field": key,
                        "label": label,
                        "value": item.get("value"),
                        "confidence": item.get("confidence"),
                        "source_file": item.get("source_file"),
                        "status": "inferred",
                        "message": f"We may have identified this {label}. Please confirm.",
                    }
                )
    return out[:8]

"""Confidence helpers for evidence intelligence."""
from __future__ import annotations

from typing import Dict, List

from .schemas import ExtractedItem, ProjectProfile


def summarize_confidence(profile: Dict) -> Dict[str, int]:
    counts = {"confirmed": 0, "inferred": 0, "uncertain": 0, "conflicting": 0}
    for key in (
        "company_name_candidates",
        "emails",
        "phones",
        "addresses",
        "domains",
        "websites",
        "people",
        "vendors",
        "technologies",
        "cloud_providers",
        "identity_providers",
        "compliance_references",
    ):
        for item in profile.get(key) or []:
            st = (item.get("status") if isinstance(item, dict) else getattr(item, "status", "inferred")) or "inferred"
            conf = float(item.get("confidence", 0.5) if isinstance(item, dict) else getattr(item, "confidence", 0.5))
            if st == "confirmed":
                counts["confirmed"] += 1
            elif st in ("rejected",):
                continue
            elif st == "conflicting":
                counts["conflicting"] += 1
            elif conf < 0.55:
                counts["uncertain"] += 1
            else:
                counts["inferred"] += 1
    return counts


def merge_items(existing: List[Dict], new_items: List[ExtractedItem], max_per_type: int = 20) -> List[Dict]:
    by_val: Dict[str, Dict] = {f"{i.get('type')}:{i.get('value','').lower()}": i for i in existing if i.get("value")}
    for item in new_items:
        key = f"{item.type}:{item.value.lower()}"
        if key in by_val:
            old = by_val[key]
            if item.confidence > float(old.get("confidence", 0)):
                by_val[key] = item.model_dump()
        else:
            by_val[key] = item.model_dump()
    out = list(by_val.values())
    out.sort(key=lambda x: float(x.get("confidence", 0)), reverse=True)
    return out[:max_per_type]


def mark_conflicting_company_names(profile: Dict) -> bool:
    """If multiple distinct company names are inferred, mark all as conflicting.

    Returns True if any conflicts were detected.
    """
    candidates = profile.get("company_name_candidates") or []
    inferred = [
        c for c in candidates
        if c.get("status") in ("inferred", "conflicting")
    ]
    if len(inferred) > 1:
        for c in inferred:
            c["status"] = "conflicting"
        return True
    return False

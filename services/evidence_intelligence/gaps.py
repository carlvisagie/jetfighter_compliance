"""Detect likely missing evidence gaps (domain-aware).

The original v1 of this module shipped one CMMC-flavoured rule set
that ran against every project. That was a meaningful first-customer
embarrassment for DOT/FMCSA carriers and EU DPP suppliers: they saw
"missing SSP/POA&M" instead of the actually-relevant "missing Driver
Qualification File" or "missing Digital Product Passport".

This module now:

* Auto-detects the project's primary compliance domain (see
  :mod:`services.evidence_intelligence.domains`) when the caller does
  not pass one explicitly.
* Selects the matching rule pack (CMMC / DOT_FMCSA / EU_DPP / HIPAA
  / general) plus a universal pack of basics every program needs.
* Treats a gap as *satisfied* by either a matching ``document_type``
  in the inventory **or** any of the rule's ``text_signals`` appearing
  in the extracted text snippets we've stored on the profile.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .domains import Domain, detect_compliance_domain, rules_for_domain
from .schemas import GapItem


# Public re-export for backward compatibility — earlier callers imported
# ``GAP_DEFS`` from this module. Their intent was "every default rule",
# which today is CMMC + universal.
from .domains import CMMC_RULES as _CMMC, UNIVERSAL_RULES as _UNIVERSAL

GAP_DEFS: List[Dict[str, Any]] = _CMMC + _UNIVERSAL


def _present_doc_types(profile: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for row in profile.get("document_inventory") or []:
        out.add(str(row.get("document_type") or "unknown"))
    return out


def _profile_text_blob(profile: Dict[str, Any]) -> str:
    """Stitch together a low-cost text blob for signal matching.

    We don't keep the full extracted text on the profile (that lives
    in extractions.jsonl), so signals here ride on the inventory rows
    and the entity strings we *did* persist — enough to catch domain-
    specific phrases like "DOT physical" or "driver qualification".
    """
    parts: List[str] = []
    for row in profile.get("document_inventory") or []:
        parts.append(str(row.get("file") or ""))
        parts.append(str(row.get("document_type") or ""))
        for sig in row.get("signals") or []:
            parts.append(str(sig))
    for bucket in (
        "company_name_candidates",
        "emails",
        "domains",
        "vendors",
        "technologies",
        "compliance_references",
    ):
        for item in profile.get(bucket) or []:
            v = item.get("value")
            if v:
                parts.append(str(v))
    return " ".join(parts).lower()


def _rule_satisfied(
    rule: Dict[str, Any],
    *,
    present: Set[str],
    text_blob: str,
) -> bool:
    doc_types = set(rule.get("doc_types") or set())
    if doc_types and (present & doc_types):
        return True
    for signal in rule.get("text_signals") or ():
        if signal and signal.lower() in text_blob:
            return True
    return False


def detect_gaps(
    profile: Dict[str, Any],
    *,
    domain: Optional[Domain] = None,
) -> List[GapItem]:
    """Return the prioritised gap list for this project.

    ``domain`` may be passed explicitly when the caller already knows
    it (e.g. operator override); otherwise we auto-detect from the
    profile signals.
    """
    if domain is None:
        d = detect_compliance_domain(profile)
        domain = d.domain or "general"

    present   = _present_doc_types(profile)
    text_blob = _profile_text_blob(profile)
    rules     = rules_for_domain(domain)

    gaps: List[GapItem] = []
    for rule in rules:
        if _rule_satisfied(rule, present=present, text_blob=text_blob):
            continue
        gaps.append(
            GapItem(
                gap_id        = rule["gap_id"],
                label         = rule["label"],
                plain         = rule["explanation"],
                why           = rule.get("why", ""),
                priority      = rule.get("priority", "medium"),
                confidence    = 0.72,
                example_item_id = rule.get("catalog_key", ""),
            )
        )

    prio = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: prio.get(g.priority, 9))
    return gaps

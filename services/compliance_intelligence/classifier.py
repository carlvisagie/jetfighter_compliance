"""Rule-based classification of compliance changes."""
from __future__ import annotations

import re
from typing import List, Tuple

from .schemas import ChangeRecord, ClassificationResult, Severity

RULES: List[Tuple[str, List[str], Severity, bool]] = [
    ("CMMC", [r"\bcmmc\b", r"cyber\s*ab", r"certification\s+level"], "high", True),
    ("NIST 800-171", [r"800-171", r"sp\s*800-171"], "high", False),
    ("NIST 800-53", [r"800-53", r"sp\s*800-53"], "medium", False),
    ("DFARS", [r"\bdfars\b", r"252\.204"], "high", True),
    ("FAR", [r"\bfar\b", r"federal\s+acquisition"], "medium", False),
    ("CUI", [r"\bcui\b", r"controlled\s+unclassified"], "medium", False),
    ("ITAR", [r"\bitar\b", r"ddtc", r"export\s+control"], "high", True),
    ("CISA alert", [r"cisa", r"cybersecurity\s+advisory", r"kev", r"vulnerability"], "high", True),
    ("EU DPP/ESPR", [r"digital\s+product\s+passport", r"\bespr\b", r"ecodesign"], "medium", False),
]

IMPACT_AREA_RULES: List[Tuple[str, List[str]]] = [
    ("evidence_requirements", [r"evidence", r"artifact", r"assessment", r"audit"]),
    ("customer_guidance", [r"guidance", r"small\s+business", r"contractor"]),
    ("internal_workflow", [r"workflow", r"process", r"assessment"]),
    ("pricing_scope", [r"scope", r"pricing", r"level\s+[12]"]),
    ("acquisition_messaging", [r"outreach", r"marketplace", r"sam\.gov"]),
]


def classify_change(change: ChangeRecord, *, source_tags: List[str] = None) -> ClassificationResult:
    blob = f"{change.diff_summary} {change.title_new} {change.title_old} {' '.join(source_tags or [])}".lower()
    frameworks: List[str] = []
    severity: Severity = "info"
    urgent = False
    conf = 0.65

    for label, patterns, sev, is_urgent in RULES:
        if any(re.search(p, blob) for p in patterns):
            if label not in frameworks:
                frameworks.append(label)
            if _sev_rank(sev) > _sev_rank(severity):
                severity = sev
            if is_urgent:
                urgent = True
            conf = min(0.95, conf + 0.05)

    if not frameworks and source_tags:
        for tag in source_tags:
            t = tag.lower()
            if "cmmc" in t:
                frameworks.append("CMMC")
            elif "nist" in t:
                frameworks.append("NIST")
            elif "dfars" in t:
                frameworks.append("DFARS")
            elif "cisa" in t:
                frameworks.append("CISA alert")
            elif "dpp" in t or "eu" in t:
                frameworks.append("EU DPP/ESPR")

    impact_areas: List[str] = []
    for area, patterns in IMPACT_AREA_RULES:
        if any(re.search(p, blob) for p in patterns):
            impact_areas.append(area)
    if change.change_type in ("changed_content", "phrase_change", "title_change"):
        impact_areas.append("internal_workflow")
    if not impact_areas:
        impact_areas.append("customer_guidance")

    summary = f"Detected {change.change_type.replace('_', ' ')}"
    if frameworks:
        summary += f" — may affect {', '.join(frameworks[:4])}"

    return ClassificationResult(
        change_id=change.change_id,
        frameworks=frameworks,
        impact_areas=sorted(set(impact_areas)),
        severity=severity,
        urgent=urgent,
        summary=summary,
        confidence=conf,
    )


def _sev_rank(s: Severity) -> int:
    return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(s, 0)

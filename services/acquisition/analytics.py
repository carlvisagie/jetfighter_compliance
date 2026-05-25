"""Acquisition analytics and intelligence reports from accumulated forensic memory."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import DATA
from .intelligence_paths import (
    FORENSIC_EVENTS_JSONL,
    OUTCOMES_JSONL,
    ORG_PROFILES_JSONL,
    REPORTS_DIR,
    ensure_intel_dirs,
)
from .memory import _load_outcomes, get_learned_weights


def _load_forensic_events(base: Path) -> List[Dict[str, Any]]:
    path = base / FORENSIC_EVENTS_JSONL
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_org_profiles(base: Path) -> List[Dict[str, Any]]:
    path = base / ORG_PROFILES_JSONL
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        latest[r.get("org_key", "")] = r
    return list(latest.values())


def analyze_acquisition_intel(intel_base: Optional[Path] = None) -> Dict[str, Any]:
    base = ensure_intel_dirs(intel_base)
    outcomes = _load_outcomes(base)
    events = _load_forensic_events(base)
    profiles = _load_org_profiles(base)
    weights = get_learned_weights(base)

    pain_counter: Counter = Counter()
    gap_counter: Counter = Counter()
    industry_counter: Counter = Counter()
    segment_counter: Counter = Counter()
    urgency_counter: Counter = Counter()

    conversions = 0
    inquiries = 0
    abandon = 0

    for o in outcomes:
        stage = o.get("stage", "")
        if stage == "intake_completed" and o.get("success"):
            conversions += 1
        if stage == "inquiry_submitted":
            inquiries += 1
        if not o.get("success") and "abandon" in stage:
            abandon += 1
        meta = o.get("metadata") or {}
        for u in meta.get("urgency_indicators") or []:
            urgency_counter[u] += 1
        if meta.get("segment"):
            segment_counter[meta["segment"]] += 1

    for p in profiles:
        comp = p.get("compliance_readiness_profile") or {}
        for u in comp.get("urgency_indicators") or []:
            urgency_counter[u] += 1
        org = p.get("organizational_maturity_profile") or {}
        for g in org.get("gaps") or []:
            gap_counter[g] += 1
        doc = p.get("documentation_maturity_profile") or {}
        if doc.get("file_count", 0) == 0:
            gap_counter["no evidence uploaded yet"] += 1

    for e in events:
        payload = e.get("payload") or {}
        inq = payload.get("inquiry") or {}
        for u in inq.get("urgency_indicators") or []:
            pain_counter[u] += 1

    # Scan inquiry files for industries
    inq_dir = DATA / "inquiries"
    if inq_dir.exists():
        for f in inq_dir.glob("inquiry-*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                subj = (d.get("subject") or "").lower()
                if "cmmc" in subj:
                    industry_counter["cmmc"] += 1
                if "ai" in subj:
                    industry_counter["ai compliance"] += 1
            except Exception:
                pass

    return {
        "outcome_count": len(outcomes),
        "conversions": conversions,
        "inquiries": inquiries,
        "abandon_signals": abandon,
        "conversion_rate": (conversions / inquiries) if inquiries else 0.0,
        "top_pain_signals": pain_counter.most_common(10),
        "top_gaps": gap_counter.most_common(10),
        "top_urgency": urgency_counter.most_common(10),
        "subjects": industry_counter.most_common(10),
        "segments": segment_counter.most_common(10),
        "learned_weights": weights,
        "org_profiles_tracked": len(profiles),
        "forensic_events": len(events),
    }


def write_acquisition_analytics_report(intel_base: Optional[Path] = None) -> Path:
    intel = analyze_acquisition_intel(intel_base)
    base = ensure_intel_dirs(intel_base)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "acquisition_analytics_report.md"
    lines = [
        "# Acquisition analytics report",
        "",
        "## Conversion summary",
        "",
        f"- Outcomes recorded: **{intel['outcome_count']}**",
        f"- Inquiries: **{intel['inquiries']}**",
        f"- Intake completed: **{intel['conversions']}**",
        f"- Conversion rate (inquiry→intake): **{intel['conversion_rate']:.0%}**",
        f"- Abandon signals: **{intel['abandon_signals']}**",
        "",
        "## Recurring pain / urgency",
        "",
    ]
    for sig, cnt in intel["top_pain_signals"]:
        lines.append(f"- {sig}: {cnt}")
    if not intel["top_pain_signals"]:
        lines.append("- (accumulate more onboarding data)")
    lines.extend(["", "## Common gaps", ""])
    for g, cnt in intel["top_gaps"]:
        lines.append(f"- {g}: {cnt}")
    lines.extend(["", "## Best converting subjects", ""])
    for s, cnt in intel["subjects"]:
        lines.append(f"- {s}: {cnt}")
    lines.extend(["", "## Learned scoring weights (adaptive)", "", "```json", json.dumps(intel["learned_weights"], indent=2), "```", ""])
    lines.extend(
        [
            "",
            "## Forensic memory",
            "",
            f"- Organization profiles: **{intel['org_profiles_tracked']}**",
            f"- Forensic events: **{intel['forensic_events']}**",
            "",
            "## Recommendations",
            "",
            "1. Prioritize segments with highest conversion in outcomes.",
            "2. Lead with paperwork review — pricing after scope clarity.",
            "3. Review orgs with documentation_maturity_profile score &lt; 40 for extra onboarding support.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_forensic_intelligence_report(intel_base: Optional[Path] = None) -> Path:
    base = ensure_intel_dirs(intel_base)
    profiles = _load_org_profiles(base)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "forensic_intelligence_report.md"
    lines = [
        "# Forensic intelligence report",
        "",
        "Lawful organizational memory from onboarding, intake, and evidence (user-provided + public discovery metadata only).",
        "",
        f"Organizations tracked: **{len(profiles)}**",
        "",
    ]
    for p in sorted(profiles, key=lambda x: -(x.get("compliance_readiness_profile") or {}).get("score", 0))[:15]:
        org = p.get("org_key", "?")
        comp = p.get("compliance_readiness_profile") or {}
        doc = p.get("documentation_maturity_profile") or {}
        org_m = p.get("organizational_maturity_profile") or {}
        lines.append(f"### {org}")
        lines.append(f"- Compliance readiness: **{comp.get('score', 0)}**")
        lines.append(f"- Documentation maturity: **{doc.get('score', 0)}** (files: {doc.get('file_count', 0)})")
        lines.append(f"- Organizational maturity: **{org_m.get('score', 0)}** ({org_m.get('maturity_hint', '')})")
        lines.append("")
    if not profiles:
        lines.append("_No profiles yet — complete inquiry/intake/evidence flows to populate memory._")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

"""Discovery run reports for owner review."""
from __future__ import annotations

from pathlib import Path
from typing import List

from .models import ImportStats, Lead, utc_now
from .storage import reports_dir


def write_discovery_report(stats: ImportStats, all_leads: List[Lead], base: Path | None = None) -> Path:
    out_dir = reports_dir(base)
    path = out_dir / "latest_discovery_report.md"
    pain_top = sorted(stats.top_pain_signals.items(), key=lambda x: -x[1])[:10]
    queue_count = sum(1 for l in all_leads if l.fit_score >= 65 and l.status in ("new", "reviewed"))
    lines = [
        "# Latest discovery report",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|------:|",
        f"| Total rows read | {stats.total_rows} |",
        f"| Valid rows | {stats.valid_rows} |",
        f"| Rejected rows | {stats.rejected_rows} |",
        f"| Duplicates skipped | {stats.duplicates_skipped} |",
        f"| New leads imported | {stats.imported} |",
        f"| Fit score ≥ 80 | {stats.scored_80_plus} |",
        f"| Fit score 65–79 | {stats.scored_65_79} |",
        f"| Low fit (&lt; 65) | {stats.low_fit} |",
        f"| Review queue size | {queue_count} |",
        "",
        "## Top pain signals (this import)",
        "",
    ]
    if pain_top:
        for sig, cnt in pain_top:
            lines.append(f"- {sig}: {cnt}")
    else:
        lines.append("- (none recorded)")
    lines.extend(
        [
            "",
            "## Rejection reasons",
            "",
        ]
    )
    if stats.rejection_reasons:
        for r in stats.rejection_reasons[:20]:
            lines.append(f"- {r}")
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## New lead IDs",
            "",
        ]
    )
    if stats.new_lead_ids:
        for lid in stats.new_lead_ids:
            lines.append(f"- `{lid}`")
    else:
        lines.append("- (none)")
    high = [l for l in all_leads if l.fit_score >= 80][-5:]
    if high:
        lines.extend(["", "## Recent high-fit leads (sample)", ""])
        for l in high:
            lines.append(f"- **{l.company_name}** ({l.lead_id}) — fit {l.fit_score}, {l.reason_summary}")
    lines.extend(
        [
            "",
            "## Next recommended owner actions",
            "",
            "1. Open `data/acquisition/leads/review_queue.csv` and review leads with fit ≥ 65.",
            "2. Open `/ui/lead_discovery.html` for workflow and Sintra helper roles.",
            "3. Manually verify company/contact on public sources (no automated outreach).",
            "4. Mark approved leads in `leads.csv` / ops notes — status `approved_for_outreach` only after human approval.",
            "5. Send personalized outreach with the lead's `inquiry_routed_link` when approved.",
            "6. Log funnel in `data/acquisition/tracking.csv` after contact.",
            "",
            "**No automated contact occurred in this import.**",
            "",
        ]
    )
    from services.defensive_wiring import safe_write_text

    safe_write_text(

        path,

        "\n".join(lines),

        component="acquisition_export",

        context="export generation",

        severity="warning"

    )
    return path

"""Operational alert email templates."""
from __future__ import annotations

import html
from typing import Any, Dict

from .severity import SEVERITY_EMOJI, SEVERITY_LABELS, Severity


def _esc(text: str) -> str:
    return html.escape(str(text or ""))


def render_alert_html(
    *,
    title: str,
    body: str,
    severity: Severity,
    event_type: str,
    when_utc: str,
    context: Dict[str, Any],
    action_hint: str = "",
) -> str:
    emoji = SEVERITY_EMOJI.get(severity, "")
    label = SEVERITY_LABELS.get(severity, "INFO")
    rows = []
    for key in (
        "company",
        "source",
        "fit_score",
        "qualification_score",
        "upload_count",
        "file_types",
        "pain_signals",
        "emotional_burden_score",
        "campaign",
        "message_variant",
        "route_url",
        "continuation_url",
        "project_id",
        "stage",
    ):
        val = context.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val[:8])
        rows.append(f"<tr><td style='padding:4px 12px 4px 0;color:#666;'>{_esc(key)}</td><td>{_esc(val)}</td></tr>")

    links = ""
    for link_key in ("route_url", "continuation_url", "source_url", "post_url"):
        url = context.get(link_key)
        if url:
            links += f"<p><a href='{_esc(url)}'>{_esc(link_key.replace('_', ' '))}</a></p>"

    hint = f"<p style='margin-top:1rem;color:#444;'><strong>Next step:</strong> {_esc(action_hint)}</p>" if action_hint else ""

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#1a1a1a;max-width:640px;">
  <div style="border-left:4px solid #2563eb;padding-left:16px;margin-bottom:24px;">
    <p style="margin:0;font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:#666;">{emoji} {_esc(label)} · KeepYourContracts</p>
    <h1 style="margin:8px 0 0;font-size:22px;">{_esc(title)}</h1>
    <p style="margin:4px 0 0;font-size:13px;color:#888;">{_esc(when_utc)} · {_esc(event_type)}</p>
  </div>
  <p>{_esc(body)}</p>
  {"<table style='margin:16px 0;border-collapse:collapse;'>" + "".join(rows) + "</table>" if rows else ""}
  {links}
  {hint}
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
  <p style="font-size:12px;color:#999;">Operational alert — not legal advice. Customer documents are never attached.</p>
</body>
</html>
""".strip()


def subject_for_alert(title: str, severity: Severity, event_type: str) -> str:
    prefix = SEVERITY_LABELS.get(severity, "ALERT")
    if event_type == "first_paperwork_submission":
        return f"🚨 [{prefix}] {title}"
    return f"[{prefix}] {title}"

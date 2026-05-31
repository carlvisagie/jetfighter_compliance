"""Operational alerting engine — organism nervous system."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from . import dedupe, email as alert_email, routing, telegram, throttling
from .paths import load_config, load_state, save_state
from .rules import get_rule
from .severity import SEVERITY_EMOJI, SEVERITY_LABELS, Severity, parse_severity
from . import telemetry as alert_telemetry

logger = logging.getLogger(__name__)

_TEST_EMAIL_RE = re.compile(
    r"(pytest|test@|@example\.(com|org)|@test\.|\+test@|noreply@keepyourcontracts\.com)",
    re.I,
)


def is_real_customer_email(email: str) -> bool:
    el = (email or "").strip().lower()
    if not el or "@" not in el:
        return False
    if _TEST_EMAIL_RE.search(el):
        return False
    if el.endswith("@acquisition.local"):
        return False
    return True


def raise_alert(
    event_type: str,
    *,
    title: str = "",
    body: str = "",
    severity: Optional[Severity] = None,
    context: Optional[Dict[str, Any]] = None,
    dedupe_key: str = "",
    force: bool = False,
) -> Dict[str, Any]:
    """
    Emit an operational alert. Respects throttling, dedupe, quiet hours unless force or CRITICAL.
  Never includes file contents or secrets in outbound messages.
    """
    cfg = load_config()
    rule = get_rule(event_type, severity=severity)
    sev = severity or rule.severity
    ctx = dict(context or {})
    ctx.setdefault("operator_name", cfg.get("operator_name", ""))
    ctx.setdefault("operator_phone", cfg.get("operator_phone", ""))
    title = title or rule.title_template
    throttle_key = dedupe_key or f"{event_type}:{ctx.get('project_id') or ctx.get('lead_id') or ctx.get('company', '')[:40]}"

    result: Dict[str, Any] = {
        "ok": True,
        "event_type": event_type,
        "severity": SEVERITY_LABELS.get(sev, "INFO"),
        "suppressed": False,
        "telegram": None,
        "email": None,
    }

    if not force:
        if rule.dedupe_seconds and dedupe.is_duplicate(throttle_key, rule.dedupe_seconds):
            result["suppressed"] = True
            result["reason"] = "dedupe"
            alert_telemetry.link_memory("alert_suppressed", metadata={"reason": "dedupe", "event_type": event_type})
            return result
        if throttling.is_throttled(throttle_key, event_type, sev):
            result["suppressed"] = True
            result["reason"] = "throttle"
            return result

    rec = alert_telemetry.append_history(
        {
            "event_type": event_type,
            "severity": SEVERITY_LABELS.get(sev, "INFO"),
            "title": title,
            "body": body,
            "context": {k: v for k, v in ctx.items() if k not in ("file_content", "smtp_pass", "token")},
            "acknowledged": False,
            "channels": {},
        }
    )
    result["alert_id"] = rec.get("alert_id")
    alert_telemetry.link_memory("alert_generated", alert_id=rec.get("alert_id", ""), metadata={"event_type": event_type})

    emoji = SEVERITY_EMOJI.get(sev, "ℹ️")
    tg_text = telegram.format_telegram_message(title=title, body=body, severity_emoji=emoji, context=ctx)

    if routing.should_send_telegram(rule, cfg):
        tg = telegram.send_telegram_message(tg_text)
        result["telegram"] = tg
        rec["channels"]["telegram"] = tg
        if tg.get("ok"):
            alert_telemetry.link_memory("alert_sent", alert_id=rec.get("alert_id", ""), metadata={"channel": "telegram"})
        elif not tg.get("skipped"):
            alert_telemetry.append_failure({"alert_id": rec.get("alert_id"), "channel": "telegram", "error": tg.get("error")})
            alert_telemetry.link_memory("alert_failed", alert_id=rec.get("alert_id", ""), metadata={"channel": "telegram"})

    if routing.should_send_email(rule, cfg):
        to = routing.operator_email(cfg)
        if to:
            from services.emails import send_email_with_result

            html = alert_email.render_alert_html(
                title=title,
                body=body,
                severity=sev,
                event_type=event_type,
                when_utc=rec.get("when_utc", ""),
                context=ctx,
                action_hint=_action_hint(event_type),
            )
            subj = alert_email.subject_for_alert(title, sev, event_type)
            em = send_email_with_result(to, subj, html)
            result["email"] = em
            rec["channels"]["email"] = em
            if em.get("ok"):
                alert_telemetry.link_memory("alert_sent", alert_id=rec.get("alert_id", ""), metadata={"channel": "email"})
            elif not em.get("skipped"):
                alert_telemetry.append_failure({"alert_id": rec.get("alert_id"), "channel": "email", "error": em.get("error")})
        else:
            result["email"] = {"ok": False, "skipped": True, "reason": "no_operator_email"}

    if not result.get("suppressed"):
        dedupe.mark_seen(throttle_key)
        throttling.mark_sent(throttle_key, event_type, sev)

    return result


def _action_hint(event_type: str) -> str:
    hints = {
        "first_paperwork_submission": "Open Control → review project and evidence. Welcome the customer.",
        "paperwork_submitted": "Review uploaded files in the project workspace.",
        "high_fit_target": "Review draft outreach in Acquisition Intelligence — no auto-send.",
        "upload_abandonment": "Optional: light follow-up only if appropriate; do not spam.",
        "acquisition_conversion": "Confirm workspace and continuation links work.",
        "compliance_review_critical": "Review item in Compliance Intelligence panel.",
        "smtp_failure": "Check SMTP env vars and send test email from Control.",
    }
    return hints.get(event_type, "Open Control Center for details.")


def alert_first_paperwork_submission(
    *,
    email: str,
    name: str,
    project_id: str,
    upload_count: int,
    file_types: List[str],
    source: str = "",
    fit_score: int = 0,
    continuation_url: str = "",
    route_url: str = "",
    pain_signals: Optional[List[str]] = None,
    lead_id: str = "",
) -> Dict[str, Any]:
    """CRITICAL — first real customer paperwork. Operator must know immediately."""
    if not is_real_customer_email(email):
        return {"ok": True, "skipped": True, "reason": "not_real_customer"}

    state = load_state()
    ctx: Dict[str, Any] = {
        "company": name,
        "source": source,
        "upload_count": upload_count,
        "file_types": file_types,
        "project_id": project_id,
        "continuation_url": continuation_url,
        "route_url": route_url,
        "fit_score": fit_score,
        "pain_signals": pain_signals or [],
    }
    if lead_id:
        ctx["lead_id"] = lead_id
    if state.get("first_paperwork_alert_sent"):
        return raise_alert(
            "paperwork_submitted",
            title="Paperwork submitted",
            body=f"{name or email} completed upload-first onboarding.",
            context=ctx,
            dedupe_key=f"paperwork:{project_id}",
        )

    state["first_paperwork_alert_sent"] = True
    state["first_paperwork_project_id"] = project_id
    state["first_paperwork_utc"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(state)

    ctx["company"] = name or email.split("@")[0]
    ctx["source"] = source or "upload-first"
    return raise_alert(
        "first_paperwork_submission",
        title="FIRST REAL PAPERWORK SUBMISSION",
        body="A real customer submitted paperwork via upload-first onboarding.",
        severity=Severity.CRITICAL,
        context=ctx,
        dedupe_key="first_paperwork_ever",
        force=True,
    )


def alert_high_fit_target(target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cfg = load_config()
    threshold = int(cfg.get("qualification_threshold", 75))
    score = int(target.get("qualification_score") or target.get("fit_score") or 0)
    if score < threshold:
        return None
    return raise_alert(
        "high_fit_target",
        title=f"High-fit target: {target.get('company_name', 'Unknown')[:60]}",
        body=(target.get("pain_signal") or target.get("signal_level") or "Compliance burden detected")[:300],
        context={
            "company": target.get("company_name"),
            "source": target.get("source"),
            "fit_score": target.get("fit_score"),
            "qualification_score": score,
            "pain_signals": target.get("pain_signal"),
            "emotional_burden_score": target.get("emotional_burden_score"),
            "route_url": target.get("route_url"),
        },
        dedupe_key=f"high_fit:{target.get('target_id') or target.get('lead_id')}",
    )


def alert_acquisition_conversion(*, lead_id: str, intake_id: str) -> Optional[Dict[str, Any]]:
    """Fired when a prospect who came from acquisition uploads their paperwork."""
    return raise_alert(
        "acquisition_conversion",
        title=f"Acquisition lead converted to intake: {lead_id}",
        body=f"Lead {lead_id} submitted paperwork — intake {intake_id} is ready for review.",
        context={"lead_id": lead_id, "intake_id": intake_id},
        dedupe_key=f"acq_conv:{lead_id}:{intake_id}",
    )


def alert_organism_failure(event_type: str, *, message: str = "", metadata: Optional[Dict] = None) -> Dict[str, Any]:
    return raise_alert(
        event_type,
        title=get_rule(event_type).title_template,
        body=message[:500],
        severity=Severity.CRITICAL,
        context=metadata or {},
        dedupe_key=f"failure:{event_type}",
    )


def get_operator_dashboard() -> Dict[str, Any]:
    cfg = load_config()
    history = alert_telemetry.load_history(limit=80)
    critical_open = [h for h in history if h.get("severity") == "CRITICAL" and not h.get("acknowledged")]
    return {
        "ok": True,
        "config": {
            "email_enabled": cfg.get("email_enabled"),
            "telegram_enabled": cfg.get("telegram_enabled"),
            "telegram_configured": telegram.telegram_configured(),
            "high_fit_threshold": cfg.get("high_fit_threshold"),
            "quiet_hours": f"{cfg.get('quiet_hours_start')}-{cfg.get('quiet_hours_end')} UTC",
            "operator_name": cfg.get("operator_name"),
            "operator_phone": cfg.get("operator_phone"),
            "operator_email": routing.operator_email(cfg),
        },
        "recent_alerts": list(reversed(history[-25:])),
        "unacknowledged_critical": critical_open,
        "first_paperwork_sent": bool(load_state().get("first_paperwork_alert_sent")),
        "safety": {
            "no_customer_docs_in_alerts": True,
            "no_secrets_in_alerts": True,
            "ops_auth_required": True,
        },
    }

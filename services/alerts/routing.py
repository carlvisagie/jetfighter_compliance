"""Channel routing — email, Telegram, quiet hours."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from .paths import load_config
from .rules import AlertRule
from .severity import Severity, parse_severity


def in_quiet_hours(cfg: Dict[str, Any]) -> bool:
    start = int(cfg.get("quiet_hours_start", 22))
    end = int(cfg.get("quiet_hours_end", 7))
    hour = datetime.now(timezone.utc).hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def should_send_telegram(rule: AlertRule, cfg: Dict[str, Any]) -> bool:
    if not cfg.get("telegram_enabled", True) or not rule.telegram:
        return False
    min_sev = parse_severity(cfg.get("min_severity_telegram", "IMPORTANT"))
    if rule.severity < min_sev:
        return False
    if in_quiet_hours(cfg) and not rule.bypass_quiet and rule.severity < Severity.CRITICAL:
        return False
    return True


def should_send_email(rule: AlertRule, cfg: Dict[str, Any]) -> bool:
    if not cfg.get("email_enabled", True) or not rule.email:
        return False
    min_sev = parse_severity(cfg.get("min_severity_email", "HIGH"))
    if rule.severity < min_sev and rule.event_type != "first_paperwork_submission":
        return False
    if in_quiet_hours(cfg) and not rule.bypass_quiet and rule.severity < Severity.CRITICAL:
        return False
    return True


def operator_email(cfg: Dict[str, Any] | None = None) -> str:
    from ..config import SETTINGS

    cfg = cfg or load_config()
    return (cfg.get("operator_email") or SETTINGS.digest_email_to or "").strip()

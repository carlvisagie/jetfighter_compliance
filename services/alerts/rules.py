"""Alert event rules — severity, channels, dedupe windows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .severity import Severity


@dataclass(frozen=True)
class AlertRule:
    event_type: str
    severity: Severity
    title_template: str
    dedupe_seconds: int = 0
    telegram: bool = True
    email: bool = True
    bypass_quiet: bool = False


RULES: Dict[str, AlertRule] = {
    "first_paperwork_submission": AlertRule(
        "first_paperwork_submission",
        Severity.CRITICAL,
        "FIRST REAL PAPERWORK SUBMISSION",
        dedupe_seconds=0,
        bypass_quiet=True,
    ),
    "paperwork_submitted": AlertRule(
        "paperwork_submitted",
        Severity.HIGH,
        "Paperwork submitted",
        dedupe_seconds=300,
        bypass_quiet=True,
    ),
    "high_fit_target": AlertRule(
        "high_fit_target",
        Severity.IMPORTANT,
        "High-fit acquisition target",
        dedupe_seconds=3600,
    ),
    "acquisition_target_discovered": AlertRule(
        "acquisition_target_discovered",
        Severity.INFO,
        "Acquisition target discovered",
        dedupe_seconds=1800,
        telegram=False,
        email=False,
    ),
    "upload_started": AlertRule(
        "upload_started",
        Severity.IMPORTANT,
        "Upload started",
        dedupe_seconds=600,
        email=False,
    ),
    "continuation_resumed": AlertRule(
        "continuation_resumed",
        Severity.IMPORTANT,
        "Continuation resumed",
        dedupe_seconds=600,
        email=False,
    ),
    "upload_abandonment": AlertRule(
        "upload_abandonment",
        Severity.HIGH,
        "Upload abandonment",
        dedupe_seconds=86400,
    ),
    "acquisition_conversion": AlertRule(
        "acquisition_conversion",
        Severity.HIGH,
        "Acquisition conversion",
        dedupe_seconds=600,
        bypass_quiet=True,
    ),
    "compliance_review_critical": AlertRule(
        "compliance_review_critical",
        Severity.HIGH,
        "Compliance intelligence — review required",
        dedupe_seconds=3600,
    ),
    "compliance_regulatory_change": AlertRule(
        "compliance_regulatory_change",
        Severity.HIGH,
        "Regulatory change detected",
        dedupe_seconds=7200,
    ),
    "smtp_failure": AlertRule(
        "smtp_failure",
        Severity.CRITICAL,
        "SMTP failure",
        dedupe_seconds=1800,
        bypass_quiet=True,
    ),
    "scheduler_failure": AlertRule(
        "scheduler_failure",
        Severity.CRITICAL,
        "Scheduler failure",
        dedupe_seconds=3600,
        bypass_quiet=True,
    ),
    "telemetry_failure": AlertRule(
        "telemetry_failure",
        Severity.CRITICAL,
        "Telemetry failure",
        dedupe_seconds=1800,
        bypass_quiet=True,
    ),
    "acquisition_connector_failure": AlertRule(
        "acquisition_connector_failure",
        Severity.CRITICAL,
        "Acquisition connector failure",
        dedupe_seconds=3600,
        bypass_quiet=True,
    ),
    "memory_bridge_failure": AlertRule(
        "memory_bridge_failure",
        Severity.CRITICAL,
        "Central memory bridge failure",
        dedupe_seconds=3600,
        bypass_quiet=True,
    ),
    "upload_failure": AlertRule(
        "upload_failure",
        Severity.CRITICAL,
        "Upload system failure",
        dedupe_seconds=900,
        bypass_quiet=True,
    ),
    "qr_generation_failure": AlertRule(
        "qr_generation_failure",
        Severity.CRITICAL,
        "QR generation failure",
        dedupe_seconds=1800,
    ),
    "continuation_token_failure": AlertRule(
        "continuation_token_failure",
        Severity.CRITICAL,
        "Continuation token failure",
        dedupe_seconds=900,
        bypass_quiet=True,
    ),
    "digest_daily": AlertRule(
        "digest_daily",
        Severity.INFO,
        "Daily operational digest",
        dedupe_seconds=82800,
        telegram=False,
    ),
    "digest_weekly": AlertRule(
        "digest_weekly",
        Severity.INFO,
        "Weekly operational digest",
        dedupe_seconds=604800,
        telegram=False,
    ),
    "telemetry_learning_insight": AlertRule(
        "telemetry_learning_insight",
        Severity.INFO,
        "Organism learning insight",
        dedupe_seconds=7200,
        telegram=False,
        email=False,
    ),
}


def get_rule(event_type: str, *, severity: Optional[Severity] = None) -> AlertRule:
    if event_type in RULES:
        return RULES[event_type]
    return AlertRule(
        event_type,
        severity or Severity.INFO,
        event_type.replace("_", " ").title(),
        dedupe_seconds=1800,
    )

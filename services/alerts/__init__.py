"""
KYC Operational Alerting Nervous System.

Intelligent, throttled operational awareness — not spam.
"""
from .engine import (
    alert_first_paperwork_submission,
    alert_high_fit_target,
    alert_organism_failure,
    get_operator_dashboard,
    is_real_customer_email,
    raise_alert,
)
from .digest import generate_daily_digest, generate_weekly_digest
from .paths import load_config, save_config

__all__ = [
    "raise_alert",
    "alert_first_paperwork_submission",
    "alert_high_fit_target",
    "alert_organism_failure",
    "get_operator_dashboard",
    "is_real_customer_email",
    "generate_daily_digest",
    "generate_weekly_digest",
    "load_config",
    "save_config",
]

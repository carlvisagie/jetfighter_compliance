"""Organism observability — telemetry hardening and operator dashboards."""
from .beacon import record_customer_beacon
from .dashboard import get_operator_cockpit_observability
from .emit import organism_emit, write_failure_count
from .funnels import compute_acquisition_funnel, compute_upload_funnel
from .health import detect_silent_failures
from .registry import learning_goal_for

__all__ = [
    "organism_emit",
    "write_failure_count",
    "learning_goal_for",
    "record_customer_beacon",
    "get_operator_cockpit_observability",
    "compute_upload_funnel",
    "compute_acquisition_funnel",
    "detect_silent_failures",
]

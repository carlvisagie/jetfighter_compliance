"""Autonomous acquisition intelligence organism — burden removal, upload-first routing."""

from .analytics import analyze_acquisition_intel, write_acquisition_analytics_report, write_forensic_intelligence_report
from .discovery import run_csv_import, run_finder_discovery, build_inquiry_link
from .forensics import reconstruct_journey, record_inquiry_submitted, record_intake_completed
from .learning import (
    load_experiments,
    load_failures,
    load_winners,
    record_experiment,
    record_failure,
    record_winner,
    run_learning_cycle,
)
from .messaging import generate_message, list_variants, CORE_HEADLINE, CORE_SUBLINE
from .models import Lead, SEGMENTS
from .connectors.usaspending_live import run_usaspending_live_connector
from .orchestration import (
    get_operator_dashboard,
    ingest_discovery_candidate,
    ingest_public_signal,
    run_acquisition_cycle,
    track_funnel_event,
)
from .routing import build_upload_route, route_lead
from .scoring import score_lead, score_lead_full
from .signals import detect_signals
from .qualification import qualify_lead

__all__ = [
    "Lead",
    "SEGMENTS",
    "CORE_HEADLINE",
    "CORE_SUBLINE",
    "score_lead",
    "score_lead_full",
    "detect_signals",
    "qualify_lead",
    "run_csv_import",
    "run_finder_discovery",
    "build_inquiry_link",
    "build_upload_route",
    "route_lead",
    "generate_message",
    "list_variants",
    "ingest_public_signal",
    "ingest_discovery_candidate",
    "run_usaspending_live_connector",
    "run_acquisition_cycle",
    "track_funnel_event",
    "get_operator_dashboard",
    "run_learning_cycle",
    "record_winner",
    "record_failure",
    "record_experiment",
    "load_winners",
    "load_failures",
    "load_experiments",
    "analyze_acquisition_intel",
    "write_acquisition_analytics_report",
    "write_forensic_intelligence_report",
    "record_inquiry_submitted",
    "record_intake_completed",
    "reconstruct_journey",
]

"""Telemetry event registry — each event maps to an operational learning goal."""
from __future__ import annotations

from typing import Dict

# subsystem -> event_type -> learning_goal
EVENT_GOALS: Dict[str, Dict[str, str]] = {
    "acquisition_organism": {
        "acquisition_cycle_started": "Measure discovery cycle health and coverage",
        "acquisition_cycle_completed": "Detect zero-result or thin cycles",
        "discovery_cluster_used": "Learn which clusters produce prey",
        "prey_scored": "Tune burden vs predator scoring",
        "operator_approved": "Correlate approvals with real uploads",
        "operator_denied": "Train predator and topical filters",
        "queue_starvation": "Never fail silently with empty queue",
        "low_confidence_prey_cycle": "Flag weak discovery quality",
        "upload_conversion_completed": "Primary success — real paperwork",
    },
    "reddit_acquisition": {
        "reddit_discovery_started": "Acquisition cycle start",
        "reddit_discovery_completed": "Acquisition cycle completion stats",
        "reddit_reply_approved": "Operator approved prey",
        "reddit_post_ignored": "Operator denied prey",
        "prey_scored": "Prey quality per post",
    },
    "customer_session": {
        "upload_page_view": "Measure inquiry funnel entry",
        "helper_opened": "Hesitation before upload",
        "upload_started": "Upload momentum start",
        "upload_completed": "File entered organism",
        "upload_first_abandoned": "Trust or friction failure",
        "workspace_created": "Onboarding completion",
    },
    "customer_friction": {
        "upload_started": "Project upload path",
        "upload_abandoned": "Where momentum died",
        "continuation_completed": "Return visit trust",
    },
    "knowledge_cockpit": {
        "overlay_opened": "Contextual mentor usage",
        "overlay_collapsed": "Operator dismissed help",
        "overlay_failure": "Cockpit mentor broken",
        "explanation_generated": "What views need teaching",
        "concept_lookup": "Recurring operator confusion",
        "related_concepts_opened": "Concept graph exploration depth",
    },
    "evidence_intelligence": {
        "document_classified": "Evidence mapping quality",
        "evidence_mapping_failure": "Parser/classifier breakage",
        "gap_detected": "Missing evidence categories",
    },
    "organism_health": {
        "telemetry_write_failed": "Silent telemetry loss",
        "overlay_failure": "Cockpit mentor broken",
        "orphan_upload_detected": "Stuck session without project",
        "stuck_session_detected": "Abandoned mid-flow",
    },
}


def learning_goal_for(subsystem: str, event_type: str) -> str:
    return (
        EVENT_GOALS.get(subsystem, {}).get(event_type)
        or EVENT_GOALS.get("acquisition_organism", {}).get(event_type)
        or f"Observe {subsystem}/{event_type}"
    )

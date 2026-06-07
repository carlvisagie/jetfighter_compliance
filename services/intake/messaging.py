"""Reusable intake copy blocks — upload-first, low pressure (marketing strings may say Founding Pilot)."""
from __future__ import annotations

from typing import Any, Dict, List

PILOT_HEADLINE = "Founding Pilot — Free Compliance Burden Review"

PILOT_INTRO = (
    "We are testing a new upload-first workflow designed for contractors overwhelmed by "
    "security questionnaires, CMMC, DFARS, vendor requests, and documentation chaos."
)

PILOT_UPLOAD_LIST = (
    "Upload whatever you already have:\n"
    "- screenshots\n"
    "- policies\n"
    "- spreadsheets\n"
    "- notes\n"
    "- questionnaires\n"
    "- partial paperwork\n"
    "We will organize it, identify likely gaps, and use the results to improve the platform."
)

PILOT_REASSURANCE = "No perfect paperwork required."

PILOT_STYLE = "helpful, collaborative, low pressure, transparent, burden-relief oriented"


def intake_messaging_blocks() -> Dict[str, Any]:
    return {
        "headline": PILOT_HEADLINE,
        "intro": PILOT_INTRO,
        "upload_prompt": PILOT_UPLOAD_LIST,
        "reassurance": PILOT_REASSURANCE,
        "style": PILOT_STYLE,
        "success_metric": "real_paperwork_submitted",
        "primary_route": "/ui/inquiry.html",
    }



def intake_outreach_snippet(*, include_route: bool = False, route_url: str = "") -> str:
    """Short Reddit/public paste block for intake validation."""
    parts: List[str] = [
        PILOT_HEADLINE,
        "",
        PILOT_INTRO,
        "",
        PILOT_UPLOAD_LIST,
        "",
        PILOT_REASSURANCE,
    ]
    if include_route and route_url:
        parts.extend(["", f"If you want to try the intake: {route_url}"])
    return "\n".join(parts)


pilot_outreach_snippet = intake_outreach_snippet

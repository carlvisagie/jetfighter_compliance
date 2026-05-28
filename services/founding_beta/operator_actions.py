"""Operator actions on founding beta intakes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from .classification import classify_intake
from .intake import _load_intake, _save_intake
from .learning_hooks import record_founding_beta_learning
from .telemetry import emit_beta_event

VALID_ACTIONS = frozenset(
    {
        "approve_review",
        "request_more_info",
        "mark_high_value",
        "archive",
    }
)

_STATUS_MAP = {
    "approve_review": "approved",
    "request_more_info": "needs_info",
    "mark_high_value": "high_value",
    "archive": "archived",
}

_EVENT_MAP = {
    "approve_review": "operator_approved",
    "request_more_info": "operator_request_more_info",
    "mark_high_value": "operator_high_value",
    "archive": "operator_archived",
}


def apply_operator_action(
    intake_id: str,
    action: str,
    *,
    operator_note: str = "",
) -> Dict[str, Any]:
    action = (action or "").strip().lower()
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Use one of: {', '.join(sorted(VALID_ACTIONS))}",
        )

    rec = _load_intake(intake_id)
    new_status = _STATUS_MAP[action]
    rec["review_status"] = new_status
    rec["status"] = new_status
    if operator_note:
        rec["operator_note"] = operator_note.strip()[:1000]
    _save_intake(intake_id, rec)

    clf = classify_intake(intake_id)
    event_type = _EVENT_MAP[action]
    emit_beta_event(
        event_type,
        message=f"{action} on {intake_id}",
        metadata={
            "intake_id": intake_id,
            "review_status": new_status,
            "primary_category": clf.get("primary_category"),
        },
    )
    record_founding_beta_learning(
        event_type,
        intake_id=intake_id,
        success=True,
        extra={
            "primary_category": clf.get("primary_category"),
            "last_intake_id": intake_id,
        },
    )

    return {
        "ok": True,
        "intake_id": intake_id,
        "action": action,
        "review_status": new_status,
        "classification": clf,
    }

"""Validation mode — enable auto-kickoff for testing and validation projects."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_validation_project(intake_record: Dict[str, Any]) -> bool:
    """
    Check if intake qualifies for validation mode (auto-kickoff without payment).
    
    Validation projects bypass payment gate to enable end-to-end organism testing.
    
    Returns True if ANY of these conditions are met:
    1. validation_project flag is True
    2. founding_pilot flag is True  
    3. intake_id starts with "FB-test-" (explicit test intake)
    
    Commercial projects (payment required) return False.
    """
    # Explicit validation flag
    if intake_record.get("validation_project") is True:
        return True
    
    # Founding pilot flag (existing pattern)
    if intake_record.get("founding_pilot") is True:
        return True
    
    # Test intake by ID pattern
    intake_id = intake_record.get("intake_id", "")
    if intake_id.startswith("FB-test-"):
        return True
    
    return False


def is_auto_kickoff_eligible(intake_record: Dict[str, Any]) -> bool:
    """
    Check if intake is eligible for automatic project kickoff.
    
    Auto-kickoff occurs when:
    1. Payment confirmed (payment.payment_received_at_utc is set), OR
    2. Validation mode enabled (validation_project, founding_pilot, or test intake)
    
    Returns (eligible: bool, reason: str)
    """
    # Check payment confirmation
    payment = intake_record.get("payment") or {}
    payment_confirmed = bool(payment.get("payment_received_at_utc"))
    
    if payment_confirmed:
        return True, "payment_confirmed"
    
    # Check validation mode
    if is_validation_project(intake_record):
        return True, "validation_mode"
    
    return False, "payment_required"


def should_bypass_payment_gate(intake_record: Dict[str, Any]) -> bool:
    """
    Determine if payment gate should be bypassed for this intake.
    
    Used by kickoff to construct appropriate operator_note when auto-kickoff
    triggers without payment confirmation.
    
    Returns True only for validation projects.
    Commercial projects always require payment.
    """
    return is_validation_project(intake_record)

"""Backward-compat shim — canonical: services.intake.telemetry."""
from services.intake.telemetry import INTAKE_EVENT_TYPES as BETA_EVENT_TYPES
from services.intake.telemetry import emit_intake_event as emit_beta_event

__all__ = ["BETA_EVENT_TYPES", "emit_beta_event"]

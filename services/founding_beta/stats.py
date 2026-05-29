"""Backward-compat shim — canonical: services.intake.stats."""
from services.intake.stats import get_intake_status as get_founding_beta_status

__all__ = ["get_founding_beta_status"]

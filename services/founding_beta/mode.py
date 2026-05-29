"""Backward-compat shim — canonical: services.intake.mode."""
from services.intake.mode import is_intake_mode as is_founding_beta_mode

__all__ = ["is_founding_beta_mode"]

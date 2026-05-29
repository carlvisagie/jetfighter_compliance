"""Backward-compat shim — canonical: services.intake.learning_hooks."""
from services.intake.learning_hooks import record_intake_learning as record_founding_beta_learning

__all__ = ["record_founding_beta_learning"]

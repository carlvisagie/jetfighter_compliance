"""Email transport adapters — pure delivery, zero business logic."""
from . import manual_adapter, resend_adapter, smtp_adapter

__all__ = ["resend_adapter", "smtp_adapter", "manual_adapter"]

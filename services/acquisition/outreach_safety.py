"""PATCH 13A-8A: Acquisition outreach safety gate.

This module enforces all safety controls for autonomous outreach:
- Environment flag check (ACQUISITION_AUTO_SEND_ENABLED)
- Suppression list (global + per-lead)
- Opt-out / unsubscribe tracking
- Daily send cap enforcement
- Audit logging
- Operator approval workflow

DEFAULT BEHAVIOR: No automatic sends. All leads remain draft_only until
explicitly approved by operator via send-approved endpoints.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from . import telemetry
from .models import utc_now


def _root() -> Path:
    from ..config import DATA
    d = DATA / "acquisition" / "outreach_safety"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _suppression_path() -> Path:
    return _root() / "suppression_list.jsonl"


def _optout_path() -> Path:
    return _root() / "optouts.jsonl"


def _send_log_path() -> Path:
    return _root() / "send_log.jsonl"


def _daily_stats_path() -> Path:
    return _root() / "daily_stats.json"


# ---------------------------------------------------------------------------
# Environment flag check
# ---------------------------------------------------------------------------

def is_auto_send_enabled() -> bool:
    """Check if autonomous outreach is enabled via environment flag.
    
    DEFAULT: False. Must be explicitly set to true in production.
    """
    from ..config import SETTINGS
    return SETTINGS.acquisition_auto_send_enabled


def get_daily_send_cap() -> int:
    """Get the daily send cap from settings."""
    from ..config import SETTINGS
    return SETTINGS.acquisition_daily_send_cap


# ---------------------------------------------------------------------------
# Suppression list
# ---------------------------------------------------------------------------

def load_suppression_list() -> Set[str]:
    """Load all suppressed emails (lowercase, deduplicated)."""
    path = _suppression_path()
    suppressed: Set[str] = set()
    if not path.exists():
        return suppressed
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            email = (rec.get("email") or "").lower().strip()
            if email and rec.get("active", True):
                suppressed.add(email)
        except Exception:
            pass
    return suppressed


def add_to_suppression(
    email: str,
    *,
    reason: str = "manual",
    lead_id: str = "",
    note: str = "",
) -> Dict[str, Any]:
    """Add an email to the suppression list."""
    email_lower = email.lower().strip()
    if not email_lower or "@" not in email_lower:
        return {"ok": False, "error": "invalid_email"}
    
    record = {
        "email": email_lower,
        "reason": reason,
        "lead_id": lead_id,
        "note": note,
        "added_utc": utc_now(),
        "active": True,
    }
    path = _suppression_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    telemetry.emit(
        "suppression_added",
        lead_id=lead_id,
        metadata={"email": email_lower, "reason": reason},
    )
    return {"ok": True, "email": email_lower}


def is_suppressed(email: str) -> bool:
    """Check if an email is on the suppression list."""
    return email.lower().strip() in load_suppression_list()


# ---------------------------------------------------------------------------
# Opt-out / unsubscribe tracking
# ---------------------------------------------------------------------------

def load_optouts() -> Set[str]:
    """Load all opted-out emails."""
    path = _optout_path()
    optouts: Set[str] = set()
    if not path.exists():
        return optouts
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            email = (rec.get("email") or "").lower().strip()
            if email and rec.get("opted_out", True):
                optouts.add(email)
        except Exception:
            pass
    return optouts


def record_optout(
    email: str,
    *,
    source: str = "unsubscribe_link",
    lead_id: str = "",
) -> Dict[str, Any]:
    """Record an opt-out request."""
    email_lower = email.lower().strip()
    if not email_lower or "@" not in email_lower:
        return {"ok": False, "error": "invalid_email"}
    
    record = {
        "email": email_lower,
        "source": source,
        "lead_id": lead_id,
        "opted_out_utc": utc_now(),
        "opted_out": True,
    }
    path = _optout_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # Also add to suppression list
    add_to_suppression(email_lower, reason="optout", lead_id=lead_id)
    
    telemetry.emit(
        "optout_recorded",
        lead_id=lead_id,
        metadata={"email": email_lower, "source": source},
    )
    return {"ok": True, "email": email_lower}


def is_opted_out(email: str) -> bool:
    """Check if an email has opted out."""
    return email.lower().strip() in load_optouts()


# ---------------------------------------------------------------------------
# Daily send cap
# ---------------------------------------------------------------------------

def _load_daily_stats() -> Dict[str, Any]:
    """Load today's send statistics."""
    path = _daily_stats_path()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if not path.exists():
        return {"date": today, "sent_count": 0, "blocked_count": 0}
    
    try:
        stats = json.loads(path.read_text(encoding="utf-8"))
        if stats.get("date") != today:
            return {"date": today, "sent_count": 0, "blocked_count": 0}
        return stats
    except Exception:
        return {"date": today, "sent_count": 0, "blocked_count": 0}


def _save_daily_stats(stats: Dict[str, Any]) -> None:
    """Save daily send statistics."""
    path = _daily_stats_path()
    path.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def get_daily_send_count() -> int:
    """Get today's send count."""
    return _load_daily_stats().get("sent_count", 0)


def increment_daily_send_count() -> int:
    """Increment today's send count and return new value."""
    stats = _load_daily_stats()
    stats["sent_count"] = stats.get("sent_count", 0) + 1
    stats["last_send_utc"] = utc_now()
    _save_daily_stats(stats)
    return stats["sent_count"]


def increment_daily_blocked_count(reason: str = "") -> int:
    """Increment today's blocked count."""
    stats = _load_daily_stats()
    stats["blocked_count"] = stats.get("blocked_count", 0) + 1
    stats["last_blocked_utc"] = utc_now()
    stats["last_blocked_reason"] = reason
    _save_daily_stats(stats)
    return stats["blocked_count"]


def is_daily_cap_reached() -> bool:
    """Check if daily send cap has been reached."""
    return get_daily_send_count() >= get_daily_send_cap()


def get_remaining_daily_sends() -> int:
    """Get number of sends remaining today."""
    return max(0, get_daily_send_cap() - get_daily_send_count())


# ---------------------------------------------------------------------------
# Send audit log
# ---------------------------------------------------------------------------

def log_send_attempt(
    lead_id: str,
    email: str,
    *,
    approved: bool,
    sent: bool,
    blocked_reason: str = "",
    operator_approved: bool = False,
    auto_send: bool = False,
) -> Dict[str, Any]:
    """Log every send attempt for audit purposes."""
    record = {
        "lead_id": lead_id,
        "email": email.lower().strip(),
        "timestamp_utc": utc_now(),
        "approved": approved,
        "sent": sent,
        "blocked_reason": blocked_reason,
        "operator_approved": operator_approved,
        "auto_send": auto_send,
    }
    path = _send_log_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_send_log(limit: int = 100) -> List[Dict[str, Any]]:
    """Load recent send log entries."""
    path = _send_log_path()
    if not path.exists():
        return []
    
    entries: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries[-limit:]


# ---------------------------------------------------------------------------
# Pre-send safety check
# ---------------------------------------------------------------------------

def check_send_eligibility(
    email: str,
    lead_id: str = "",
    *,
    require_operator_approval: bool = True,
    operator_approved: bool = False,
) -> Dict[str, Any]:
    """
    Check if a send is allowed. Returns eligibility status and reason.
    
    This is the CENTRAL GATE for all outreach. Every send must pass this check.
    """
    email_lower = email.lower().strip()
    
    # 1. Validate email
    if not email_lower or "@" not in email_lower:
        return {
            "eligible": False,
            "reason": "invalid_email",
            "detail": "Email address is invalid or missing.",
        }
    
    # 2. Check suppression list
    if is_suppressed(email_lower):
        return {
            "eligible": False,
            "reason": "suppressed",
            "detail": "Email is on suppression list.",
        }
    
    # 3. Check opt-out list
    if is_opted_out(email_lower):
        return {
            "eligible": False,
            "reason": "opted_out",
            "detail": "Recipient has opted out of communications.",
        }
    
    # 4. Check daily cap
    if is_daily_cap_reached():
        return {
            "eligible": False,
            "reason": "daily_cap_reached",
            "detail": f"Daily send cap of {get_daily_send_cap()} reached.",
        }
    
    # 5. Check operator approval requirement
    if require_operator_approval and not operator_approved:
        # Check if auto-send is even enabled
        if not is_auto_send_enabled():
            return {
                "eligible": False,
                "reason": "auto_send_disabled",
                "detail": "ACQUISITION_AUTO_SEND_ENABLED is false. Operator approval required.",
            }
        # Even with auto-send enabled, we still require explicit approval for now
        return {
            "eligible": False,
            "reason": "operator_approval_required",
            "detail": "Operator must explicitly approve this send.",
        }
    
    return {
        "eligible": True,
        "reason": "approved",
        "detail": "Send is allowed.",
        "remaining_daily_sends": get_remaining_daily_sends(),
    }


# ---------------------------------------------------------------------------
# Operator dashboard data
# ---------------------------------------------------------------------------

def get_outreach_safety_status() -> Dict[str, Any]:
    """Get current outreach safety status for operator dashboard."""
    stats = _load_daily_stats()
    
    return {
        "auto_send_enabled": is_auto_send_enabled(),
        "daily_cap": get_daily_send_cap(),
        "sent_today": stats.get("sent_count", 0),
        "blocked_today": stats.get("blocked_count", 0),
        "remaining_today": get_remaining_daily_sends(),
        "suppression_count": len(load_suppression_list()),
        "optout_count": len(load_optouts()),
        "last_send_utc": stats.get("last_send_utc"),
        "policy_note": (
            "Auto-send DISABLED. All outreach requires operator approval."
            if not is_auto_send_enabled()
            else "Auto-send ENABLED. Sends will go out automatically for qualified leads."
        ),
    }

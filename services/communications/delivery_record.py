"""Email delivery record — append-only forensic log.

Every outbound email attempt writes one JSONL record regardless of outcome.
This is the audit trail: who, what, when, which provider, sent or not.

Schema per record:
    message_id          MSG-xxxx (unique per attempt)
    message_hash        SHA-256(to + subject + html)[:32] — dedup key
    intent              outreach_invite | payment_link | upload_confirmation |
                        operator_alert | operational
    to                  recipient address
    subject             email subject
    sent                bool — True only if a provider confirmed delivery
    provider_attempted  list of providers tried in order
    provider_succeeded  str or None
    fallback_used       bool — True if a non-primary provider delivered
    manual_fallback_generated  bool — True if copyable fallback was built
    lead_id / intake_id / project_id   attribution IDs (empty string if N/A)
    timestamp_utc       ISO-8601
    provider_response   {provider_name: response_dict}
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FILENAME = "email_delivery.jsonl"


def _log_dir() -> Path:
    """Runtime log directory — swappable in tests via monkeypatch."""
    try:
        from services.config import DATA
        d = DATA / "communications"
    except Exception:
        d = Path("data") / "communications"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_message_id() -> str:
    return "MSG-" + uuid.uuid4().hex[:12].upper()


def message_hash(to: str, subject: str, html: str) -> str:
    payload = f"{to}\x00{subject}\x00{html}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def record_delivery(
    *,
    msg_id: str,
    msg_hash: str,
    intent: str,
    to: str,
    subject: str,
    sent: bool,
    provider_attempted: List[str],
    provider_succeeded: Optional[str],
    fallback_used: bool,
    manual_fallback_generated: bool,
    lead_id: str = "",
    intake_id: str = "",
    project_id: str = "",
    provider_response: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one record to the delivery log. Never raises."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec: Dict[str, Any] = {
        "message_id": msg_id,
        "message_hash": msg_hash,
        "intent": intent,
        "to": to,
        "subject": subject,
        "sent": sent,
        "provider_attempted": provider_attempted,
        "provider_succeeded": provider_succeeded,
        "fallback_used": fallback_used,
        "manual_fallback_generated": manual_fallback_generated,
        "lead_id": lead_id,
        "intake_id": intake_id,
        "project_id": project_id,
        "timestamp_utc": now,
        "provider_response": provider_response or {},
    }
    try:
        log_dir = _log_dir() if base is None else (base / "communications")
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / _FILENAME
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("delivery_record: write failed: %s", exc)
    return rec


def load_delivery_log(*, base: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read the full delivery log. Returns [] on any error."""
    try:
        log_dir = _log_dir() if base is None else (base / "communications")
        log = log_dir / _FILENAME
        if not log.is_file():
            return []
        rows: List[Dict[str, Any]] = []
        for line in log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows
    except Exception:
        return []

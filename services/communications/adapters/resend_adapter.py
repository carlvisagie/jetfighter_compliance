"""Resend API transport adapter.

Pure HTTP delivery — zero business logic, zero domain imports.
All configuration is passed as arguments; this module owns nothing.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_configured(api_key: str) -> bool:
    return bool(api_key and api_key.strip())


def send(
    to: str,
    subject: str,
    html: str,
    *,
    from_addr: str,
    api_key: str,
) -> Dict[str, Any]:
    """POST to Resend API. Returns {sent, provider, ...} — never raises."""
    payload = json.dumps({
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        provider_id = body.get("id", "")
        logger.info("resend: delivered to %s (id=%s)", to, provider_id)
        return {"sent": True, "provider": "resend", "provider_id": provider_id}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        logger.warning("resend: HTTP %s for %s: %s", exc.code, to, raw[:300])
        return {
            "sent": False,
            "provider": "resend",
            "error": "resend_http_error",
            "detail": raw[:300],
            "http_status": exc.code,
        }
    except Exception as exc:
        logger.warning("resend: request failed for %s: %s", to, exc)
        return {
            "sent": False,
            "provider": "resend",
            "error": type(exc).__name__,
            "detail": str(exc)[:200],
        }

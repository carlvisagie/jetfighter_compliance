"""Telegram Bot operational alerts — primary realtime channel."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def telegram_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_CHAT_ID", "").strip())


def format_telegram_message(
    *,
    title: str,
    body: str,
    severity_emoji: str,
    context: Dict[str, Any],
) -> str:
    lines = [f"{severity_emoji} *{title}*"]
    if body:
        lines.append(body)
    for key, label in (
        ("source", "Source"),
        ("company", "Company"),
        ("upload_count", "Files"),
        ("fit_score", "Fit"),
        ("qualification_score", "Qualification"),
        ("pain_signals", "Signals"),
        ("campaign", "Campaign"),
        ("stage", "Stage"),
        ("project_id", "Project"),
    ):
        val = context.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val[:6])
        lines.append(f"*{label}:* {val}")
    for link_key in ("continuation_url", "route_url"):
        url = context.get(link_key)
        if url:
            lines.append(f"[Continue / route]({url})")
    return "\n".join(lines)


def send_telegram_message(text: str, *, parse_mode: str = "Markdown") -> Dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"ok": False, "skipped": True, "reason": "telegram_not_configured"}
    # Telegram message limit
    if len(text) > 4000:
        text = text[:3990] + "…"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": "false"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("ok"):
            return {"ok": True, "sent": True}
        return {"ok": False, "error": data.get("description", "telegram_api_error")}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning("Telegram send failed: %s", type(e).__name__)
        return {"ok": False, "error": type(e).__name__, "detail": str(e)[:120]}

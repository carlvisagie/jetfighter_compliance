"""Resolve public base URL for intake links (Render, env, local)."""
import os
from .config import SETTINGS


def get_public_base_url() -> str:
    base = (SETTINGS.public_base_url or "").rstrip("/")
    if base and not base.startswith("http://127.0.0.1") and not base.startswith("http://localhost"):
        return base
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if render_url:
        return render_url
    return base or "http://127.0.0.1:8080"

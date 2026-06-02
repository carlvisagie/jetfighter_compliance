"""Upload-first traffic routing — all acquisition paths lead to paperwork upload."""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from ..public_url import get_public_base_url
from .discovery import build_inquiry_link
from .models import Lead

UPLOAD_FIRST_PATHS = {
    "shop": "/ui/shop.html",
    "inquiry": "/ui/inquiry.html",
    "upload": "/upload",
}


def build_upload_route(
    *,
    lead_id: str = "",
    segment: str = "compliance-heavy",
    campaign_id: str = "upload-first",
    message_variant: str = "A",
    experiment_id: str = "",
    destination: str = "shop",
    base_url: Optional[str] = None,
) -> Dict[str, str]:
    """Primary acquisition destination: shop (upload-first onboarding with prices)."""
    base = (base_url or get_public_base_url()).rstrip("/")
    dest = destination if destination in UPLOAD_FIRST_PATHS else "shop"

    if dest == "inquiry" and lead_id:
        url = build_inquiry_link(lead_id, segment, base_url=base)
    elif dest == "upload":
        url = f"{base}/ui/intake"
    else:
        url = f"{base}{UPLOAD_FIRST_PATHS['shop']}"

    params = {"utm_campaign": campaign_id, "utm_content": message_variant}
    if lead_id:
        params["ref"] = lead_id
    if experiment_id:
        params["exp"] = experiment_id
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}{urlencode(params)}"

    return {
        "primary_url": url,
        "shop_url": f"{base}{UPLOAD_FIRST_PATHS['shop']}",
        "inquiry_url": f"{base}{UPLOAD_FIRST_PATHS['inquiry']}",
        "upload_path": UPLOAD_FIRST_PATHS["upload"],
        "campaign_id": campaign_id,
        "message_variant": message_variant,
        "routing_doctrine": "upload_first",
    }


def route_lead(lead: Lead, campaign_id: str = "upload-first", variant: str = "A") -> Lead:
    """Attach upload-first routed link to lead."""
    routes = build_upload_route(
        lead_id=lead.lead_id,
        segment=lead.segment or "compliance-heavy",
        campaign_id=campaign_id,
        message_variant=variant,
    )
    lead.inquiry_routed_link = routes["primary_url"]
    return lead

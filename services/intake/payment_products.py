"""First-sale service catalog — PayPal NCP links (post-review only)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_PRODUCTS: Dict[str, Dict[str, str]] = {
    "cmmc_l1": {
        "id": "cmmc_l1",
        "title": "CMMC Level 1 Fast-Track Assessment",
        "short_title": "CMMC Level 1 Fast-Track",
        "description": (
            "Focused readiness review for organizations pursuing CMMC Level 1 — "
            "policy alignment, evidence mapping, and a clear path to assessment."
        ),
        "price_display": "Starting at $3,500",
        "paypal_id": "PAFCVQWAP8CNL",
    },
    "cmmc_l2": {
        "id": "cmmc_l2",
        "title": "CMMC Level 2 Readiness Assessment",
        "short_title": "CMMC Level 2 Readiness",
        "description": (
            "Structured Level 2 readiness — control coverage, SSP/POA&M support, "
            "and practitioner-led guidance for certification preparation."
        ),
        "price_display": "Starting at $8,000",
        "paypal_id": "TGE3GEWHDUTG4",
    },
    "eu_dpp": {
        "id": "eu_dpp",
        "title": "EU Digital Product Passport Pilot",
        "short_title": "EU DPP Pilot",
        "description": (
            "Pilot program for EU Digital Product Passport compliance — data model review, "
            "evidence structure, and export-ready documentation planning."
        ),
        "price_display": "Starting at $6,000",
        "paypal_id": "PFMJJ4P5W5KHU",
    },
}


def paypal_ncp_url(paypal_id: str) -> str:
    return f"https://www.paypal.com/ncp/payment/{paypal_id}"


def list_payment_products() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in _PRODUCTS.values():
        out.append(
            {
                **row,
                "paypal_url": paypal_ncp_url(row["paypal_id"]),
            }
        )
    return out


def get_payment_product(product_id: str) -> Optional[Dict[str, Any]]:
    key = (product_id or "").strip().lower()
    row = _PRODUCTS.get(key)
    if not row:
        return None
    return {**row, "paypal_url": paypal_ncp_url(row["paypal_id"])}

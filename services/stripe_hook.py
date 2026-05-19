"""
Minimal Stripe webhook helpers (stdlib only — no stripe package).
Handles Payment Link checkout.session.completed → kickoff() inputs.
"""
import hashlib
import hmac
import json
import logging
import time
from typing import List, Tuple

# Slugs from ui/shop.html Payment Link URLs (buy.stripe.com/{slug})
PAYMENT_LINK_SLUG_TO_SKU = {
    "28E7sD7691Wq6v2c9l2kw01": "CMMC-L1-FAST",
    "aFaaEP8adcB44mU0qD2kw00": "CMMC-L2",
    "3cIdRIfCF1WqbPmc9l2kw04": "DPP-ESPR",
}


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str, tolerance: int = 300) -> bool:
    if not secret or not sig_header:
        return False
    parts = {}
    for item in sig_header.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k.strip()] = v.strip()
    ts = parts.get("t")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False
    try:
        if abs(time.time() - int(ts)) > tolerance:
            return False
    except ValueError:
        return False
    signed = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def _skus_from_session(session: dict) -> List[str]:
    meta = session.get("metadata") or {}
    if meta.get("sku"):
        return [str(meta["sku"])]
    if meta.get("skus"):
        raw = meta["skus"]
        if isinstance(raw, str):
            return [s.strip() for s in raw.split(",") if s.strip()]
    blob = json.dumps(session)
    for slug, sku in PAYMENT_LINK_SLUG_TO_SKU.items():
        if slug in blob:
            return [sku]
    amount = session.get("amount_total")
    if amount:
        return [f"STRIPE-{amount}"]
    return ["STRIPE-CHECKOUT"]


def parse_checkout_completed(event: dict) -> Tuple[str, str, str, List[str]]:
    """Return (order_id, email, name, skus) from checkout.session.completed."""
    session = event.get("data", {}).get("object") or {}
    order_id = session.get("id") or session.get("payment_intent") or f"stripe-{int(time.time())}"
    details = session.get("customer_details") or {}
    email = details.get("email") or session.get("customer_email") or ""
    name = details.get("name") or ""
    skus = _skus_from_session(session)
    return order_id, email, name, skus

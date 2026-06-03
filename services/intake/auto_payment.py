"""Autonomous payment link dispatch — fires after intake classification.

After a customer uploads documents and they are classified with enough confidence,
the system selects the correct product and sends the payment link without any
operator intervention. This is the core autonomous revenue path.

Mapping: classification primary_category → product_id
  CMMC documents (SSP, POAM, SPRS, NIST, VENDOR) → cmmc_l1  (default entry product)
  Level 2 signals (complex SSP with POAM, multi-domain) → cmmc_l2
  EU/DPP signals → eu_dpp

The system upgrades from L1 to L2 when document complexity warrants it.
Confidence threshold: 0.65 minimum. Below that, operator review is flagged instead.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Module-level references — can be replaced in tests via monkeypatch
def _load_intake(intake_id: str) -> Dict[str, Any]:
    from .intake import _load_intake as _real
    return _real(intake_id)


def _send_payment_link(
    intake_id: str,
    product_id: str,
    *,
    operator_note: str = "",
    update_status: bool = True,
) -> Dict[str, Any]:
    from .operator_actions import _send_payment_link as _real
    return _real(intake_id, product_id, operator_note=operator_note, update_status=update_status)

_CONFIDENCE_THRESHOLD = 0.65

# primary_category values from classification.py mapped to product_id
_CATEGORY_TO_PRODUCT: Dict[str, str] = {
    "SSP": "cmmc_l1",
    "POAM": "cmmc_l2",       # POA&M often indicates L2 complexity
    "SPRS": "cmmc_l1",
    "NIST questionnaire": "cmmc_l1",
    "Vendor form": "cmmc_l1",
    "Policy set": "cmmc_l1",
    "Asset inventory": "cmmc_l1",
    "Network diagram": "cmmc_l2",  # network diagrams typically L2 scope
    "Unknown": None,
}


def _pick_product_from_classification(clf: Dict[str, Any]) -> Optional[str]:
    """Map classification output to the best product_id. Returns None if confidence too low."""
    confidence = float(clf.get("confidence_score") or 0)
    if confidence < _CONFIDENCE_THRESHOLD:
        return None

    primary = str(clf.get("primary_category") or "")
    file_types = list(clf.get("file_types") or [])
    context = str(clf.get("intake_context") or clf.get("context") or "").lower()

    # Check context for EU/DPP signals first
    if any(k in context for k in ("eu dpp", "digital product passport", "eu dpa", "eudpp", "dpp")):
        return "eu_dpp"

    # Check if multiple document types suggest L2 scope
    l2_indicators = {"POAM", "Network diagram", "SSP"}
    if len(l2_indicators.intersection(set(file_types))) >= 2:
        return "cmmc_l2"

    product_id = _CATEGORY_TO_PRODUCT.get(primary)
    return product_id


def auto_send_payment_link(intake_id: str, clf: Dict[str, Any]) -> Dict[str, Any]:
    """Autonomously select product and send payment link after classification.

    Called immediately after `classify_intake` in the upload pipeline.
    No operator action required.
    """
    rec = _load_intake(intake_id)

    # Skip if payment already sent
    if rec.get("payment") and rec["payment"].get("payment_link_generated_at_utc"):
        logger.info("auto_payment: %s already has payment — skip", intake_id)
        return {"ok": True, "skipped": True, "reason": "payment_already_exists", "intake_id": intake_id}

    # Skip if no email
    email = (rec.get("email") or "").strip()
    if not email or "@" not in email:
        logger.info("auto_payment: %s has no email — cannot send", intake_id)
        return {"ok": False, "skipped": True, "reason": "no_email", "intake_id": intake_id}

    product_id = _pick_product_from_classification(clf)

    if not product_id:
        confidence = float(clf.get("confidence_score") or 0)
        logger.info(
            "auto_payment: %s confidence %.2f below threshold or unknown category — flagging for operator",
            intake_id,
            confidence,
        )
        # Flag for operator but don't block
        try:
            from services.alerts import raise_alert
            raise_alert(
                "paperwork_submitted",
                title=f"Manual product selection needed — {intake_id}",
                body=(
                    f"Classification confidence {confidence:.0%} is below threshold "
                    f"or category unknown. Operator must select product and send payment link."
                ),
                context={
                    "intake_id": intake_id,
                    "primary_category": clf.get("primary_category"),
                    "confidence_score": confidence,
                    "action_required": "select_product_and_send_payment_link",
                },
                dedupe_key=f"manual_product:{intake_id}",
            )
        except Exception as exc:
            logger.warning("auto_payment alert skipped: %s", exc)
        return {
            "ok": False,
            "skipped": True,
            "reason": "low_confidence_or_unknown_category",
            "intake_id": intake_id,
            "confidence_score": clf.get("confidence_score"),
            "primary_category": clf.get("primary_category"),
        }

    logger.info(
        "auto_payment: %s → product=%s (category=%s confidence=%.2f) — sending payment link",
        intake_id,
        product_id,
        clf.get("primary_category"),
        float(clf.get("confidence_score") or 0),
    )

    try:
        result = _send_payment_link(
            intake_id,
            product_id,
            operator_note="auto-sent by KYC autonomous pipeline",
            update_status=False,  # keep pending_review so operator can confirm in queue
        )
        result["auto_triggered"] = True
        return result
    except Exception as exc:
        logger.error("auto_payment: _send_payment_link failed for %s: %s", intake_id, exc)
        # Alert operator — they need to send manually
        try:
            from services.alerts import raise_alert
            raise_alert(
                "paperwork_submitted",
                title=f"Auto-payment failed — manual send needed for {intake_id}",
                body=f"Product {product_id} selected but payment link send failed: {str(exc)[:200]}",
                context={
                    "intake_id": intake_id,
                    "product_id": product_id,
                    "error": str(exc)[:200],
                    "action_required": "send_payment_link_manually",
                },
                dedupe_key=f"auto_payment_failed:{intake_id}",
            )
        except Exception:
            pass
        return {
            "ok": False,
            "intake_id": intake_id,
            "product_id": product_id,
            "error": str(exc)[:200],
            "auto_triggered": True,
        }

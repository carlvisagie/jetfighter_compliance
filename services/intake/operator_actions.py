"""Operator actions on founding pilot intakes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from .classification import classify_intake
from .intake import _load_intake, _save_intake
from .learning_hooks import record_intake_learning
from .telemetry import emit_intake_event

VALID_ACTIONS = frozenset(
    {
        "approve_review",
        "request_more_info",
        "mark_high_value",
        "archive",
        "send_payment_link",
        "confirm_payment_received",
        "kickoff_project",
    }
)

_STATUS_MAP = {
    "approve_review": "approved",
    "request_more_info": "needs_info",
    "mark_high_value": "high_value",
    "archive": "archived",
    "confirm_payment_received": "paid",
}

_EVENT_MAP = {
    "approve_review": "operator_approved",
    "request_more_info": "operator_request_more_info",
    "mark_high_value": "operator_high_value",
    "archive": "operator_archived",
    "confirm_payment_received": "operator_payment_received",
}


def apply_operator_action(
    intake_id: str,
    action: str,
    *,
    operator_note: str = "",
    product_id: str = "",
) -> Dict[str, Any]:
    action = (action or "").strip().lower()
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Use one of: {', '.join(sorted(VALID_ACTIONS))}",
        )

    if action == "send_payment_link":
        return _send_payment_link(intake_id, product_id, operator_note=operator_note)

    if action == "confirm_payment_received":
        return _confirm_payment_received(intake_id, operator_note=operator_note)

    if action == "kickoff_project":
        from .kickoff import kickoff_project_from_intake

        return kickoff_project_from_intake(intake_id, operator_note=operator_note)

    rec = _load_intake(intake_id)
    prev_status = rec.get("review_status") or rec.get("status") or ""
    new_status = _STATUS_MAP[action]
    rec["review_status"] = new_status
    rec["status"] = new_status
    if operator_note:
        rec["operator_note"] = operator_note.strip()[:1000]
    _save_intake(intake_id, rec)

    # Custody capture: operator review-status transition is a court-grade
    # event ("operator X moved this intake from approved → needs_info at
    # time T"). The intake_record source in custody_timeline only ever
    # surfaces the *current* status, so without this transaction event
    # the per-transition timestamp would be lost.
    try:
        from .transactions import append_transaction_event

        append_transaction_event(
            intake_id,
            f"operator_action_{action}",
            metadata={
                "prev_review_status": prev_status,
                "new_review_status":  new_status,
                "operator_note":      (operator_note or "")[:200],
            },
        )
    except Exception:
        pass

    clf = classify_intake(intake_id)
    event_type = _EVENT_MAP[action]
    emit_intake_event(
        event_type,
        message=f"{action} on {intake_id}",
        metadata={
            "intake_id": intake_id,
            "review_status": new_status,
            "primary_category": clf.get("primary_category"),
        },
    )
    record_intake_learning(
        event_type,
        intake_id=intake_id,
        success=True,
        extra={
            "primary_category": clf.get("primary_category"),
            "last_intake_id": intake_id,
        },
    )

    return {
        "ok": True,
        "intake_id": intake_id,
        "action": action,
        "review_status": new_status,
        "classification": clf,
    }


def _send_payment_link(
    intake_id: str,
    product_id: str,
    *,
    operator_note: str = "",
    update_status: bool = True,
) -> Dict[str, Any]:
    """Send (or re-send) a payment link email for an intake.

    update_status=False is used by the autonomous pipeline — the intake stays
    in pending_review so the operator can confirm. Set True (default) only for
    explicit operator-triggered sends.
    """
    from datetime import datetime, timezone

    from .payment_email import send_payment_link_email
    from .payment_products import get_payment_product

    product = get_payment_product(product_id)
    if not product:
        raise HTTPException(
            status_code=400,
            detail="product_id required — use cmmc_l1, cmmc_l2, or eu_dpp",
        )

    rec = _load_intake(intake_id)
    email = (rec.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Intake missing valid customer email")

    existing = dict(rec.get("payment") or {})
    if (
        existing.get("product_id") == product["id"]
        and existing.get("payment_link_generated_at_utc")
        and existing.get("paypal_url")
    ):
        mail = dict(existing.get("payment_link_email") or {})
        return {
            "ok": True,
            "intake_id": intake_id,
            "action": "send_payment_link",
            "product_id": product["id"],
            "product_title": product.get("title"),
            "paypal_url": product.get("paypal_url"),
            "email_result": mail,
            "email_sent": bool(existing.get("payment_link_sent_at_utc")),
            "duplicate_skipped": True,
            "payment": existing,
        }

    company = (rec.get("company") or "").strip()
    name = company or email.split("@")[0] or "Customer"

    mail = send_payment_link_email(
        to_email=email,
        customer_name=name,
        company=company,
        product_id=product["id"],
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payment = dict(existing)
    payment.update(
        {
            "product_id": product["id"],
            "product_title": product.get("title"),
            "price_display": product.get("price_display"),
            "paypal_url": product.get("paypal_url"),
            "payment_link_generated_at_utc": now,
            "payment_link_email": mail,
        }
    )
    if mail.get("sent"):
        payment["payment_link_sent_at_utc"] = now
    else:
        payment["payment_link_sent_at_utc"] = None

    rec["payment"] = payment
    if operator_note:
        rec["operator_note"] = operator_note.strip()[:1000]
    if update_status and rec.get("review_status") not in ("archived",):
        rec["review_status"] = rec.get("review_status") or "approved"
        if rec.get("review_status") == "pending_review":
            rec["review_status"] = "approved"
    rec["status"] = rec.get("review_status") or rec.get("status")
    _save_intake(intake_id, rec)

    email_sent = bool(mail.get("sent"))

    # Custody capture: payment-link generation/send is the moment the
    # platform asks the customer for money — must appear in the chain
    # of custody with the product, the recipient, and whether the email
    # actually left the building.
    try:
        from .transactions import append_transaction_event

        append_transaction_event(
            intake_id,
            "operator_payment_link_sent",
            ok=email_sent or bool(mail.get("skipped")),
            metadata={
                "product_id":      product["id"],
                "product_title":   product.get("title"),
                "price_display":   product.get("price_display"),
                "recipient_email": email,
                "email_sent":      email_sent,
                "email_skipped":   bool(mail.get("skipped")),
            },
        )
    except Exception:
        pass

    emit_intake_event(
        "operator_payment_link_sent",
        message=f"Payment link generated for {product.get('title')}",
        metadata={
            "intake_id": intake_id,
            "product_id": product["id"],
            "email": email,
            "email_sent": email_sent,
            "email_skipped": bool(mail.get("skipped")),
            "manual_fallback": not email_sent,
        },
    )
    record_intake_learning(
        "operator_payment_link_sent",
        intake_id=intake_id,
        success=True,
        extra={"product_id": product["id"], "last_intake_id": intake_id},
    )

    return {
        "ok": True,
        "intake_id": intake_id,
        "action": "send_payment_link",
        "product_id": product["id"],
        "product_title": product.get("title"),
        "paypal_url": product.get("paypal_url"),
        "email_result": mail,
        "email_sent": email_sent,
        "payment": payment,
    }


def _confirm_payment_received(
    intake_id: str, *, operator_note: str = ""
) -> Dict[str, Any]:
    """Operator marks PayPal payment as received.

    Closes the open loop flagged in the 2026-06-04 revenue-pipeline
    audit: payment links are generated but PayPal has no webhook back,
    so "did the customer pay?" relied on operators remembering to
    check a separate inbox. This route lets the operator (or a future
    webhook) record receipt explicitly, which:

      • stamps `payment.payment_received_at_utc` on the intake,
      • promotes review_status → "paid",
      • emits a custody event + telemetry row so the awareness layer
        knows the loop closed,
      • returns kickoff-ready signal so the operator UI can prompt
        the next step in one click.
    """
    from datetime import datetime, timezone

    rec = _load_intake(intake_id)
    existing = dict(rec.get("payment") or {})
    if not existing.get("payment_link_generated_at_utc"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot confirm payment — no payment link has been "
                "generated for this intake. Send the payment link first."
            ),
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payment = dict(existing)
    if payment.get("payment_received_at_utc"):
        # Idempotent — re-confirming is harmless.
        return {
            "ok": True,
            "intake_id": intake_id,
            "action": "confirm_payment_received",
            "payment": payment,
            "duplicate_skipped": True,
            "review_status": rec.get("review_status"),
        }
    payment["payment_received_at_utc"] = now
    payment["payment_confirmed_via"] = "operator"
    rec["payment"] = payment
    rec["review_status"] = "paid"
    rec["status"] = "paid"
    if operator_note:
        rec["operator_note"] = operator_note.strip()[:1000]
    _save_intake(intake_id, rec)

    try:
        from .transactions import append_transaction_event

        append_transaction_event(
            intake_id,
            "operator_payment_received",
            ok=True,
            metadata={
                "product_id":     payment.get("product_id"),
                "product_title": payment.get("product_title"),
                "price_display": payment.get("price_display"),
                "received_via":  "operator",
            },
        )
    except Exception:
        pass

    emit_intake_event(
        "operator_payment_received",
        message=f"Operator confirmed payment for {payment.get('product_title')}",
        metadata={
            "intake_id":     intake_id,
            "product_id":    payment.get("product_id"),
            "received_via": "operator",
        },
    )
    record_intake_learning(
        "operator_payment_received",
        intake_id=intake_id,
        success=True,
        extra={"product_id": payment.get("product_id")},
    )

    return {
        "ok": True,
        "intake_id":      intake_id,
        "action":         "confirm_payment_received",
        "review_status": rec.get("review_status"),
        "payment":        payment,
        "kickoff_ready": True,
    }

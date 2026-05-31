"""Post-review payment link email — PayPal only, sent by operator after approval."""
from __future__ import annotations

import html
from typing import Any, Dict

from .payment_products import get_payment_product


def build_payment_link_email_html(
    *,
    customer_name: str,
    company: str,
    product: Dict[str, Any],
) -> str:
    name = html.escape(customer_name or "there")
    co = html.escape(company or "your organization")
    title = html.escape(str(product.get("title") or ""))
    price = html.escape(str(product.get("price_display") or ""))
    pay_url = html.escape(str(product.get("paypal_url") or ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<body style="font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; line-height: 1.6; max-width: 640px;">
  <p>Dear {name},</p>
  <p>Thank you for submitting your paperwork to KeepYourContracts. We have reviewed your materials
  for <strong>{co}</strong> and we are ready to move forward.</p>
  <p><strong>Selected service:</strong> {title}<br>
  <strong>Investment:</strong> {price}</p>
  <p>When you are ready, please complete payment securely via PayPal:</p>
  <p style="margin: 1.5rem 0;">
    <a href="{pay_url}" style="display: inline-block; background: #003087; color: #ffffff;
      padding: 14px 28px; text-decoration: none; font-weight: 600; border-radius: 6px;">
      Pay with PayPal
    </a>
  </p>
  <p style="font-size: 0.95rem; color: #444;">
    Or copy this link: <a href="{pay_url}">{pay_url}</a>
  </p>
  <p><strong>What happens next</strong></p>
  <ol>
    <li>Complete payment via the link above.</li>
    <li>Our team confirms receipt and opens your project workspace.</li>
    <li>You receive next-step guidance and continued support through delivery.</li>
  </ol>
  <p>If you have questions before paying, reply to this email — we are here to help.</p>
  <p>With appreciation,<br><strong>KeepYourContracts</strong><br>
  <a href="https://compliance.keepyourcontracts.com">compliance.keepyourcontracts.com</a></p>
</body>
</html>"""


def send_payment_link_email(
    *,
    to_email: str,
    customer_name: str,
    company: str,
    product_id: str,
) -> Dict[str, Any]:
    product = get_payment_product(product_id)
    if not product:
        return {"ok": False, "error": "invalid_product", "product_id": product_id}

    subject = "KeepYourContracts — Project Approval & Payment Link"
    body = build_payment_link_email_html(
        customer_name=customer_name,
        company=company,
        product=product,
    )

    from services.emails import send_email_with_result

    result = send_email_with_result(to_email.strip(), subject, body)
    return {
        **result,
        "product_id": product_id,
        "product_title": product.get("title"),
        "paypal_url": product.get("paypal_url"),
    }

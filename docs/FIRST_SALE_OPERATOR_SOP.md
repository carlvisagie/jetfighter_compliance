# First Sale — Operator SOP

Short checklist for the upload-first → review → payment → kickoff path.  
**Cockpit:** https://compliance.keepyourcontracts.com/ui/control.html (ops login required)

---

## Product catalog (PayPal NCP)

| Product | Price | Product ID | PayPal link ID | Full URL |
|---------|-------|--------------|----------------|----------|
| CMMC L1 | $3,500 | `cmmc_l1` | `PAFCVQWAP8CNL` | https://www.paypal.com/ncp/payment/PAFCVQWAP8CNL |
| CMMC L2 | $8,000 | `cmmc_l2` | `TGE3GEWHDUTG4` | https://www.paypal.com/ncp/payment/TGE3GEWHDUTG4 |
| EU DPP | $6,000 | `eu_dpp` | `PFMJJ4P5W5KHU` | https://www.paypal.com/ncp/payment/PFMJJ4P5W5KHU |

Match the service to what you recommended after paperwork review. Do not send a payment link before review.

---

## 1. Review a new intake

1. Open **Control** → **Intake Queue**.
2. Find the card by company name, email, or intake ID (`FB-…`).
3. Check **Documents** — preview or download uploaded files.
4. Note classification, confidence/risk, and any integrity warnings.
5. If more files are needed: **Request more info** (optional operator note).
6. When ready to proceed: **Approve review** (or leave as approved after payment-link send).

---

## 2. Select the correct product

In the intake card, use **Service for payment link**:

- **CMMC Level 1 Fast-Track ($3,500)** → `cmmc_l1` — small org / Level 1 scope
- **CMMC Level 2 Readiness ($8,000)** → `cmmc_l2` — Level 2 / SSP–POA&M scope
- **EU DPP Pilot ($6,000)** → `eu_dpp` — EU Digital Product Passport pilot

Pick the service that matches your written recommendation to the customer.

---

## 3. Send or copy the payment link

1. Select the service in the dropdown.
2. Click **Send payment link**.
3. Outcome:
   - **Email sent** — customer received PayPal link via SMTP.
   - **Email failed / SMTP off** — action still succeeds; use manual fallback on the card (see §4).

On the card you will see:

- **PayPal URL** (clickable)
- **Copy Payment Link**
- **Copy customer email**
- **Manual email text** (expand for subject + body)

Re-clicking **Send payment link** for the same product does not spam email again; use **Copy Payment Link** if the link is already generated.

---

## 4. Manually email the customer (SMTP failed)

When the card shows **Email failed — copy link manually**:

1. Click **Copy customer email** → paste into your mail client **To** field.
2. Expand **Manual email text** → **Copy manual email** (or copy from the panel).

**Subject:**  
`KeepYourContracts — Project Approval & Payment Link`

**Body template:**

```
Your paperwork review is complete. Based on your submission, the recommended service is:
[service name]
Price: [price]
Payment link: [PayPal URL]
After payment, we will open your project workspace and begin the compliance review.
```

Fill in service name, price, and PayPal URL from the intake card. Send from your normal business mailbox (e.g. admin@keepyourcontracts.com).

---

## 5. Confirm PayPal payment (manual)

There is no automated payment webhook on this path. Confirm payment yourself:

1. Check **PayPal** (NCP / business account) for a completed payment matching the customer and amount.
2. Match payer email or name to the intake when possible.
3. Optionally open the PayPal URL from the card and verify it shows the correct item and price before the customer pays.
4. Do **not** kick off until you are satisfied payment is received.

Record confirmation in your operator note or external ledger (see §7).

---

## 6. Kickoff project

1. After payment is confirmed, return to the same intake card.
2. Click **Kickoff project** (confirm the dialog: customer has paid).
3. System creates a **project ID** and links intake files into project evidence.
4. Use **Open intake** or project surfaces as needed for delivery.

Kickoff requires files on durable disk and a valid customer email on the intake.

---

## 7. What to record on the intake

The system records automatically when you send a payment link:

- `payment.product_id`, `product_title`, `price_display`, `paypal_url`
- `payment_link_generated_at_utc`
- `payment_link_sent_at_utc` — set only if SMTP delivery succeeded; `null` if manual email required

You should still capture (operator note, PayPal, or CRM):

- Recommended service and why
- Payment confirmation (PayPal transaction ID / date / amount)
- Date kickoff was run and resulting **project ID**
- Any follow-up promised to the customer

---

## Quick reference

| Step | Cockpit action |
|------|----------------|
| Review | Intake Queue → documents + approve |
| Product | Service dropdown |
| Payment link | **Send payment link** or **Copy Payment Link** |
| No email | Copy email + manual body → send yourself |
| Paid? | PayPal dashboard (manual) |
| Start work | **Kickoff project** |

For SMTP setup (optional): `docs/KYC_SMTP_SETUP.md`. First sale does **not** depend on SMTP when manual fallback is used.

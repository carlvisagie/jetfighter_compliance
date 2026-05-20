# KYC Branded QR Payment System (Task 20)

**Date:** 2026-05-19  
**Scope:** Branded QR assets + optional UI display blocks. No backend or onboarding changes.

---

## Summary

Unified **enterprise-branded** QR payment assets for all five PayPal products. Web PNGs live under `ui/assets/qr/`; printable posters under `docs/assets/posters/`. Shop and inquiry pages include optional, non-cluttered QR blocks.

---

## Generated assets — web (`ui/assets/qr/`)

| File | Product | Price | PayPal URL | Size (bytes) |
|------|---------|-------|------------|--------------|
| `kyc-cmmc-l1-qr.png` | CMMC Level 1 Readiness Assessment | $3,500 | `…/PAFCVQWAP8CNL` | 21,624 |
| `kyc-cmmc-l2-qr.png` | CMMC Level 2 Readiness Assessment | $8,000 | `…/TGE3GEWHDUTG4` | 21,375 |
| `kyc-dpp-qr.png` | EU Digital Product Passport Pilot | $6,000 | `…/PFMJJ4P5W5KHU` | 20,690 |
| `kyc-ai-essential-qr.png` | AI Compliance Essential | $800 | `…/9SW62N7N2ADFW` | 21,411 |
| `kyc-ai-growth-qr.png` | AI Compliance Growth | $2,500 | `…/ZH3BTPVUS8SPJ` | 21,961 |

**Dimensions:** 480×640 px (portrait cards).  
**Design:** Dark KYC theme (`#060d18` / `#0f1c2e`), white QR inset, accent price, KeepYourContracts header, product title, CTA, `keepyourcontracts.com` footer.

---

## Poster inventory (`docs/assets/posters/`)

| File | Product | Size (bytes) | Print |
|------|---------|--------------|-------|
| `kyc-poster-cmmc-l1.png` | CMMC L1 | 42,389 | 1200×1600 px |
| `kyc-poster-cmmc-l2.png` | CMMC L2 | 42,158 | 1200×1600 px |
| `kyc-poster-dpp.png` | EU DPP | 40,953 | 1200×1600 px |
| `kyc-poster-ai-essential.png` | AI Essential | 41,422 | 1200×1600 px |
| `kyc-poster-ai-growth.png` | AI Growth | 42,664 | 1200×1600 px |

**Poster copy:** “Scan to Begin” + product CTA + large QR + price — suitable for trade shows and print.

---

## Generator

| Script | Purpose |
|--------|---------|
| `scripts/generate_payment_qr_assets.py` | Regenerate web + poster PNGs from PayPal URLs |
| `docs/assets/qr_manifest.txt` | URL + byte size manifest |

**Dependencies:** `qrcode[pil]`, `pillow` (see script header).

---

## UI integration (non-clutter)

| Page | Change |
|------|--------|
| `ui/shop.html` | Compact `.kyc-payment-qr` under each PayPal button (max 10rem wide) |
| `ui/inquiry.html` | Collapsible `<details>` “Pay now on mobile” with 5-thumb grid |
| `ui/assets/styles/components.css` | `.kyc-payment-qr`, `.kyc-qr-pay-options`, `.kyc-qr-pay-grid` |

Inquiry form `#f` and shop PayPal links unchanged.

---

## Mobile scan verification

**Method:** OpenCV `QRCodeDetector` decode on exported web PNGs (full branded card).

| Asset | Decoded URL match |
|-------|-------------------|
| `kyc-cmmc-l1-qr.png` | **PASS** |
| `kyc-cmmc-l2-qr.png` | **PASS** |
| `kyc-dpp-qr.png` | **PASS** |
| `kyc-ai-essential-qr.png` | **PASS** |
| `kyc-ai-growth-qr.png` | **PASS** |

**QR module settings:** Error correction **H**, black-on-white module area inside white rounded box for camera contrast.

**Manual mobile check (recommended):** Scan each shop-page QR with phone camera → confirm PayPal checkout opens for correct product.

---

## Live asset verification (Render)

| Asset | Expected | Post-deploy |
|-------|----------|-------------|
| `/ui/assets/qr/kyc-cmmc-l1-qr.png` | HTTP 200 | Pending |
| All 5 web QR PNGs | HTTP 200 | Pending |
| `/ui/shop.html` references 5 QR paths | Present | Pending |
| `/ui/inquiry.html` details block | Present | Pending |

*Updated after deploy push.*

---

## Preserved unchanged

- Backend, kickoff, intake, upload, evidence APIs  
- Just Talk / SAGE  
- Existing `kyc_upload_qr.png` path (upload flow; separate from payment QRs)  
- Platform design system tokens  

---

## Success criteria

| Criterion | Status |
|-----------|--------|
| 5 branded web QR PNGs | **Done** |
| 5 printable posters | **Done** |
| Shop + inquiry QR blocks | **Done** |
| Decode verification | **Done** (OpenCV) |
| Live deploy verification | **Pending push** |

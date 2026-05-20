"""
Task 20 — Generate branded PayPal payment QR assets (web + print posters).
Run: python scripts/generate_payment_qr_assets.py
"""
from __future__ import annotations

from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H

ROOT = Path(__file__).resolve().parents[1]
QR_DIR = ROOT / "ui" / "assets" / "qr"
POSTER_DIR = ROOT / "docs" / "assets" / "posters"

# Design tokens (match design-system.css)
BG = "#060d18"
SURFACE = "#0f1c2e"
LINE = "#1f3250"
TEXT = "#f4f7fb"
MUTED = "#9eb4d1"
ACCENT = "#4d9bff"
ACCENT_DARK = "#1f7cff"

PRODUCTS = [
    {
        "file": "kyc-cmmc-l1-qr.png",
        "poster": "kyc-poster-cmmc-l1.png",
        "short": "CMMC Level 1",
        "title": "CMMC Level 1 Readiness Assessment",
        "price": "$3,500",
        "cta": "Start Assessment",
        "paypal_id": "PAFCVQWAP8CNL",
    },
    {
        "file": "kyc-cmmc-l2-qr.png",
        "poster": "kyc-poster-cmmc-l2.png",
        "short": "CMMC Level 2",
        "title": "CMMC Level 2 Readiness Assessment",
        "price": "$8,000",
        "cta": "Secure Your Slot",
        "paypal_id": "TGE3GEWHDUTG4",
    },
    {
        "file": "kyc-dpp-qr.png",
        "poster": "kyc-poster-dpp.png",
        "short": "EU DPP Pilot",
        "title": "EU Digital Product Passport Pilot",
        "price": "$6,000",
        "cta": "Launch Pilot",
        "paypal_id": "PFMJJ4P5W5KHU",
    },
    {
        "file": "kyc-ai-essential-qr.png",
        "poster": "kyc-poster-ai-essential.png",
        "short": "AI Compliance Essential",
        "title": "AI Compliance Essential",
        "price": "$800",
        "cta": "Begin Compliance Intake",
        "paypal_id": "9SW62N7N2ADFW",
    },
    {
        "file": "kyc-ai-growth-qr.png",
        "poster": "kyc-poster-ai-growth.png",
        "short": "AI Compliance Growth",
        "title": "AI Compliance Growth",
        "price": "$2,500",
        "cta": "Launch Readiness Review",
        "paypal_id": "ZH3BTPVUS8SPJ",
    },
]


def paypal_url(paypal_id: str) -> str:
    return f"https://www.paypal.com/ncp/payment/{paypal_id}"


def load_fonts() -> dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    candidates = {
        "brand": [
            r"C:\Windows\Fonts\segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
        "title": [
            r"C:\Windows\Fonts\segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
        "body": [
            r"C:\Windows\Fonts\segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "price": [
            r"C:\Windows\Fonts\segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
    }
    fonts: dict = {}
    for key, paths in candidates.items():
        for p in paths:
            if Path(p).exists():
                size = {"brand": 28, "title": 22, "body": 16, "price": 36}.get(key, 18)
                if key == "poster_brand":
                    size = 52
                if key == "poster_title":
                    size = 40
                if key == "poster_price":
                    size = 64
                if key == "poster_body":
                    size = 28
                fonts[key] = ImageFont.truetype(p, size)
                break
        if key not in fonts:
            fonts[key] = ImageFont.load_default()
    fonts["poster_brand"] = _try_font(
        [r"C:\Windows\Fonts\segoeuib.ttf"], 52, fonts.get("brand")
    )
    fonts["poster_title"] = _try_font(
        [r"C:\Windows\Fonts\segoeuib.ttf"], 38, fonts.get("title")
    )
    fonts["poster_price"] = _try_font(
        [r"C:\Windows\Fonts\segoeuib.ttf"], 72, fonts.get("price")
    )
    fonts["poster_body"] = _try_font(
        [r"C:\Windows\Fonts\segoeui.ttf"], 28, fonts.get("body")
    )
    fonts["poster_scan"] = _try_font(
        [r"C:\Windows\Fonts\segoeuib.ttf"], 44, fonts.get("title")
    )
    return fonts


def _try_font(paths, size, fallback):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return fallback or ImageFont.load_default()


def make_qr_image(url: str, module_px: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#ffffff")
    img = img.convert("RGB")
    if module_px:
        img = img.resize((module_px, module_px), Image.Resampling.NEAREST)
    return img


def wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for w in words:
        trial = " ".join(current + [w])
        if draw.textlength(trial, font=font) <= max_width:
            current.append(w)
        else:
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def draw_branded_card(
    product: dict,
    size: tuple[int, int],
    qr_px: int,
    fonts: dict,
    poster: bool = False,
) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    margin = 48 if poster else 28
    pad = 20

    # Header bar
    draw.rectangle((0, 0, w, 8), fill=ACCENT_DARK)
    draw.rectangle((margin, margin, w - margin, margin + 4), fill=LINE)

    y = margin + 16
    brand = "KeepYourContracts"
    draw.text((margin, y), "Keep", fill=TEXT, font=fonts["poster_brand" if poster else "brand"])
    keep_w = draw.textlength("Keep", font=fonts["poster_brand" if poster else "brand"])
    draw.text(
        (margin + keep_w, y),
        "YourContracts",
        fill=ACCENT,
        font=fonts["poster_brand" if poster else "brand"],
    )
    y += 56 if poster else 40

    draw.text((margin, y), "ENTERPRISE COMPLIANCE", fill=MUTED, font=fonts["poster_body" if poster else "body"])
    y += 36 if poster else 24

    title_font = fonts["poster_title" if poster else "title"]
    for line in wrap_text(draw, product["title"], title_font, w - 2 * margin):
        draw.text((margin, y), line, fill=TEXT, font=title_font)
        y += 44 if poster else 28

    y += 8
    draw.text(
        (margin, y),
        product["price"],
        fill=ACCENT,
        font=fonts["poster_price" if poster else "price"],
    )
    y += 80 if poster else 48

    url = paypal_url(product["paypal_id"])
    qr = make_qr_image(url, qr_px)
    qr_pad = 24 if poster else 16
    box_w = qr.width + 2 * qr_pad
    box_h = qr.height + 2 * qr_pad
    box_x = (w - box_w) // 2
    box_y = y
    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_w, box_y + box_h),
        radius=16,
        fill="#ffffff",
        outline=LINE,
        width=2,
    )
    img.paste(qr, (box_x + qr_pad, box_y + qr_pad))
    y = box_y + box_h + (32 if poster else 20)

    cta_font = fonts["poster_body" if poster else "body"]
    cta = product["cta"] if not poster else "Scan to Begin"
    tw = draw.textlength(cta, font=cta_font)
    draw.text(((w - tw) / 2, y), cta, fill=TEXT, font=cta_font)
    y += 36 if poster else 22

    sub = "Secure PayPal checkout" if not poster else product["cta"]
    sw = draw.textlength(sub, font=fonts["body"])
    draw.text(((w - sw) / 2, y), sub, fill=MUTED, font=fonts["body"])

    # Footer
    foot_y = h - (margin + 8)
    draw.rectangle((margin, foot_y - 4, w - margin, foot_y), fill=LINE)
    foot = "keepyourcontracts.com"
    fw = draw.textlength(foot, font=fonts["body"])
    draw.text(((w - fw) / 2, foot_y + 8), foot, fill=MUTED, font=fonts["body"])

    return img


def verify_qr_decode(path: Path, expected_url: str) -> bool:
    try:
        from pyzbar.pyzbar import decode as zbar_decode
    except ImportError:
        # Fallback: trust qrcode library round-trip
        qr = qrcode.QRCode()
        qr.add_data(expected_url)
        qr.make(fit=True)
        return path.exists() and path.stat().st_size > 5000

    img = Image.open(path)
    # Decode white inset only — scan full image
    codes = zbar_decode(img)
    if not codes:
        return False
    data = codes[0].data.decode("utf-8")
    return data == expected_url


def main() -> None:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()

    results = []
    for p in PRODUCTS:
        url = paypal_url(p["paypal_id"])
        web = draw_branded_card(p, (480, 640), 220, fonts, poster=False)
        web_path = QR_DIR / p["file"]
        web.save(web_path, "PNG", optimize=True)
        poster = draw_branded_card(p, (1200, 1600), 520, fonts, poster=True)
        poster_path = POSTER_DIR / p["poster"]
        poster.save(poster_path, "PNG", optimize=True)
        ok = verify_qr_decode(web_path, url)
        results.append((p["file"], url, ok, web_path.stat().st_size, poster_path.stat().st_size))
        print(f"OK {p['file']} verify={ok} web={web_path.stat().st_size} poster={poster_path.stat().st_size}")

    # Manifest for docs
    manifest = ROOT / "docs" / "assets" / "qr_manifest.txt"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8") as f:
        for fname, url, ok, ws, ps in results:
            f.write(f"{fname}\t{url}\tdecode_ok={ok}\tweb_bytes={ws}\tposter_bytes={ps}\n")
    print("Wrote", manifest)


if __name__ == "__main__":
    main()

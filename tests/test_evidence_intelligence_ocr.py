"""Regression guard for the OCR fallback in evidence-intelligence extraction.

Real DOT/FMCSA, medical, and older policy archives are routinely
delivered as scanned PDFs or smartphone-photo packets. Before this
work the platform happily emitted "we organized your files" while
extracting **zero** text from those uploads — the silent-failure mode
called out in the 2026-06-04 evidence-intelligence forensic audit.

These tests pin the four contracts that keep that from happening
again:

1. Text PDFs continue to use pypdf and OCR never fires.
2. With ``KYC_OCR_ENABLED`` unset, scanned PDFs do *not* invoke OCR
   (graceful default — no surprises in CI / dev without binaries).
3. With ``KYC_OCR_ENABLED=true`` and the OCR helpers patched to
   succeed, a scanned PDF surfaces real text and ``ocr_applied=True``.
4. With ``KYC_OCR_ENABLED=true`` but the tesseract binary missing,
   extraction degrades cleanly with an ``image_ocr_skipped`` /
   ``scanned_pdf_ocr_skipped`` warning instead of raising.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from services.evidence_intelligence import extraction as ext_mod
from services.evidence_intelligence import ocr as ocr_mod
from services.evidence_intelligence.extraction import extract_from_file


# --- helpers ----------------------------------------------------------------


def _png_with_text(text: str) -> bytes:
    """Tiny PNG header — content is irrelevant; we mock the OCR call."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 80), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _scanned_like_pdf() -> bytes:
    """A real-bytes PDF whose pages contain only an embedded image, so
    pypdf returns whitespace.  We use a 1-byte trick: hand-write a
    minimal PDF that has no text operators."""
    # Smallest valid PDF — single empty page. pypdf will extract "" from
    # it, which is exactly the scanned-PDF signal looks_like_scanned_pdf
    # is built to detect.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000053 00000 n \n"
        b"0000000098 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n149\n%%EOF\n"
    )


def _text_pdf_with_real_text() -> bytes:
    """A genuine text PDF — pypdf finds clear sentences, OCR must NOT fire."""
    # We write a small PDF with a Hello world text stream — long enough
    # to clear the looks_like_scanned_pdf threshold.
    body = (
        "This is a real text PDF containing genuine extractable text. "
        "The Multi-Factor Authentication policy applies to all employees. "
        "Vendor security review is performed annually. "
        "Backup retention is set to thirty days for production data."
    )
    # Build a minimal but valid text-bearing PDF. Use pypdf via a
    # round-trip — much simpler than hand-rolling cross-references.
    try:
        from pypdf import PdfWriter
    except ImportError:  # pragma: no cover - dependency is in requirements.txt
        pytest.skip("pypdf not available")
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Add a content stream that draws text using the standard Helvetica.
    from pypdf.generic import (
        ContentStream,
        DecodedStreamObject,
        NameObject,
        DictionaryObject,
        TextStringObject,
        NumberObject,
        ArrayObject,
    )
    content_str = (
        f"BT\n/F1 12 Tf\n50 700 Td\n({body}) Tj\nET\n"
    )
    stream = DecodedStreamObject()
    stream.set_data(content_str.encode("latin-1"))
    page[NameObject("/Contents")] = stream
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"):     NameObject("/Font"),
                NameObject("/Subtype"):  NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            })
        })
    })
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --- tests ------------------------------------------------------------------


def test_text_pdf_unchanged_when_ocr_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("KYC_OCR_ENABLED", raising=False)
    p = tmp_path / "policy.pdf"
    p.write_bytes(_text_pdf_with_real_text())

    result = extract_from_file(p)

    assert result.extraction_method == "pdf_text"
    assert "Multi-Factor Authentication" in (result.text_preview or "")
    assert result.ocr_applied is False
    assert result.ocr_status == ""


def test_text_pdf_unchanged_even_when_ocr_enabled(tmp_path, monkeypatch):
    """OCR must only fire when pypdf returns < min_chars — a normal
    text PDF should never invoke tesseract."""
    monkeypatch.setenv("KYC_OCR_ENABLED", "true")
    # Belt-and-suspenders: even if OCR enabled, ocr_pdf_bytes should
    # not be called for a text PDF that returns substantial characters.
    called = {"pdf": 0}

    def _spy(*a, **kw):
        called["pdf"] += 1
        return "", "ocr_ok"

    monkeypatch.setattr(ext_mod, "ocr_pdf_bytes", _spy)
    p = tmp_path / "real_policy.pdf"
    p.write_bytes(_text_pdf_with_real_text())

    result = extract_from_file(p)

    assert called["pdf"] == 0, "ocr_pdf_bytes must not run for text PDFs"
    assert result.ocr_applied is False


def test_scanned_pdf_no_ocr_when_flag_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("KYC_OCR_ENABLED", raising=False)
    p = tmp_path / "scanned.pdf"
    p.write_bytes(_scanned_like_pdf())

    result = extract_from_file(p)

    assert result.ocr_applied is False
    assert result.ocr_status == ""
    # Without OCR the scanned PDF is correctly empty / pending.
    assert (result.text_preview or "").strip() == ""


def test_scanned_pdf_triggers_ocr_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("KYC_OCR_ENABLED", "true")
    # Bypass the availability probe so we don't need tesseract installed.
    monkeypatch.setattr(
        ext_mod,
        "ocr_pdf_bytes",
        lambda data, **kw: (
            "Driver Qualification File: DOT physical certificate "
            "expires 2026-12-31. Medical examiner: Jane Doe.",
            "ocr_ok",
        ),
    )

    p = tmp_path / "dot_packet.pdf"
    p.write_bytes(_scanned_like_pdf())

    result = extract_from_file(p)

    assert result.ocr_applied is True
    assert result.ocr_status == "ocr_ok"
    assert result.ocr_text_length > 0
    assert result.extraction_method == "pdf_ocr"
    assert "Driver Qualification" in (result.text_preview or "")
    # Pending must be cleared once OCR yielded text.
    assert result.pending_analysis is False


def test_scanned_pdf_degrades_cleanly_when_tesseract_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("KYC_OCR_ENABLED", "true")
    monkeypatch.setattr(
        ext_mod,
        "ocr_pdf_bytes",
        lambda data, **kw: ("", "ocr_binary_unavailable"),
    )

    p = tmp_path / "scanned_no_binary.pdf"
    p.write_bytes(_scanned_like_pdf())

    result = extract_from_file(p)

    assert result.ocr_applied is False
    assert result.ocr_status == "ocr_binary_unavailable"
    assert any(
        w.startswith("scanned_pdf_ocr_skipped") for w in result.warnings
    )
    assert result.pending_analysis is True


def test_image_triggers_ocr_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("KYC_OCR_ENABLED", "true")
    monkeypatch.setattr(
        ext_mod,
        "ocr_image_bytes",
        lambda data, **kw: ("MFA enrollment required for all administrators", "ocr_ok"),
    )

    p = tmp_path / "mfa_screenshot.png"
    p.write_bytes(_png_with_text("placeholder"))

    result = extract_from_file(p)

    assert result.ocr_applied is True
    assert result.ocr_status == "ocr_ok"
    assert result.extraction_method == "image_ocr"
    assert "MFA enrollment" in (result.text_preview or "")
    # The pre-OCR metadata-only awaiting-OCR warning must NOT be there
    # when OCR actually ran.
    assert "image_text_awaits_ocr_for_full_extraction" not in result.warnings


def test_image_degrades_cleanly_when_tesseract_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("KYC_OCR_ENABLED", "true")
    monkeypatch.setattr(
        ext_mod,
        "ocr_image_bytes",
        lambda data, **kw: ("", "ocr_module_unavailable"),
    )

    p = tmp_path / "scan.jpg"
    p.write_bytes(_png_with_text("placeholder"))

    result = extract_from_file(p)

    assert result.ocr_applied is False
    assert result.ocr_status == "ocr_module_unavailable"
    assert any(
        w.startswith("image_ocr_skipped") for w in result.warnings
    )


def test_ocr_module_helpers_handle_disabled_default(monkeypatch):
    monkeypatch.delenv("KYC_OCR_ENABLED", raising=False)
    avail = ocr_mod.check_ocr_availability()
    assert avail.available is False
    assert avail.reason == "disabled"

    text, status = ocr_mod.ocr_image_bytes(b"\x89PNG\r\n\x1a\n")
    assert text == ""
    assert status == "ocr_disabled"

    text, status = ocr_mod.ocr_pdf_bytes(b"%PDF-1.4\n%%EOF\n")
    assert text == ""
    assert status == "ocr_disabled"


def test_looks_like_scanned_pdf_threshold():
    assert ocr_mod.looks_like_scanned_pdf("") is True
    assert ocr_mod.looks_like_scanned_pdf("   \n  ") is True
    assert ocr_mod.looks_like_scanned_pdf("Hello") is True  # < 80 chars
    long_text = "MFA " * 50  # well over 80 chars
    assert ocr_mod.looks_like_scanned_pdf(long_text) is False

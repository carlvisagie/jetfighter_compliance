"""Optical character recognition for scanned PDFs and images.

Real customer compliance packets — especially DOT/FMCSA, medical, and
older policy archives — arrive as scanned PDFs or smartphone photos
that pypdf cannot read. Without OCR the platform was happily emitting
``"we organized your files"`` while extracting zero text, which is the
exact silent-failure mode flagged in the 2026-06-04 evidence-
intelligence forensic audit.

This module:

* Detects whether OCR is *available* in this environment (Python
  package present **and** the underlying ``tesseract`` / ``poppler``
  binaries actually resolve).
* Provides ``ocr_image_bytes`` and ``ocr_pdf_bytes`` helpers that
  always return a (text, status) tuple and never raise.
* Is fully config-gated by ``KYC_OCR_ENABLED`` so production can opt
  in once binaries are deployed without disturbing the existing
  metadata-only image path.

The functions return ``status`` strings the caller can record:

* ``ocr_ok``                  — text extracted (text_length > 0)
* ``ocr_empty``               — OCR ran but found no characters
* ``ocr_disabled``            — ``KYC_OCR_ENABLED`` is not truthy
* ``ocr_module_unavailable``  — ``pytesseract`` / ``pdf2image`` not
                                installed
* ``ocr_binary_unavailable``  — ``tesseract`` / ``poppler`` not on PATH
* ``ocr_failed``              — runtime exception during OCR
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Tuple

logger = logging.getLogger(__name__)

_OCR_ENV_VAR = "KYC_OCR_ENABLED"
_TRUTHY = frozenset({"1", "true", "yes", "on", "enabled"})

# Bound on how many pages we OCR in a single sync request — beyond this
# the work must be queued. Tesseract is ~1–3 seconds per page on a
# typical Render Standard instance, so 15 pages keeps p95 under 45s.
DEFAULT_OCR_MAX_PAGES = 15
DEFAULT_OCR_DPI       = 200


@dataclass
class OcrAvailability:
    available: bool
    reason:    str          # "ok", "disabled", "module_unavailable", "binary_unavailable", "probe_failed"
    detail:    str = ""     # human-readable explanation for logs


def ocr_enabled() -> bool:
    """Whether OCR is enabled by configuration.

    Defaults to OFF so local dev / CI without binaries stays quiet.
    Production opts in via ``KYC_OCR_ENABLED=true``.
    """
    return str(os.environ.get(_OCR_ENV_VAR, "false")).strip().lower() in _TRUTHY


def check_ocr_availability() -> OcrAvailability:
    """Probe whether OCR can actually run right now.

    The check is cheap (no real OCR work performed) and never raises.
    """
    if not ocr_enabled():
        return OcrAvailability(False, "disabled",
                               f"{_OCR_ENV_VAR} is not enabled")
    try:
        import pytesseract  # noqa: F401
    except ImportError as exc:
        return OcrAvailability(False, "module_unavailable",
                               f"pytesseract missing: {exc}")
    try:
        import pdf2image  # noqa: F401
    except ImportError as exc:
        # We can still OCR raw images even without pdf2image, so don't
        # disable wholesale — but record the gap for telemetry.
        logger.info("ocr: pdf2image missing — PDF OCR will be skipped: %s",
                    exc)
    try:
        import pytesseract as _pyt
        # ``get_tesseract_version`` resolves the binary on PATH and
        # raises pytesseract.TesseractNotFoundError if it's missing.
        _pyt.get_tesseract_version()
    except Exception as exc:
        return OcrAvailability(False, "binary_unavailable",
                               f"tesseract binary not resolvable: {exc}")
    return OcrAvailability(True, "ok", "")


def ocr_image_bytes(data: bytes, *, lang: str = "eng") -> Tuple[str, str]:
    """OCR a single image (PNG/JPG/TIFF/...). Returns ``(text, status)``."""
    avail = check_ocr_availability()
    if not avail.available:
        # Distinguish "disabled" from "unavailable" so callers/operators
        # can tell config gaps from environment gaps.
        return "", {
            "disabled":            "ocr_disabled",
            "module_unavailable": "ocr_module_unavailable",
            "binary_unavailable": "ocr_binary_unavailable",
        }.get(avail.reason, "ocr_failed")

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "ocr_module_unavailable"

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            text = pytesseract.image_to_string(img, lang=lang) or ""
    except Exception as exc:
        logger.warning("ocr: image OCR failed: %s", exc)
        return "", "ocr_failed"

    text = text.strip()
    if not text:
        return "", "ocr_empty"
    return text, "ocr_ok"


def ocr_pdf_bytes(
    data: bytes,
    *,
    lang: str = "eng",
    max_pages: int = DEFAULT_OCR_MAX_PAGES,
    dpi: int = DEFAULT_OCR_DPI,
) -> Tuple[str, str]:
    """OCR a PDF by rasterising each page and running tesseract.

    Bounded by ``max_pages`` so a 500-page packet cannot tar-pit the
    extraction worker. Returns ``(text, status)``.
    """
    avail = check_ocr_availability()
    if not avail.available:
        return "", {
            "disabled":            "ocr_disabled",
            "module_unavailable": "ocr_module_unavailable",
            "binary_unavailable": "ocr_binary_unavailable",
        }.get(avail.reason, "ocr_failed")

    try:
        import pdf2image
    except ImportError:
        return "", "ocr_module_unavailable"
    try:
        import pytesseract
    except ImportError:
        return "", "ocr_module_unavailable"

    try:
        images = pdf2image.convert_from_bytes(
            data, dpi=dpi, fmt="png", last_page=max(1, int(max_pages)),
        )
    except Exception as exc:
        # pdf2image raises its own PDFInfoNotInstalledError when
        # poppler is missing — surface that as the binary signal.
        msg = str(exc).lower()
        if "poppler" in msg or "pdfinfo" in msg or "pdftoppm" in msg:
            return "", "ocr_binary_unavailable"
        logger.warning("ocr: pdf2image conversion failed: %s", exc)
        return "", "ocr_failed"

    parts = []
    for img in images:
        try:
            page_text = pytesseract.image_to_string(img, lang=lang) or ""
        except Exception as exc:
            logger.warning("ocr: page OCR failed: %s", exc)
            continue
        if page_text.strip():
            parts.append(page_text)
    text = "\n".join(parts).strip()
    if not text:
        return "", "ocr_empty"
    return text, "ocr_ok"


def looks_like_scanned_pdf(extracted_text: str, *, min_chars: int = 80) -> bool:
    """Heuristic: pypdf returned almost no text → likely scanned PDF.

    Real text PDFs of even short policies return hundreds of characters
    on page one. A receipt-printer scan returns whitespace plus a few
    page-number glyphs. ``min_chars`` is the conservative threshold.
    """
    if not extracted_text:
        return True
    return len(extracted_text.strip()) < int(min_chars)

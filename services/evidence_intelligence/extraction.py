"""Text extraction from uploaded evidence (rule-based v1)."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Tuple

from .schemas import ExtractionResult

MAX_SYNC_BYTES = 2 * 1024 * 1024
MAX_PREVIEW = 8000
MAX_SNIPPET_STORE = 240

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key?|password|passwd|token|bearer|credential|auth[_-]?key)\s*[:=]\s*\S{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),                                          # AWS access key
    re.compile(r"ASIA[0-9A-Z]{16}"),                                          # AWS temp key
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),               # JWT
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                                       # GitHub PAT
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),                                       # OpenAI key pattern
    re.compile(r"(?i)private[_\s-]?key\s*[:=]\s*\S{16,}"),
]

DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".msi", ".scr", ".vbs", ".js"}


def redact_secrets(text: str) -> str:
    if not text:
        return text
    out = text
    for rx in SECRET_PATTERNS:
        out = rx.sub("[REDACTED]", out)
    return out


def safe_snippet(text: str, limit: int = MAX_SNIPPET_STORE) -> str:
    t = redact_secrets((text or "").strip())
    if len(t) > limit:
        return t[: limit - 3] + "..."
    return t


def _extract_txt(data: bytes) -> Tuple[str, str]:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc), "text_plain"
        except UnicodeDecodeError:
            continue
    return "", "decode_failed"


def _extract_pdf(data: bytes) -> Tuple[str, str]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages[:30]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts), "pdf_text"
    except ImportError:
        return "", "pdf_unavailable"
    except Exception:
        return "", "pdf_failed"


def _extract_csv(data: bytes) -> Tuple[str, str]:
    text, _ = _extract_txt(data)
    if not text:
        return "", "csv_empty"
    try:
        rows = list(csv.reader(io.StringIO(text)))
        return "\n".join(", ".join(r) for r in rows[:200]), "csv_parse"
    except Exception:
        return text[:MAX_PREVIEW], "csv_raw"


def extract_from_file(path: Path, *, size_bytes: int = 0) -> ExtractionResult:
    name = path.name
    ext = path.suffix.lower()
    result = ExtractionResult(source_file=name, mime_hint=ext)

    if ext in DANGEROUS_EXTENSIONS:
        result.ok = False
        result.pending_analysis = True
        result.errors.append("unsupported_file_type")
        result.extraction_method = "rejected_type"
        return result

    size = size_bytes or path.stat().st_size
    if size > MAX_SYNC_BYTES:
        result.pending_analysis = True
        result.warnings.append("file_too_large_for_sync_analysis")
        result.extraction_method = "pending"
        return result

    try:
        data = path.read_bytes()
    except Exception as e:
        result.ok = False
        result.errors.append(str(e)[:120])
        return result

    text = ""
    method = "none"
    if ext in (".txt", ".md", ".log", ".json", ".xml", ".html", ".htm"):
        text, method = _extract_txt(data)
        if ext == ".json":
            method = "json_text"
    elif ext == ".pdf":
        text, method = _extract_pdf(data)
        if method == "pdf_unavailable":
            result.warnings.append("pdf_extraction_unavailable")
            result.pending_analysis = True
    elif ext in (".csv",):
        text, method = _extract_csv(data)
    elif ext in (".doc", ".docx", ".xlsx", ".xls"):
        result.pending_analysis = True
        result.warnings.append("office_format_pending")
        method = "office_pending"
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        result.pending_analysis = True
        result.warnings.append("image_ocr_not_enabled_v1")
        method = "image_pending"
    else:
        text, method = _extract_txt(data)
        if not text.strip():
            result.pending_analysis = True
            result.warnings.append("unknown_format")

    text = redact_secrets(text)
    result.text_length = len(text)
    result.text_preview = safe_snippet(text, MAX_PREVIEW)
    result.extraction_method = method
    if not text.strip() and not result.pending_analysis:
        result.warnings.append("no_extractable_text")
    return result

"""Smoke test for the unauthenticated EI binaries probe.

``/healthz/ei-binaries`` exists so operators (and the deployment
loop) can verify at a glance whether the OCR + PDF rasterisation
stack is genuinely live inside the running container — not just
"configured". Without it, OCR degrades to
``ocr_binary_unavailable`` for every customer scan with no
operator visibility, which is what hid the issue when production
intake FB-1dfab13c120b uploaded images.

This test pins the response shape so future refactors cannot
silently drop fields the operator UI depends on.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_ei_binaries_returns_expected_shape():
    import server
    client = TestClient(server.app)

    r = client.get("/healthz/ei-binaries")
    assert r.status_code == 200, r.text
    body = r.json()

    for key in (
        "ok",
        "ocr_enabled",
        "pytesseract_import",
        "pdf2image_import",
        "tesseract_binary",
        "poppler_binary",
    ):
        assert key in body, f"probe missing key {key!r}: {body!r}"

    assert isinstance(body["ok"],          bool)
    assert isinstance(body["ocr_enabled"], bool)
    assert isinstance(body["tesseract_binary"], dict)
    assert isinstance(body["poppler_binary"],   dict)
    assert "available" in body["tesseract_binary"]
    assert "available" in body["poppler_binary"]


def test_healthz_ei_binaries_unauthenticated():
    """The probe is intentionally unauthenticated, like /healthz. It
    must not require an X-Ops-Key header or session cookie."""
    import server
    client = TestClient(server.app)

    r = client.get("/healthz/ei-binaries")
    assert r.status_code == 200, (
        "EI binaries probe must be reachable without ops auth so the "
        "deployment loop can verify OCR is live"
    )

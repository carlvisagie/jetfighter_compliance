"""Ensure customer-facing UI does not link to internal operations consoles."""

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

PUBLIC_PAGES = [
    "/ui/shop.html",
    "/ui/inquiry.html",
    "/ui/intake.html",
    "/ui/upload.html",
]

FORBIDDEN = [
    "/ui/control.html",
    "/ui/memory.html",
    "Operations Console",
    'href="/ui/control.html"',
    "href=\"/ui/memory.html\"",
]


def test_public_pages_have_no_ops_console_links():
    for path in PUBLIC_PAGES:
        r = client.get(path)
        assert r.status_code == 200, path
        html = r.text
        for needle in FORBIDDEN:
            assert needle not in html, f"{needle} found on {path}"


def test_shop_uses_internal_tracking_wording():
    r = client.get("/ui/shop.html")
    assert "continue internally" in r.text
    assert "operations console" not in r.text.lower()

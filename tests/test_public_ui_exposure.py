"""Comprehensive audit: public customer UI must not expose internal operator surfaces."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests.conftest import TEST_OPS_PASSWORD
UI_ROOT = Path(__file__).resolve().parents[1] / "ui"

# Customer-safe pages (served to prospects, clients, vendors).
PUBLIC_PAGES = [
    "/ui/shop.html",
    "/ui/inquiry.html",
    "/ui/intake.html",
    "/ui/upload.html",
    "/ui/continue.html",
    "/ui/index.html",
    "/ui/vendor_quote.html",
]

# Operator-only pages — must carry noindex and must not be linked from public pages.
INTERNAL_PAGES = [
    "/ui/control.html",
    "/ui/memory.html",
    "/ui/command.html",
    "/ui/webhook_test.html",
    "/ui/knowledge.html",
    "/ui/status.html",
    "/ui/inbox.html",
    "/ui/scan.html",
    "/ui/event.html",
    "/ui/healthz.html",
    "/ui/lead_discovery.html",
    "/ui/onboarding_validation.html",
    "/ui/new_client.html",
    "/ui/readiness/index.html",
    "/ui/readiness/script.html",
    "/ui/readiness/questions.html",
    "/ui/readiness/scoring.html",
    "/ui/readiness/report.html",
    "/ui/readiness/outreach.html",
    "/ui/readiness/pre-call.html",
    "/ui/readiness/follow-up.html",
]

FORBIDDEN_LINK_FRAGMENTS = [
    "/ui/control.html",
    "/ui/memory.html",
    "/ui/command.html",
    "/ui/webhook_test.html",
    "/api/memory/",
    "/api/ops/",
    'href="/ui/control.html"',
    'href="/ui/memory.html"',
    'href="/ui/command.html"',
    'href="/ui/webhook_test.html"',
    "Operations Console",
]

FORBIDDEN_PUBLIC_TERMS = [
    "operations console",
    "organism",
    "telemetry",
    "self-heal",
    "self heal",
    "internal diagnostic",
    "observability",
    "/api/memory/",
    "/api/ops/",
]

ALLOWED_PUBLIC_NAV_HREFS = {
    "/ui/shop.html",
    "/ui/inquiry.html",
    "/ui/intake.html",
    "/ui/upload.html",
}

PUBLIC_NAV_LINK_RE = re.compile(
    r'<nav class="kyc-nav"(?! kyc-nav--ops)[^>]*>.*?</nav>',
    re.DOTALL | re.IGNORECASE,
)
HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_return_200(anon_client, path: str) -> None:
    r = anon_client.get(path)
    assert r.status_code == 200, path


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_have_no_internal_links(anon_client, path: str) -> None:
    html = anon_client.get(path).text
    for needle in FORBIDDEN_LINK_FRAGMENTS:
        assert needle not in html, f"{needle!r} found on {path}"


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_have_no_internal_terms(anon_client, path: str) -> None:
    lower = anon_client.get(path).text.lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in lower, f"{term!r} found on {path}"


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_nav_only_customer_links(anon_client, path: str) -> None:
    html = anon_client.get(path).text
    match = PUBLIC_NAV_LINK_RE.search(html)
    if not match:
        return
    nav_html = match.group(0)
    for href in HREF_RE.findall(nav_html):
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        if href.startswith("http"):
            continue
        assert href in ALLOWED_PUBLIC_NAV_HREFS, f"Unexpected public nav link {href!r} on {path}"


def test_shop_uses_internal_tracking_wording(anon_client) -> None:
    html = anon_client.get("/ui/shop.html").text
    assert "continue internally" in html.lower()
    assert "operations console" not in html.lower()


@pytest.mark.parametrize("path", INTERNAL_PAGES)
def test_internal_pages_have_noindex(client, path: str) -> None:
    html = client.get(path).text.lower()
    assert "noindex" in html, f"{path} missing noindex meta"
    assert "nofollow" in html, f"{path} missing nofollow meta"


@pytest.mark.parametrize("path", INTERNAL_PAGES)
def test_internal_pages_require_login(anon_client, path: str) -> None:
    r = anon_client.get(path, follow_redirects=False)
    assert r.status_code == 302, path
    assert "/ui/login.html" in (r.headers.get("location") or "")


@pytest.mark.parametrize("path", INTERNAL_PAGES)
def test_internal_pages_not_linked_from_public_shop(anon_client, path: str) -> None:
    """Regression: shop is the main landing page."""
    shop = anon_client.get("/ui/shop.html").text
    assert path not in shop, f"Internal path {path} linked from shop.html"


def test_public_pages_list_is_complete_vs_customer_html() -> None:
    """Guardrail: new top-level customer HTML should be classified explicitly."""
    customer_candidates = {
        "shop.html",
        "inquiry.html",
        "intake.html",
        "upload.html",
        "continue.html",
        "index.html",
        "vendor_quote.html",
    }
    for name in customer_candidates:
        assert f"/ui/{name}" in PUBLIC_PAGES

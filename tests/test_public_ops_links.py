"""Ensure customer-facing UI does not link to internal operations consoles.

Consolidated into tests/test_public_ui_exposure.py; kept for backwards compatibility.
"""

from tests.test_public_ui_exposure import (
    FORBIDDEN_LINK_FRAGMENTS as FORBIDDEN,
    PUBLIC_PAGES,
    test_public_pages_have_no_internal_links as test_public_pages_have_no_ops_console_links,
    test_shop_uses_upload_first_wording,
)

__all__ = [
    "FORBIDDEN",
    "PUBLIC_PAGES",
    "test_public_pages_have_no_ops_console_links",
    "test_shop_uses_upload_first_wording",
]

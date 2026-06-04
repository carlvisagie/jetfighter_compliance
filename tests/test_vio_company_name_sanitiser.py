"""VIO company-name sanitiser — the operator must never see a URL,
empty string, or absurdly long paste as a company name.
"""
from __future__ import annotations

from services.vio_overview import _clean_company_name


def test_passes_through_normal_company_names():
    assert _clean_company_name("Apex Aerospace LLC") == "Apex Aerospace LLC"
    assert _clean_company_name("Sigma Defense Solutions Inc") == "Sigma Defense Solutions Inc"


def test_strips_whitespace_only_to_unknown():
    assert _clean_company_name("") == "Unknown"
    assert _clean_company_name("   ") == "Unknown"
    assert _clean_company_name(None) == "Unknown"


def test_extracts_apex_domain_from_full_url():
    assert _clean_company_name("http://www.example.com/path") == "example.com"
    assert _clean_company_name("https://Acme.io/upload") == "acme.io"


def test_extracts_apex_domain_from_bare_domain():
    assert _clean_company_name("www.foo.com") == "foo.com"
    assert _clean_company_name("bar.io/whatever") == "bar.io"


def test_long_paste_is_truncated_with_ellipsis():
    paste = "X" * 200
    result = _clean_company_name(paste)
    assert len(result) <= 121
    assert result.endswith("…")

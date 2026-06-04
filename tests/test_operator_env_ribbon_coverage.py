"""Doctrine guardrail: every operator-protected HTML page must wire the
environment ribbon.

Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md §2 — operators must not be
able to view counts on any internal surface without simultaneously seeing
whether the page is connected to production. The ribbon either confirms
PRODUCTION (calm green) or warns NON-PRODUCTION / UNKNOWN (red + dimmed
body), and the script also re-paints every 5 minutes so a deploy that
flips the environment is noticed.

This test reads ``PROTECTED_UI_EXACT`` and ``PROTECTED_UI_PREFIXES`` from
``services/ops_auth.py`` so it stays in lockstep with the real auth
contract; if a new operator page is added to the auth set, this test
catches the missing ribbon on the next run.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.ops_auth import PROTECTED_UI_EXACT, PROTECTED_UI_PREFIXES

_REPO = Path(__file__).resolve().parents[1]
_UI = _REPO / "ui"
_RIBBON_SCRIPT = '/ui/assets/js/env-ribbon.js'


def _ui_path(route: str) -> Path:
    return _REPO / route.lstrip("/")


def _protected_html_files() -> list[Path]:
    files: list[Path] = []
    for route in sorted(PROTECTED_UI_EXACT):
        p = _ui_path(route)
        if p.is_file():
            files.append(p)
    for prefix in PROTECTED_UI_PREFIXES:
        prefix_path = _REPO / prefix.lstrip("/")
        if prefix_path.is_dir():
            for p in sorted(prefix_path.rglob("*.html")):
                if p.is_file() and p not in files:
                    files.append(p)
    return files


_PAGES = _protected_html_files()


@pytest.mark.parametrize(
    "page",
    _PAGES,
    ids=[str(p.relative_to(_REPO)).replace("\\", "/") for p in _PAGES],
)
def test_protected_page_wires_env_ribbon(page: Path) -> None:
    """Every operator-protected page must include the env-ribbon script.

    The script is self-installing: it injects the stylesheet and the
    `#env-ribbon` element if missing, so one script tag is enough. Pages
    that still hand-roll the markup are also fine (they get the same
    re-painting behavior).
    """
    text = page.read_text(encoding="utf-8", errors="ignore")
    assert _RIBBON_SCRIPT in text, (
        f"Operator-protected page {page.relative_to(_REPO)} is missing "
        f"'<script src=\"{_RIBBON_SCRIPT}\">'. Add it just before </head>. "
        f"Doctrine: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md §2."
    )


def test_protected_page_set_is_non_empty() -> None:
    """Defensive: if PROTECTED_UI_EXACT ever empties, this test catches it
    so we do not silently pass test_protected_page_wires_env_ribbon by
    iterating over zero pages."""
    assert _PAGES, (
        "No protected operator HTML pages were discovered — either "
        "PROTECTED_UI_EXACT is empty or the ui/ tree is missing. "
        "Refusing to claim env-ribbon coverage passes vacuously."
    )

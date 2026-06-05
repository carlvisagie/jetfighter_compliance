"""Pin the L2 header minimization — the orb is the passport.

Carl, 2026-06-05:
   "the orb should contain all company information... WE USE TABS TEXT
    AS ABSOLUTE LAST RESORT. TELL THE STORY IN PICTURES!!!"

Before this change, the L2 header carried:
   · back button             (navigation — kept)
   · company name title       (DUPLICATED in orb initials + halo)
   · email subtitle          (DUPLICATED in orb satellite)
   · state pill              (DUPLICATED in orb halo colour + breathing)
   · reprocess EI button     (operator override — kept)

The duplication violated the "pictures over text" doctrine. With the
orb passport now carrying identity, state, contacts and compliance,
the header is reduced to navigation chrome + one override action.

This guard pins:

  · The title / subtitle / state pill DOM nodes are NOT built. A
    future refactor that re-introduces text-on-canvas trips this.
  · `back` and `reprocess EI` stay (they are not duplicated by the
    orb — they are actions, not identity).
  · The header sets the browser document.title to the company name,
    so OS chrome carries the identity the canvas no longer prints.
  · An aria-label on the header preserves accessibility for screen
    readers that don't read the orb.
  · The CSS for the deprecated text classes is removed so it can't
    silently start displaying things again.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS   = ROOT / "ui" / "assets" / "js" / "vio-level2.js"
CSS  = ROOT / "ui" / "assets" / "styles" / "vio.css"


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def _css() -> str:
    return CSS.read_text(encoding="utf-8")


def test_header_does_not_build_title_subtitle_state():
    src = _js()
    # The buildHeader function must not construct the title block at
    # all. We look for tell-tale class names that used to be created.
    # If a future change re-adds them, this fails.
    assert "el('div', 'vio-l2-titlewrap')" not in src, (
        "the orb passport carries identity now — buildHeader must NOT "
        "build a vio-l2-titlewrap text block (Carl 2026-06-05, 'pictures "
        "over text')"
    )
    assert "el('div', 'vio-l2-title')" not in src, (
        "buildHeader must NOT print the company name as on-canvas text "
        "(the orb's initials + browser tab title cover this)"
    )
    assert "el('div', 'vio-l2-sub')" not in src, (
        "buildHeader must NOT print the contact email as on-canvas text "
        "(the orb's east satellite encodes presence)"
    )
    assert "el('div', 'vio-l2-state')" not in src, (
        "buildHeader must NOT print the state as an on-canvas pill "
        "(the orb's halo encodes state colour + breathing)"
    )


def test_header_keeps_navigation_and_override():
    src = _js()
    assert "el('button', 'vio-l2-back')" in src, (
        "the back button is navigation chrome — it must stay (the orb "
        "doesn't have a back gesture)"
    )
    assert "el('button', 'vio-l2-reproc')" in src, (
        "the reprocess button is an operator override — it must stay "
        "(autonomy-by-default makes it rarely needed but always "
        "available)"
    )


def test_header_sets_document_title():
    src = _js()
    assert "document.title" in src, (
        "the header must set document.title to the company name so the "
        "OS bar / task switcher still answers 'which L2 am I in?'"
    )
    assert "VIO" in src, "document.title should be prefixed with VIO"


def test_header_keeps_aria_label_for_accessibility():
    src = _js()
    assert "aria-label" in src, (
        "the header must carry an aria-label naming the company + state "
        "so screen-reader users get parity with sighted users (who read "
        "the orb passport)"
    )


def test_reprocess_tooltip_describes_override_not_default():
    """The button copy must reflect that reprocess is now the OVERRIDE
    path — not the primary action. Autonomy doctrine: the freshness
    sweep is the default; this button exists for "I want it now"."""
    src = _js()
    assert "override" in src.lower() or "Override" in src, (
        "reprocess button tooltip must describe it as an override path, "
        "not the primary action (the freshness sweep is the default)"
    )


def test_unused_text_css_classes_removed():
    css = _css()
    # The text-pill CSS that used to drive the header text MUST be
    # gone. If a future change re-adds these, the visual regression
    # could reappear before anyone notices.
    for selector in (
        ".vio-l2-titlewrap",
        ".vio-l2-title ",
        ".vio-l2-sub ",
        ".vio-l2-state ",
    ):
        assert selector not in css, (
            f"deprecated header CSS '{selector.strip()}' must stay "
            "removed — re-adding it lets text creep back onto the L2 "
            "canvas"
        )


def test_reprocess_button_pushed_to_right_edge():
    """With the middle title block removed, the reprocess override
    needs `margin-left: auto` so the header reads as
    `← back | … | reprocess` instead of `← back | reprocess | …`."""
    css = _css()
    assert ".vio-l2-reproc { margin-left: auto; }" in css or (
        ".vio-l2-reproc" in css and "margin-left: auto" in css
    ), (
        "header layout must push reprocess to the right edge — "
        "otherwise it sits awkwardly next to the back button after "
        "the title block was removed"
    )

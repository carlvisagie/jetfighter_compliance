"""Regression guard: VIO Level 1 must render the sketch.

Pins the contract created by the 2026-06-05 sketch-faithful rebuild
(docs/VIO_SOURCE_BRIEF.md). Two failure modes this catches:

1. **Silent invisible render.** vio.js used to call VIO_BOOT.ready()
   immediately after renderTraces() with no check on whether any
   .vio-trace actually got appended. A renderer that quietly produced
   nothing (or appended nodes with zero size) would tear the boot
   overlay down and leave a black page. The fixed contract: ready()
   only fires if `.vio-trace` or `.vio-empty` is present; otherwise
   VIO_BOOT.fault('render-empty', ...) is called so the operator sees
   a visible diagnostic.

2. **Drift from the sketch grammar.** The brief's §5 grammar — square /
   triangle / hexagon / circle / diamond / starburst, coloured green /
   amber / red / blue / grey — is the design source. A future refactor
   that drops one of these primitives loses a piece of the operator's
   reading vocabulary.

This guard is pure file inspection (no Node/JS execution) so it runs
in the same pytest pass as the other VIO guards.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT     = Path(__file__).resolve().parents[1]
VIO_JS   = ROOT / "ui" / "assets" / "js" / "vio.js"
VIO_CSS  = ROOT / "ui" / "assets" / "styles" / "vio.css"
BRIEF_MD = ROOT / "docs" / "VIO_SOURCE_BRIEF.md"
SKETCH   = ROOT / "docs" / "assets" / "vio_sketch.jpeg"


@pytest.fixture(scope="module")
def vio_js() -> str:
    return VIO_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vio_css() -> str:
    return VIO_CSS.read_text(encoding="utf-8")


# ── Visibility safeguard ────────────────────────────────────────────────────

def test_ready_only_fires_after_traces_paint(vio_js: str) -> None:
    """VIO_BOOT.ready() must be gated on `.vio-trace` or `.vio-empty`
    actually being present in the DOM. Without this, an empty-render
    bug tears the boot overlay down and leaves a black screen."""
    assert "querySelectorAll('.vio-trace, .vio-empty')" in vio_js, (
        "expected vio.js to count rendered .vio-trace/.vio-empty "
        "nodes before calling VIO_BOOT.ready()"
    )
    # And we must call fault() on the empty-render branch so the
    # operator sees a diagnostic, not a void.
    assert "render-empty" in vio_js, (
        "expected vio.js to call VIO_BOOT.fault('render-empty', ...) "
        "when the renderer produces zero visible nodes"
    )


# ── Sketch event vocabulary (brief §5) ──────────────────────────────────────

def test_sketch_shape_primitives_present(vio_js: str) -> None:
    """All six sketch primitives must be implementable in vio.js."""
    for prim in ("_svgSquare", "_svgTriangle", "_svgHexagon",
                 "_svgCircle", "_svgDiamond", "_svgStarburst"):
        assert prim in vio_js, (
            f"missing sketch primitive {prim!r} in vio.js — "
            "the brief's §5 shape grammar requires all six"
        )


def test_event_types_cover_backend_timeline(vio_js: str) -> None:
    """vio.js must handle every event type produced by
    services/vio_overview.py `_build_timeline`. If the backend grows
    a new event type and vio.js doesn't know about it, it'll silently
    fall back to a generic circle — losing meaning."""
    backend_types = {
        "intake", "upload", "analysis", "gap",
        "confirmation", "payment", "error", "complete",
    }
    for t in backend_types:
        assert f"'{t}'" in vio_js or f"\"{t}\"" in vio_js, (
            f"vio.js does not reference event type {t!r}; "
            "the backend produces it and the renderer must map it"
        )


def test_status_color_tokens_match_brief(vio_js: str) -> None:
    """Color tokens (green/amber/red/blue/grey) must all appear as
    STATUS_COLOR values. The brief locks this palette."""
    for color in ("green", "amber", "red", "blue", "grey"):
        assert f"'{color}'" in vio_js, (
            f"missing color token {color!r} in STATUS_COLOR; "
            "brief §5 requires this palette"
        )


# ── Sketch geometry (the row, the orb, the spine) ───────────────────────────

def test_identity_orb_styled_in_css(vio_css: str) -> None:
    """The new identity orb selector must exist in the CSS — without
    it the renderer paints an unstyled DOM node and the operator sees
    a tiny grey box where the BIG sketch circle should be."""
    assert ".vio-id-orb" in vio_css, (
        "expected .vio-id-orb selector in vio.css — the sketch's "
        "BIG left circle. Renderer creates the node; CSS makes it big."
    )


def test_event_shape_styled_in_css(vio_css: str) -> None:
    """Event shapes must have colour rules driven by data-color."""
    for color in ("green", "amber", "red", "blue", "grey"):
        sel = f'.vio-event[data-color="{color}"]'
        assert sel in vio_css, (
            f"missing CSS for {sel}; without it the colour palette "
            "from brief §5 is invisible"
        )


def test_legacy_backbone_hidden(vio_css: str) -> None:
    """The sketch is a timeline, not a fixed stage bar. The legacy
    backbone strip must be hidden (markup retained for compat)."""
    assert ".vio-backbone { display: none; }" in vio_css, (
        "expected .vio-backbone hidden in vio.css — the sketch's "
        "spine is a timeline, the old stage-bar legend is misleading"
    )


def test_only_one_motion_loop_per_doctrine(vio_css: str) -> None:
    """Doctrine §5: stillness is baseline; motion only for
    actively-waiting/urgent. Keyframes are allowed but they must be
    the named 'breathe' family — no rogue spin/bounce/wobble."""
    # We only assert what motion IS present, not what's absent; CSS
    # comments and other selectors are free to mention motion.
    # The point is: any animated element must use the breathe keyframes.
    assert "@keyframes vio-breathe" in vio_css
    assert "@keyframes vio-id-breathe" in vio_css


def test_level2_mount_respects_hidden_attribute(vio_css: str) -> None:
    """The silent killer behind every "VIO is dark" report (2026-06-04
    and 2026-06-05): `.vio-level2-mount` is defined with `display: grid`
    and `background: var(--vio-bg)`. The HTML element has the `hidden`
    attribute by default. The browser's UA stylesheet rule
    `[hidden] { display: none }` has lower specificity than
    `.vio-level2-mount { display: grid }`, so without an explicit
    override the mount renders as a 1920x1080 dark overlay at z-index
    200, hiding the entire VIO surface below the env-ribbon.

    Diagnosis was only possible via CDP `document.elementFromPoint(x, y)`
    showing that every point below the env-ribbon resolved to the L2
    mount, not the trace beneath it.

    The fix is an explicit `.vio-level2-mount[hidden] { display: none }`
    rule. If this rule is ever removed by a refactor, every operator
    sees a black page again. This test stops that."""
    assert ".vio-level2-mount[hidden]" in vio_css, (
        "missing `.vio-level2-mount[hidden]` rule — without it the L2 "
        "mount overlays the entire viewport and hides VIO. See the "
        "comment above this rule in ui/assets/styles/vio.css for the "
        "incident backstory."
    )
    # And it MUST set display:none — anything else doesn't actually
    # collapse the overlay.
    idx = vio_css.find(".vio-level2-mount[hidden]")
    snippet = vio_css[idx:idx + 200]
    assert "display: none" in snippet, (
        "the `.vio-level2-mount[hidden]` rule must set `display: none` "
        "— anything else leaves the overlay covering the page"
    )


# ── Brief enshrined in repo ─────────────────────────────────────────────────

def test_brief_enshrined() -> None:
    """The canonical source brief and Carl's sketch image must live
    in-repo so they can't be lost."""
    assert BRIEF_MD.exists(), (
        f"expected the brief at {BRIEF_MD} — VIO's canonical design "
        "source must live in the repo, not in a download folder"
    )
    assert SKETCH.exists(), (
        f"expected the authoritative sketch at {SKETCH} — every VIO "
        "change must be reconcilable against the sketch"
    )

    text = BRIEF_MD.read_text(encoding="utf-8")
    # Spot-check the bindings the brief locks in.
    for needed in (
        "Cursor-Ready Source Brief",
        "Company identity orb",
        "starburst",
        "Production only",
    ):
        assert needed in text, (
            f"brief at {BRIEF_MD} is missing expected anchor {needed!r}"
        )

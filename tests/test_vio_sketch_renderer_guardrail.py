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


def test_no_legacy_vio_orb_selector_in_css(vio_css: str) -> None:
    """The platform-orb strip at the top of vio.html uses class
    `.vio-orb` (different element from the trace identity orb, same
    class name). The pre-sketch renderer also targeted `.vio-orb`
    for the trace identity orb, with later-in-cascade rules that
    forced 28×28 circles with display:flex. Those rules silently
    poisoned the platform-orb pill layout — the screenshot at
    2026-06-05 09:45 showed the orb names mashed together
    ("KnowLLearnDObservEvenidePcProj…") because the platform orbs
    were getting trace-orb styles.

    Sketch-faithful renderer uses `.vio-id-orb`. The legacy `.vio-orb`
    bare-class rule (the one with `width: 28px; height: 28px` for the
    trace orb) was removed in commit ee90b21+1. This guard ensures it
    cannot come back without somebody noticing they're poisoning the
    platform-orb strip again.

    The .vio-orb-letter / .vio-orb-name / .vio-orb-arrow rules
    around line ~141 are FINE — they're the platform-orb pill
    selectors, not the trace-orb identity selectors. The forbidden
    pattern is the bare `.vio-orb { width: 28px... }` legacy rule."""
    # Forbidden: the legacy trace-orb rule had width:28px paired with
    # height:28px in a `.vio-orb {}` block.
    bad_signature = "width: 28px"
    if bad_signature in vio_css:
        # Only flag if it appears inside what looks like a `.vio-orb`
        # rule body (not other selectors that may legitimately use 28px).
        for chunk in vio_css.split("}"):
            head = chunk.lstrip()
            if head.startswith(".vio-orb ") or head.startswith(".vio-orb{"):
                assert "width: 28px" not in chunk, (
                    "legacy `.vio-orb { width: 28px }` rule is back — "
                    "this poisons the platform-orb pill strip. "
                    "Use `.vio-id-orb` for the trace identity orb."
                )


def test_static_assets_must_revalidate(server_py_text: str) -> None:
    """Cache discipline: /ui/assets/* must be served with
    `Cache-Control: no-cache, must-revalidate` so browsers always
    revalidate CSS/JS against the server (cheap 304 in the common
    case, fresh bytes when something changed).

    The previous `max-age=3600` policy is what made the 2026-06-05
    "WTF?" incident's recovery take an extra hard-refresh step:
    operators saw a deployed page pointing at hour-old cached CSS
    that no longer matched the renderer. Unacceptable for a primary
    surface. Pin the discipline so it cannot regress."""
    # The bad pattern that bit us — must not come back for /ui/assets/.
    bad = 'response.headers.setdefault("Cache-Control", "public, max-age=3600")'
    assert bad not in server_py_text, (
        "server.py still has `Cache-Control: public, max-age=3600` for "
        "/ui/assets/*. That is what caused the 2026-06-05 stale-CSS "
        "incident. Use `no-cache, must-revalidate` instead."
    )
    # And the good policy must be there.
    assert 'Cache-Control" = "no-cache, must-revalidate"' in server_py_text.replace("'", '"') \
        or 'must-revalidate' in server_py_text, (
        "server.py must set `Cache-Control: no-cache, must-revalidate` "
        "for /ui/assets/* responses"
    )


@pytest.fixture(scope="module")
def server_py_text() -> str:
    return (ROOT / "server.py").read_text(encoding="utf-8")


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


# ── L2 skeleton must survive a missing axis ─────────────────────────────────

@pytest.fixture(scope="module")
def vio_l2_js() -> str:
    return (ROOT / "ui" / "assets" / "js" / "vio-level2.js").read_text(encoding="utf-8")


def test_l2_drawspine_defends_against_missing_axis(vio_l2_js: str) -> None:
    """The silent killer behind every "L2 is empty / just shows overview"
    report from 2026-06-05: `renderSkeletonSpine` calls
    `drawSpine(svg, company)` without passing an `axis`, but `drawSpine`
    used to read `axis.tMin` and `axis.timeToX(...)` unconditionally.

    Because `openLevel2` is `async`, the sync `TypeError: Cannot read
    properties of undefined (reading 'tMin')` became an unhandled
    promise rejection — silent to console-light operators. The fetch
    after the skeleton never even fired, leaving a black canvas and
    only the default "overview" side title. Every L2 click looked
    broken from the operator's seat.

    The fix is one line: `if (!axis) axis = _timeAxis(detail);` at the
    top of `drawSpine`. _timeAxis(undefined) returns a total axis
    anchored at "now", which is the right skeleton behaviour. If this
    guard ever regresses, L2 silently breaks again."""
    sig_idx = vio_l2_js.find("function drawSpine(")
    assert sig_idx >= 0, "drawSpine() must exist in vio-level2.js"
    # Inspect the first ~600 chars of the function body.
    body = vio_l2_js[sig_idx:sig_idx + 800]
    assert "if (!axis)" in body and "_timeAxis(" in body, (
        "drawSpine() must default `axis` when not supplied — without "
        "this guard the skeleton render crashes silently inside the "
        "async openLevel2() and L2 stays a black canvas with only "
        "'overview' visible. See `axis.tMin` reference downstream."
    )


def test_l2_load_failure_calls_vio_boot_fault(vio_l2_js: str) -> None:
    """If the L2 landscape fetch fails (network, 5xx, malformed JSON,
    etc.), the side-panel hint is easy to miss against a black canvas.
    The defensive boot watchdog already exists for L1; L2 must use the
    same escape hatch so operators always see a visible diagnostic.

    This pins that the catch block in openLevel2 calls
    `window.VIO_BOOT.fault(...)`. Without it, future regressions in
    the network layer or backend payload shape will reproduce the
    "everything looks black, no idea what broke" experience."""
    catch_idx = vio_l2_js.find("'could not load landscape:")
    assert catch_idx >= 0, "L2 must surface load failures via side hint"
    window = vio_l2_js[catch_idx:catch_idx + 600]
    assert "VIO_BOOT" in window and "fault(" in window, (
        "openLevel2() catch block must call window.VIO_BOOT.fault(...) "
        "so a failed landscape load surfaces a visible diagnostic "
        "instead of a silent black canvas"
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

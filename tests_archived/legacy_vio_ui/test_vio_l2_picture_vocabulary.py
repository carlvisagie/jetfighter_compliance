"""VIO L2 — pictogram vocabulary + multi-expressive spine guards.

Carl 2026-06-05, after the river/now/stage-backbone landed:

    "even pictures, graphics, animations, gifs, jpeg, if something is
     appropriate use it go hog wild with your imagination"

    "the timeline itself must convey a myriad of information and
     situations"

    "thicker lines for some things thinner for others a broken line
     for some a choked out line in some cases whatever the imagination
     can come up with to help tell the story without words text or
     old tech"

This guard pins three things the icon-era VIO must always honour:

  1. Each event kind renders as a RICH PICTOGRAM, not a bare circle
     or square. Operators must read the *kind* from the picture, not
     by hovering for a tooltip.

  2. The spine line itself is MULTI-EXPRESSIVE — it can swell, narrow,
     choke (stall), and break (critical/high finding scar). All four
     modes must remain in the renderer.

  3. The ICON PALETTE utility classes ship and are tinted per-kind so
     the picture's colour also carries severity.

If any of these regress, the timeline goes back to looking like a
strip of identical dots and the operator loses glance-info.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
L2_JS     = REPO_ROOT / "ui" / "assets" / "js"     / "vio-level2.js"
VIO_CSS   = REPO_ROOT / "ui" / "assets" / "styles" / "vio.css"


# ── (1) Every event kind has its own pictogram drawer ───────────────────
def test_every_event_kind_has_an_icon_drawer():
    js = L2_JS.read_text(encoding="utf-8")
    drawers = (
        "_iconPaper",
        "_iconGap",
        "_iconIssue",
        "_iconPhase",
        "_iconMilestone",
        "_iconConfirmation",
        "_iconPayment",
        "_iconFinding",
        "_iconBroker",
    )
    for fn in drawers:
        assert f"function {fn}(" in js, (
            f"Pictogram drawer {fn}() is missing. Every event kind must "
            f"render as a recognizable picture, not a bare shape."
        )


def test_shape_dispatcher_uses_icon_drawers():
    """`_shapeForEvent` must dispatch into the icon drawers — i.e. it
    can't just return a `<rect>` or `<circle>` like the old version."""
    js = L2_JS.read_text(encoding="utf-8")
    start = js.find("function _shapeForEvent(")
    assert start != -1, "_shapeForEvent missing"
    end = js.find("\n  function ", start + 1)
    body = js[start:end if end != -1 else start + 4000]
    for fn in ("_iconPaper", "_iconGap", "_iconIssue", "_iconPhase",
               "_iconMilestone", "_iconPayment", "_iconFinding", "_iconBroker"):
        assert fn in body, (
            f"_shapeForEvent must call {fn} — otherwise that event kind "
            f"loses its pictogram and reverts to a generic shape."
        )


def test_icon_group_carries_kind_class():
    """The pictogram <g> must carry both `vio-icon` and a per-kind
    `vio-icon-${name}` class so the CSS palette can tint it."""
    js = L2_JS.read_text(encoding="utf-8")
    # Look in _shapeForEvent body for the class assignment.
    start = js.find("function _shapeForEvent(")
    end   = js.find("\n  function ", start + 1)
    body  = js[start:end]
    assert "'vio-icon vio-icon-'" in body, (
        "Icon group must carry both 'vio-icon' and 'vio-icon-${name}' "
        "classes so palette CSS applies."
    )
    assert "_iconNameFor(" in body, (
        "_iconNameFor() drives the per-kind class — missing means all "
        "icons would share the same class and lose their per-sub variants."
    )


# ── (2) Spine itself is multi-expressive ────────────────────────────────
def test_spine_river_chokes_on_stalls():
    """When two consecutive events are more than 24h apart, the river
    must narrow to a hairline through that window. Without this, a
    stalled intake looks identical to a busy one."""
    js = L2_JS.read_text(encoding="utf-8")
    start = js.find("function _drawSpineRiver(")
    assert start != -1, "_drawSpineRiver missing"
    end = js.find("\n  function ", start + 1)
    body = js[start:end]
    assert "STALL_MS" in body, (
        "Stall detection constant missing — the river won't choke "
        "during long silences."
    )
    assert "stallMask" in body, (
        "_drawSpineRiver must build a per-bucket stall mask and use it "
        "to collapse the river thickness through stall windows."
    )
    assert "STALL_HALF" in body, (
        "STALL_HALF constant missing — choked thickness is undefined."
    )


def test_spine_scars_render_on_critical_findings():
    """Critical/high findings must overlay a red X-scar on the river
    at the finding's X. The scar is the line's `broken` mode — a
    word-free way to say 'this is where it failed'."""
    js = L2_JS.read_text(encoding="utf-8")
    assert "function _drawSpineScars(" in js, (
        "_drawSpineScars() missing — critical findings won't visibly "
        "break the river."
    )
    # And drawSpine must actually call it.
    start = js.find("function drawSpine(")
    end   = js.find("\n  function ", start + 1)
    body  = js[start:end]
    assert "_drawSpineScars(" in body, (
        "drawSpine() must call _drawSpineScars() so the scars actually "
        "render. Defining the function isn't enough."
    )


def test_spine_live_tip_is_static_per_motion_discipline():
    """The live-tip glow at the end of the past river is STATIC —
    recent activity is not a demand for attention, so it must not
    animate (per VIO motion discipline). The CSS must not attach any
    @keyframes animation to .vio-l2-spine-livetip."""
    css = VIO_CSS.read_text(encoding="utf-8")
    # Find the .vio-l2-spine-livetip block(s) and assert no `animation:`
    blocks = re.findall(r"\.vio-l2-spine-livetip[^{]*\{[^}]*\}", css)
    assert blocks, "Live-tip CSS rule missing"
    for b in blocks:
        assert "animation:" not in b, (
            "Live-tip must NOT animate — motion discipline says continuous "
            "motion is only for unresolved demands. Recent activity is "
            "not a demand."
        )


# ── (3) Icon palette utility classes ship in CSS ───────────────────────
def test_icon_palette_utility_classes_present():
    css = VIO_CSS.read_text(encoding="utf-8")
    for cls in (
        ".vio-icon",
        ".vio-icon-fill",
        ".vio-icon-outline",
        ".vio-icon-stroke",
        ".vio-icon-glyph",
    ):
        assert cls in css, (
            f"Icon palette class {cls} missing — pictogram drawers "
            f"rely on it for consistent line-work."
        )


def test_per_kind_icon_tints_present():
    """Each event kind must re-tint at least one icon utility so the
    pictogram's colour also signals severity. Skip kinds whose
    pictogram is intentionally neutral (paper)."""
    css = VIO_CSS.read_text(encoding="utf-8")
    for kind in ("gap", "issue", "phase", "milestone", "confirmation",
                 "payment", "finding", "broker"):
        # Match any rule whose selector starts with .vio-tle-${kind}
        # and contains an icon-utility class — keeps the test robust
        # to small selector shuffling.
        pattern = rf"\.vio-tle-{kind}[^{{]*\.vio-icon-[a-z-]+[^{{]*\{{"
        assert re.search(pattern, css), (
            f"No .vio-tle-{kind} .vio-icon-* CSS rule found — that kind's "
            f"pictogram will draw in the default tint and lose its "
            f"severity signal."
        )

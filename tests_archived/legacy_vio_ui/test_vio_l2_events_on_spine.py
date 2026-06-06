"""VIO L2 — everything ON the timeline (2026-06-05).

Carl's directive after the sketch-faithful orb landed:

    "now let us put everything ON THE TIMELINE instead of under
     over below"

The legacy cluster system (computeBranches/spreadClusters/drawBranch
+ docs-papers/missing/findings labelled tile boxes above and below
the spine) is no longer the active render path. Each unit of company
history is a single shape on the spine at its real timestamp, per
the hand sketch's grammar:

    □  paper        — uploaded or generated document
    ▽  gap          — missing document (below spine, dashed)
    ▲  issue        — context flag / urgent / deadline (above spine)
    ⬡  phase        — pipeline-stage completion
    ○  milestone    — tier approval, etc.
    ◇  payment      — payment decision
    ✱  finding      — surfaced anomaly
    ✱  broker       — end-of-journey completion (slightly bigger)

This file pins:
  - the new compute/draw functions exist and the active render path
    calls them
  - the active renderLandscape does NOT call the legacy cluster
    layout helpers
  - the CSS ships the shape classes the renderer emits

If a future refactor accidentally re-enables clusters, or removes a
shape class, these guards trip.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
L2_JS     = REPO_ROOT / "ui" / "assets" / "js"     / "vio-level2.js"
VIO_CSS   = REPO_ROOT / "ui" / "assets" / "styles" / "vio.css"


# ── New flat-timeline helpers exist ──────────────────────────────────────
def test_timeline_event_compute_and_draw_helpers_exist():
    js = L2_JS.read_text(encoding="utf-8")
    assert "function computeTimelineEvents(" in js, (
        "computeTimelineEvents() must exist — it's the spine event flattener."
    )
    assert "function drawTimelineEvents(" in js, (
        "drawTimelineEvents() must exist — it positions shapes on the spine."
    )
    assert "function drawTimelineEvent(" in js, (
        "drawTimelineEvent() must exist — per-event SVG emitter."
    )
    assert "function _shapeForEvent(" in js, (
        "_shapeForEvent() must exist — the shape vocabulary lookup."
    )
    assert "function _hexagon(" in js, "hexagon primitive missing"
    assert "function _starburst(" in js, "starburst primitive missing"


# ── Active render path uses the timeline events, not clusters ───────────
def test_renderLandscape_uses_timeline_events_not_clusters():
    """renderLandscape must call computeTimelineEvents + drawTimelineEvents,
    and MUST NOT call the legacy computeBranches / drawBranch / spreadClusters
    helpers (which are still defined as dormant code but should never run)."""
    js = L2_JS.read_text(encoding="utf-8")
    start = js.find("function renderLandscape(")
    assert start != -1, "renderLandscape missing"
    end = js.find("\n  }\n", start)
    assert end != -1, "renderLandscape body not found"
    body = js[start:end]

    # renderLandscape may delegate to _renderLandscapeInner; check both.
    inner_start = js.find("function _renderLandscapeInner(")
    inner_body  = js[inner_start:js.find("\n  }\n", inner_start)] if inner_start != -1 else ""
    combined    = body + inner_body

    assert "computeTimelineEvents(" in combined, (
        "renderLandscape (or its inner delegate) must call computeTimelineEvents(detail, axis)"
    )
    assert "drawTimelineEvents(" in combined, (
        "renderLandscape (or its inner delegate) must call drawTimelineEvents(svg, events, spineY)"
    )

    # Legacy cluster helpers must NOT be called from the active body.
    for legacy in ("computeBranches(", "drawBranch(", "spreadClusters("):
        assert legacy not in combined, (
            f"renderLandscape still calls legacy cluster helper {legacy!r} "
            f"— Carl 2026-06-05: 'put everything ON THE TIMELINE instead "
            f"of under over below'. Comment it out or remove it."
        )


# ── Shape vocabulary classes ship in JS ─────────────────────────────────
def test_shape_kind_classes_emitted_by_renderer():
    """Each kind of event must get a `vio-tle-<kind>` class so the CSS
    can style it. If a kind disappears, that whole event type goes
    invisible on the spine."""
    js = L2_JS.read_text(encoding="utf-8")
    # The class name template lives in drawTimelineEvent().
    assert "vio-tle-${ev.kind}" in js, (
        "drawTimelineEvent must set class `vio-tle-${ev.kind}` so per-kind "
        "CSS rules apply."
    )
    # Every kind that computeTimelineEvents emits must be a real string.
    for kind in (
        "'paper'", "'gap'", "'issue'", "'phase'",
        "'milestone'", "'confirmation'", "'payment'",
        "'finding'", "'broker'",
    ):
        assert f"kind: {kind}" in js, (
            f"computeTimelineEvents must emit at least one event with kind {kind} "
            f"(or the corresponding shape will never appear on the spine)."
        )


# ── Shape vocabulary classes ship in CSS ────────────────────────────────
def test_shape_kind_classes_styled_in_css():
    """Each emitted kind class must have a corresponding CSS rule, or
    its shape will render in the default-circle fallback colour with
    no visual distinction."""
    css = VIO_CSS.read_text(encoding="utf-8")
    for kind in (
        "paper", "gap", "issue", "phase",
        "milestone", "confirmation", "payment",
        "finding", "broker",
    ):
        assert f".vio-tle-{kind}" in css, (
            f"CSS rule for .vio-tle-{kind} missing — that event kind "
            f"will render with no distinguishing style."
        )


def test_gap_shape_is_dashed_outline():
    """Missing/gap shapes must be dashed (per sketch convention for
    'not yet supplied'). A solid-stroke gap would visually merge with
    a real document.

    We allow EITHER the legacy `.vio-tle-gap .vio-tle-shape` selector
    OR the icon-era `.vio-tle-gap .vio-icon-*` selector to carry the
    dasharray — the guard pins the *visual intent* (gap = dashed) not
    the exact rule path, so the icon refactor doesn't trip it.
    """
    css = VIO_CSS.read_text(encoding="utf-8")
    # Scan every rule whose selector starts with `.vio-tle-gap` and
    # confirm at least one of them carries stroke-dasharray.
    import re
    blocks = re.findall(r"\.vio-tle-gap[^{]*\{[^}]*\}", css)
    assert blocks, "No .vio-tle-gap CSS rules found at all"
    assert any("stroke-dasharray" in b for b in blocks), (
        "Some .vio-tle-gap rule must set stroke-dasharray — sketch "
        "convention: missing = dashed outline, not solid. The icon "
        "refactor must not lose this."
    )


# ── Tooltip / title element preserved (label without canvas text) ───────
def test_each_event_emits_svg_title_for_hover_label():
    """The canvas itself stays text-free (Carl: pictures > words),
    but the operator still needs to know which paper / which gap a
    shape represents. The SVG <title> element provides that on hover."""
    js = L2_JS.read_text(encoding="utf-8")
    start = js.find("function drawTimelineEvent(")
    assert start != -1
    # Find the END of the function (next top-level `function ` or end of
    # ~3000 chars, whichever is sooner). Looking by chars alone misses
    # the title element once the function grew to include the bundle
    # count badge.
    end = js.find("\n  function ", start + 1)
    if end == -1:
        end = start + 4000
    body = js[start:end]
    assert "svgEl('title')" in body, (
        "drawTimelineEvent must emit an SVG <title> child so hovering "
        "a shape reveals its label without putting text on the canvas."
    )


# ── Side rule: above / on / below ───────────────────────────────────────
def test_event_side_offsets_correct():
    """Off-spine kinds must offset 30px above or below the spine, not
    cluster far away like the old layout. Pin the constant + the
    offset arithmetic."""
    js = L2_JS.read_text(encoding="utf-8")
    assert "TL_OFFSET" in js, "TL_OFFSET constant must exist"
    assert "spineY - TL_OFFSET" in js, "above-spine offset missing"
    assert "spineY + TL_OFFSET" in js, "below-spine offset missing"

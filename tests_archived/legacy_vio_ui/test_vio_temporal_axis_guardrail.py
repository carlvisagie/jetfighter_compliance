"""Pin the temporal-axis + pace-markers contract for the L1 spine.

Carl, 2026-06-05: "real per-event timestamps (currently events are
evenly spaced)" + "pace markers below the spine (sketch's ▲ slow /
fast-smooth / slower)".

Before this change, L1 placed events at `LAYOUT.spineX0 + i *
LAYOUT.spineEventGap` — pure index-based, ignored timestamps. A
30-day-old company with 4 events read identically to a 1-hour-old
company with 4 events. That throws away the time-shape of the journey
the sketch is built to communicate.

These guards pin:

  · `_eventAxis(events)` exists and exposes `xFor(event)`.
  · The axis falls back to index-based positioning when timestamps
    are missing (no crash, no empty trace — defensive).
  · The axis is temporal when every event has a parseable UTC.
  · `_drawPaceMarkers` exists and renders only when there are ≥ 2
    events AND the axis is temporal (no markers on empty / index
    fallback / single-event traces).
  · Pace bands are named `fast` / `smooth` / `slow` and the data-pace
    attribute is set on each marker (drives the CSS encoding).
  · CSS for `.vio-pace` and its band variants is present in vio.css.
  · buildSpine / buildTrace consume the axis (signature includes it).

A future refactor that drops timestamps in favour of index spacing —
or omits the pace markers — trips this test.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS   = ROOT / "ui" / "assets" / "js" / "vio.js"
CSS  = ROOT / "ui" / "assets" / "styles" / "vio.css"


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def _css() -> str:
    return CSS.read_text(encoding="utf-8")


# ── axis ───────────────────────────────────────────────────────────────


def test_event_axis_function_exists():
    assert "function _eventAxis(" in _js(), (
        "_eventAxis(events) must exist in vio.js — it is the public "
        "contract the spine uses to map events to x-coordinates"
    )


def test_axis_exposes_xfor_method():
    src = _js()
    assert "xFor:" in src, (
        "the axis object must expose xFor(event) so callers can ask "
        "for an event's x without knowing the underlying scale"
    )


def test_axis_falls_back_when_timestamps_missing():
    """An index-based fallback must exist so legacy payloads (missing
    .utc on events) still render. Otherwise the trace breaks silently."""
    src = _js()
    # The fallback is the index-based path. We assert both the
    # detection (allStamped) and the fallback math are present.
    assert "allStamped" in src, (
        "axis must check whether every event is stamped (allStamped) "
        "to decide between temporal and index modes"
    )
    assert "LAYOUT.spineX0 + i * LAYOUT.spineEventGap" in src, (
        "index-based fallback math must remain in vio.js — it's what "
        "keeps untimestamped traces rendering instead of crashing"
    )


def test_axis_uses_real_utc_when_stamped():
    src = _js()
    assert "Date.parse(ev.utc)" in src or "Date.parse(ev && ev.utc" in src, (
        "axis must Date.parse(event.utc) to convert ISO strings into "
        "comparable numbers for temporal positioning"
    )
    assert "tMin" in src and "tMax" in src, (
        "axis must compute tMin / tMax to span the visible timeline"
    )


def test_axis_clamps_span_to_readable_range():
    """Single-event or simultaneous-event traces must not divide by
    zero, and 90-day timelines must not blow up the row width."""
    src = _js()
    assert "(tMax - tMin) || 1" in src, (
        "axis must guard against zero range (single event / identical "
        "timestamps) so xFor doesn't return NaN / Infinity"
    )
    assert "maxSpan" in src and "minSpan" in src, (
        "axis must clamp the visual span (minSpan/maxSpan) so 1-day "
        "and 90-day traces both stay legible in the L1 row"
    )


# ── buildTrace + buildSpine consume the axis ───────────────────────────


def test_buildtrace_constructs_and_passes_axis():
    src = _js()
    assert "const axis = _eventAxis(events)" in src, (
        "buildTrace must construct the axis ONCE and pass it down — "
        "two axes for the same trace would produce mismatched event "
        "and spine positions"
    )
    assert "buildSpine(company, events, spineEndX, axis)" in src, (
        "buildSpine must receive the axis from buildTrace so caller "
        "and renderer agree on x-positions"
    )


def test_buildspine_uses_axis_xfor_for_events():
    src = _js()
    # The temporal positioning must be axis.xFor(ev), NOT the old
    # index-based math sitting inline.
    assert "axis.xFor(ev)" in src, (
        "buildSpine must place event shapes via axis.xFor(ev) — the "
        "old index-based math inside buildSpine is the regression "
        "this guard exists to prevent"
    )


# ── pace markers ───────────────────────────────────────────────────────


def test_drawpace_markers_function_exists():
    src = _js()
    assert "function _drawPaceMarkers(" in src, (
        "_drawPaceMarkers must exist — it draws the sketch's slow / "
        "fast-smooth / slower triangles below the spine"
    )


def test_pace_markers_only_render_for_temporal_two_plus():
    src = _js()
    # The pace-markers function must short-circuit when there are <2
    # events OR the axis is index-based. Otherwise it'd draw markers
    # on noise.
    assert "events.length < 2" in src, (
        "pace markers must not render when < 2 events (no interval "
        "to compute)"
    )
    assert "axis.temporal" in src, (
        "pace markers must only render when the axis is temporal — "
        "index spacing produces no meaningful rhythm"
    )


def test_pace_bands_are_named_fast_smooth_slow():
    src = _js()
    for band in ("fast", "smooth", "slow"):
        assert f"'{band}'" in src, (
            f"pace band '{band}' must be present — these are the three "
            "discrete categories the eye reads as distinct"
        )


def test_pace_markers_carry_data_pace_attribute():
    """The data-pace attribute is what CSS hooks onto for the visual
    encoding. Without it the markers render but every triangle looks
    identical."""
    src = _js()
    assert "data-pace" in src, (
        "pace markers must set the data-pace attribute so CSS can "
        "vary opacity / colour per band"
    )


def test_pace_markers_use_real_event_utc_for_interval():
    src = _js()
    assert "Date.parse(events[i - 1].utc" in src, (
        "pace markers must compute dt = tCurr - tPrev from event.utc "
        "to reflect the REAL elapsed interval"
    )


def test_pace_css_present_with_band_variants():
    css = _css()
    assert ".vio-pace" in css, "CSS for .vio-pace must exist"
    for band in ("fast", "smooth", "slow"):
        assert f'.vio-pace[data-pace="{band}"]' in css, (
            f"CSS must encode the '{band}' pace band — the rhythm is "
            "the visual story; without varied styling every marker "
            "looks identical"
        )

"""Motion-discipline guardrail (VIO_DOCTRINE.md § 13).

Carl's directive, 2026-06-05:

    "Continuous motion must point to something that needs attention,
    until it is handled. Once it is solved, handled, completed, the
    motion stops because it no longer demands attention."

This guardrail enforces the operational test that follows from that
directive: every `animation: ... infinite` rule in vio.css MUST be
bound to a selector that names an unresolved demand on operator
attention. Recent activity, live data, fresh uploads, or "the system
is alive" are NOT demands and may NOT pulse continuously — the
organism handles those autonomously (KYC_ORGANISM_DOCTRINE.md →
"Autonomy by default").

The incident this test is named after:
  · 2026-06-05 — `vio-l2-spine-live` pulsed on any event in the last
    60 minutes. Recent activity is not a demand. Removed; this guard
    pins the rule so it cannot return.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT     = Path(__file__).resolve().parents[1]
VIO_CSS  = ROOT / "ui" / "assets" / "styles" / "vio.css"

# Selectors that name unresolved-demand states. An animation gated to
# any of these is permitted to loop infinitely — the loop will end
# automatically the moment the state resolves (the selector stops
# matching and CSS animation halts).
PERMITTED_ATTENTION_STATES = (
    'data-stage-state="waiting_client"',
    'data-stage-state="failed"',
    'data-stage-state="inconsistent"',
    'data-event-status="waiting"',
    'data-event-status="active"',
)

# `animation: <name> <duration> ... infinite` — any selector with
# `infinite` keyword must answer to the doctrine.
_INFINITE_ANIM_RE = re.compile(r"animation:\s*[^;]*infinite[^;]*;", re.IGNORECASE)


@pytest.fixture(scope="module")
def vio_css_text() -> str:
    return VIO_CSS.read_text(encoding="utf-8")


def _find_rule_block_for_offset(css: str, anim_offset: int) -> tuple[str, int]:
    """Walk backwards from `anim_offset` to find the opening `{`, then
    walk further back to capture the selector. Returns (selector, start
    of selector char-offset). Selectors can span multiple lines."""
    # Find the opening `{` that owns this declaration.
    brace_open = css.rfind("{", 0, anim_offset)
    assert brace_open >= 0, "animation must live inside a CSS rule"

    # Walk backwards until we hit either a `}` (end of previous rule)
    # or `*/` (end of a comment) or the file start.
    cursor = brace_open
    while cursor > 0:
        cursor -= 1
        # Skip over comment blocks: when we hit `/`, check for `*/`.
        if css[cursor] == "}":
            cursor += 1
            break
        if cursor >= 1 and css[cursor - 1:cursor + 1] == "*/":
            # Skip the comment.
            comment_start = css.rfind("/*", 0, cursor)
            if comment_start >= 0:
                cursor = comment_start
            else:
                break

    selector = css[cursor:brace_open].strip()
    return selector, cursor


def test_every_infinite_animation_is_gated_to_attention_state(vio_css_text: str) -> None:
    """Walk every `animation: ... infinite` declaration in vio.css and
    confirm its selector contains at least one permitted attention-state
    token. Catches the 2026-06-05 `spine-live` class of bug at build
    time, before the operator's eye ever has to discipline it back."""
    violations: list[str] = []
    for match in _INFINITE_ANIM_RE.finditer(vio_css_text):
        selector, _ = _find_rule_block_for_offset(vio_css_text, match.start())
        gated = any(token in selector for token in PERMITTED_ATTENTION_STATES)
        if not gated:
            # Allowance for explicit doctrinal exemption (must be opted
            # into per-rule with a comment so the reviewer sees it).
            # Lookback up to 200 chars for an exemption tag.
            head = vio_css_text[max(0, match.start() - 240):match.start()]
            if "MOTION_EXEMPT" in head:
                continue
            violations.append(
                f"\n  selector: {selector}\n  rule: {match.group(0).strip()}"
            )
    assert not violations, (
        "VIO_DOCTRINE.md § 13 violation: continuous (infinite) "
        "animations must be gated to an attention-state selector "
        f"({', '.join(PERMITTED_ATTENTION_STATES)}). The following "
        f"rules pulse forever without naming an unresolved demand:\n"
        + "\n".join(violations)
        + "\n\nOptions: (a) remove the animation, (b) gate it to a "
        "permitted attention-state, or (c) add a `/* MOTION_EXEMPT: "
        "<reason> */` comment immediately above the rule documenting "
        "why the exemption is doctrinally justified."
    )


def test_dead_spine_live_class_does_not_return(vio_css_text: str) -> None:
    """Belt-and-braces guard for the specific 2026-06-05 incident:
    `.vio-l2-spine-live` was removed alongside this test. Any future
    return of that class as an ACTUAL selector (not just a comment
    breadcrumb) would put pulsing motion at the spine tip again —
    exactly the violation Carl named the doctrine after.

    We match the selector-with-opening-brace form so explanatory
    comments referencing the dead class don't trip the guard."""
    # `.vio-l2-spine-live {` and `.vio-l2-spine-live[…] {` and
    # `.vio-l2-spine-live,…` (comma-listed) are all real selector uses.
    selector_use_re = re.compile(r"\.vio-l2-spine-live\s*(?:\{|\[|,|:)")
    matches = selector_use_re.findall(vio_css_text)
    assert not matches, (
        "`.vio-l2-spine-live` was removed 2026-06-05 because it pulsed "
        "on any recent activity (not on an unresolved demand). "
        "Re-adding it as a real selector reintroduces the motion-"
        "discipline violation that named VIO_DOCTRINE.md § 13."
    )


def test_motion_doctrine_section_present() -> None:
    """If a contributor edits VIO_DOCTRINE.md and accidentally drops
    § 13 (the motion-discipline section), this guard fails fast — the
    doctrine and the code must travel together."""
    doctrine = (ROOT / "docs" / "VIO_DOCTRINE.md").read_text(encoding="utf-8")
    assert "§ 13 — Motion discipline" in doctrine, (
        "VIO_DOCTRINE.md must contain the § 13 motion-discipline "
        "section that this test enforces. Re-add it; do not delete it."
    )


def test_autonomy_principle_recorded() -> None:
    """The companion principle in KYC_ORGANISM_DOCTRINE.md — anything
    that can be autonomous, must be. Motion-discipline is downstream
    of this: when the organism handles work autonomously, there is
    nothing to demand attention, and the visual quiet is correct."""
    doctrine = (ROOT / "docs" / "KYC_ORGANISM_DOCTRINE.md").read_text(encoding="utf-8")
    assert "Autonomy by default" in doctrine, (
        "KYC_ORGANISM_DOCTRINE.md must keep the 'Autonomy by default' "
        "section — this is the upstream principle that makes motion "
        "discipline coherent. Without it, every loose 'live activity' "
        "signal can rationalise itself into an animation again."
    )

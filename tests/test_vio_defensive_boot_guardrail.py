"""Regression guard: VIO can never silently go dark again.

Backstory (2026-06-04, second incident in the same day):
  Two latent JS parse errors broke VIO twice. The fix was visible
  (parse-clean JS) but the failure-mode was invisible (silent black
  page). Even with the JS parse guard from the morning, a different
  class of failure — a long-hanging API call, a render path that
  never reaches its append, a future deploy that drops one of the
  required script tags — could put VIO back into the void.

  This guard pins the defensive-boot contract in `ui/vio.html` and
  in `ui/assets/js/vio.js` so that:
    - The boot surface is GUARANTEED to paint synchronously.
    - Any uncaught error is GUARANTEED to surface to the screen.
    - If first render does not happen within 10 seconds, a hard
      diagnostic GUARANTEED to replace the boot pulse.
    - The success path GUARANTEED to tear the boot surface down,
      otherwise the watchdog fires (intentionally loud).

  A future refactor that quietly removes any of these hooks is
  exactly the class of regression that produced this morning's
  incident. This guard catches it before merge.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIO_HTML = ROOT / "ui" / "vio.html"
VIO_JS   = ROOT / "ui" / "assets" / "js" / "vio.js"


@pytest.fixture(scope="module")
def vio_html_text() -> str:
    return VIO_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def vio_js_text() -> str:
    return VIO_JS.read_text(encoding="utf-8")


# ── Boot surface presence ───────────────────────────────────────────────────

def test_boot_iife_present_in_vio_html(vio_html_text: str) -> None:
    """The defensive boot must be an inline <script> in vio.html,
    NOT loaded from /ui/assets/js/. Loading from disk would defeat
    the purpose — a parse failure in a sibling JS file could still
    take the boot down if it depended on external assets."""
    assert "(function () {" in vio_html_text, \
        "expected an IIFE in vio.html (the defensive boot must be inline)"
    assert "window.VIO_BOOT" in vio_html_text, \
        "vio.html must define window.VIO_BOOT — the boot contract handle"


def test_boot_paints_synchronously(vio_html_text: str) -> None:
    """The boot surface must paint before any other JS runs."""
    boot_pos = vio_html_text.find("window.VIO_BOOT")
    env_ribbon_pos = vio_html_text.find('src="/ui/assets/js/env-ribbon.js"')
    vio_js_pos = vio_html_text.find('src="/ui/assets/js/vio.js"')
    assert boot_pos != -1
    assert env_ribbon_pos != -1
    assert vio_js_pos != -1
    assert boot_pos < env_ribbon_pos, \
        "defensive boot script must appear BEFORE env-ribbon.js"
    assert boot_pos < vio_js_pos, \
        "defensive boot script must appear BEFORE vio.js"


# ── Error trap ─────────────────────────────────────────────────────────────

def test_uncaught_error_trap_registered(vio_html_text: str) -> None:
    """Global error trap so uncaught exceptions become visible."""
    assert "addEventListener('error'" in vio_html_text \
        or 'addEventListener("error"' in vio_html_text, \
        "vio.html must register a window 'error' handler"


def test_unhandled_promise_rejection_trap_registered(vio_html_text: str) -> None:
    """Same for unhandled async rejections — the class of failure
    that hangs API fetches and never paints anything."""
    assert "unhandledrejection" in vio_html_text, \
        "vio.html must register a window 'unhandledrejection' handler"


# ── Watchdogs ───────────────────────────────────────────────────────────────

def test_soft_watchdog_present(vio_html_text: str) -> None:
    """At ~2s the boot line must update to reassure the operator
    we are still alive even if the API is slow."""
    assert "2000" in vio_html_text, "expected 2-second soft watchdog"
    assert "still initialising" in vio_html_text


def test_hard_watchdog_present(vio_html_text: str) -> None:
    """At ~10s the boot must flip to a hard 'failed to boot'
    diagnostic if VIO_BOOT.ready() has never been called AND no
    errors were captured (i.e. silent no-render — exactly the
    class of bug that triggered the morning's incident)."""
    assert "10000" in vio_html_text, "expected 10-second hard watchdog"
    assert "boot-timeout" in vio_html_text


# ── vio.js wires into the contract ─────────────────────────────────────────

def test_vio_js_signals_ready_on_first_render(vio_js_text: str) -> None:
    """vio.js MUST call VIO_BOOT.ready() after its first successful
    render path. Without this, the watchdog fires every load and
    every operator sees the diagnostic — intentionally loud."""
    assert "VIO_BOOT.ready" in vio_js_text, \
        "vio.js must call window.VIO_BOOT.ready() on first successful render"


def test_vio_js_signals_fault_on_error(vio_js_text: str) -> None:
    """vio.js MUST call VIO_BOOT.fault() in its catch path so the
    operator sees the actual error, not just a generic boot timeout."""
    assert "VIO_BOOT.fault" in vio_js_text, \
        "vio.js must call window.VIO_BOOT.fault(...) on error"


# ── Script-tag order (so a parse failure can be diagnosed) ─────────────────

def test_script_load_order(vio_html_text: str) -> None:
    """Locks the script load order. env-ribbon.js first (so the env
    banner paints even if VIO scripts fail). vio-level2.js before
    vio.js (vio.js depends on its globals — reversing this would
    break the click-into-L2 handlers without surfacing an error)."""
    env_pos = vio_html_text.find('src="/ui/assets/js/env-ribbon.js"')
    l2_pos  = vio_html_text.find('src="/ui/assets/js/vio-level2.js"')
    js_pos  = vio_html_text.find('src="/ui/assets/js/vio.js"')
    assert env_pos < l2_pos < js_pos, (
        "expected script order: env-ribbon.js → vio-level2.js → vio.js. "
        f"Got positions env={env_pos}, l2={l2_pos}, js={js_pos}"
    )

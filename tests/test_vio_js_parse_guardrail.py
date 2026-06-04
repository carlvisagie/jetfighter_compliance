"""Regression guard: every VIO JS bundle must be parseable.

Backstory (2026-06-04, "We need VIO connected" incident):
  vio.html loads vio-level2.js BEFORE vio.js. A pre-existing duplicate
  `const idx` declaration at line ~1601 of vio-level2.js was a
  SyntaxError. The browser crashed PARSE of vio-level2.js (so no code
  in that file ran), and because <script src=...> tags execute
  top-to-bottom, vio.js never ran either. Result: the operator opened
  /ui/vio.html and saw the static <body> (env-ribbon banner only)
  while the entire awareness field never rendered. VIO is the
  operator's only surface — a silent JS parse failure that takes the
  field offline violates VIO's contract ("the operator's eyes").

  The bug had been live across multiple deploys. It was undetectable
  by the existing pytest suites (all Python). It was undetectable by
  the operator (no error overlay; just blackness). The only signal
  was the operator manually opening DevTools Console.

  This test pins every shipping VIO JS bundle to be parseable by
  Node, which uses the same V8 engine that Chromium-based operator
  browsers do. If `node` is not available in the test environment,
  the test SKIPS rather than passing silently — that intent is
  explicit so a CI env that drops node-availability degrades to a
  "test could not run" rather than a false-green.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS_DIR = ROOT / "ui" / "assets" / "js"

# Anything served from /ui/assets/js/ may be loaded by an operator
# page; if it parses-fails, the page silently breaks.
JS_FILES = sorted(JS_DIR.glob("*.js"))


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(),
                    reason="node not available in test env; cannot syntax-check JS")
@pytest.mark.parametrize("js_path", JS_FILES, ids=lambda p: p.name)
def test_vio_js_bundle_parses(js_path: Path) -> None:
    """Every JS file under /ui/assets/js/ must parse without SyntaxError.

    A single parse error in any file loaded by an operator page can
    take the entire surface offline silently (see module docstring)."""
    result = subprocess.run(
        ["node", "--check", str(js_path)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, (
        f"\n{js_path.name} fails Node parse check (browser will crash too).\n"
        f"  stdout: {result.stdout}\n"
        f"  stderr: {result.stderr}\n"
    )


def test_at_least_one_js_file_discovered() -> None:
    """Sanity: if this returns zero files, the glob is broken and
    test_vio_js_bundle_parses would silently parametrise to nothing
    (which pytest treats as PASSED). Pin the discovery."""
    assert len(JS_FILES) >= 3, (
        f"expected to find at least 3 JS files under {JS_DIR}, "
        f"got {len(JS_FILES)}: {[p.name for p in JS_FILES]}"
    )


def test_critical_vio_bundles_present() -> None:
    """VIO L1 ships three bundles; all three are non-negotiable.

    If any of these go missing the operator surface breaks open;
    pin them by name so a refactor that renames them must update
    this test and force a doctrine conversation."""
    names = {p.name for p in JS_FILES}
    required = {"vio.js", "vio-level2.js", "env-ribbon.js"}
    missing = required - names
    assert not missing, f"required VIO JS bundles missing: {sorted(missing)}"

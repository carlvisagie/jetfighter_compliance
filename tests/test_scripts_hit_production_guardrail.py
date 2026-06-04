"""
Guardrail: every paperwork-touching script under scripts/ imports the
production-only helper and rejects --target / --env / --local flags.

Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md

A future agent that adds a `--target=local` to scripts/seed_vio_live.py
"to make development easier" will fail this test. Production is the only
target. If you want to exercise code paths, write a pytest.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Scripts whose names indicate they hit live / prod. These MUST use the
# _prod_only helper and reject --target flags.
GATED_PATTERN = re.compile(r"(?i)(live|prod|production|inventory|seed_vio)")

# Allowlist: helper modules / docs / non-paperwork utilities.
ALLOWLIST = {
    "_prod_only.py",
    "verify-render-production.ps1",
    "verify-production-live.ps1",
}


def _gated_scripts() -> list[Path]:
    out: list[Path] = []
    if not SCRIPTS_DIR.exists():
        return out
    for p in SCRIPTS_DIR.iterdir():
        if not p.is_file():
            continue
        if p.suffix != ".py":
            continue
        if p.name in ALLOWLIST:
            continue
        if GATED_PATTERN.search(p.name):
            out.append(p)
    return out


def test_prod_only_helper_exists():
    helper = SCRIPTS_DIR / "_prod_only.py"
    assert helper.exists(), (
        "scripts/_prod_only.py is missing — restore it. "
        "Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md"
    )
    src = helper.read_text(encoding="utf-8")
    for symbol in ("reject_target_flag", "production_client", "PRODUCTION_BASE_URL"):
        assert symbol in src, f"_prod_only.py missing required symbol {symbol!r}"


@pytest.mark.parametrize("script_path", _gated_scripts(), ids=lambda p: p.name)
def test_gated_script_imports_prod_only_helper(script_path: Path):
    src = script_path.read_text(encoding="utf-8")
    assert "from _prod_only import" in src or "from scripts._prod_only import" in src, (
        f"{script_path.name}: must import scripts/_prod_only and call "
        "reject_target_flag() at startup. See docs/PRODUCTION_IS_THE_ONLY_TRUTH.md"
    )
    assert "reject_target_flag(" in src, (
        f"{script_path.name}: must call reject_target_flag() at startup so a "
        "--target / --env / --local invocation fails loudly."
    )


@pytest.mark.parametrize("script_path", _gated_scripts(), ids=lambda p: p.name)
def test_gated_script_rejects_target_flag(script_path: Path):
    """Actually invoke the script with --target=local and assert exit code 2."""
    proc = subprocess.run(
        [sys.executable, str(script_path), "--target=local"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 2, (
        f"{script_path.name}: --target=local should exit 2, got {proc.returncode}. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert b"REFUSED" in proc.stderr, (
        f"{script_path.name}: refusal must mention REFUSED so operators see why. "
        f"stderr={proc.stderr!r}"
    )


def test_reject_target_flag_blocks_known_offending_args():
    """Unit-test the helper directly — fast, no subprocess."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import _prod_only as po  # type: ignore
    finally:
        # leave scripts/ on path; harmless within test session
        pass

    for argv in (
        ["--target=local"],
        ["--target", "local"],
        ["--env=test"],
        ["--environment=staging"],
        ["--local"],
        ["--use-local"],
    ):
        with pytest.raises(SystemExit) as ei:
            po.reject_target_flag(argv)
        assert ei.value.code == 2, f"argv={argv!r} should exit 2, got {ei.value.code}"


def test_reject_target_flag_allows_benign_args():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import _prod_only as po  # type: ignore

    for argv in (
        [],
        ["--check"],
        ["--clean"],
        ["--why", "investigating sev-1"],
        ["--limit=5"],
    ):
        po.reject_target_flag(argv)  # must NOT raise

"""Guardrail: VIO connection state must not false-positive Configure API on same-origin."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIO_FRONTEND = ROOT / "vio-frontend"


def _vitest_installed() -> bool:
    bindir = VIO_FRONTEND / "node_modules" / ".bin"
    if sys.platform == "win32":
        return (bindir / "vitest.cmd").is_file()
    return (bindir / "vitest").is_file()


def _npm(args: list[str]) -> list[str]:
    return [shutil.which("npm") or "npm", *args]


def _run_npm(args: list[str]) -> subprocess.CompletedProcess[str]:
    # shell=True with a list runs only argv[0] on Unix — breaks `npm test` in CI.
    return subprocess.run(
        _npm(args),
        cwd=VIO_FRONTEND,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


def _ensure_vio_frontend_deps() -> None:
    """CI and fresh clones do not commit node_modules — install before vitest."""
    if _vitest_installed():
        return
    install = _run_npm(["ci"])
    assert install.returncode == 0, (
        "vio-frontend npm ci failed:\n"
        f"stdout:\n{install.stdout}\nstderr:\n{install.stderr}"
    )


def test_vio_connection_state_unit_tests_pass():
    """apiBase === '' with successful overview must not render Configure API."""
    _ensure_vio_frontend_deps()
    result = _run_npm(["test"])
    assert result.returncode == 0, (
        "vio-frontend connection-state tests failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

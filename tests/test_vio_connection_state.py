"""Guardrail: VIO connection state must not false-positive Configure API on same-origin."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIO_FRONTEND = ROOT / "vio-frontend"


def test_vio_connection_state_unit_tests_pass():
    """apiBase === '' with successful overview must not render Configure API."""
    result = subprocess.run(
        ["npm", "test"],
        cwd=VIO_FRONTEND,
        capture_output=True,
        text=True,
        check=False,
        shell=True,
    )
    assert result.returncode == 0, (
        "vio-frontend connection-state tests failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

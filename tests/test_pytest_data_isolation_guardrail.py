"""
Guardrail: pytest is hard-isolated from the canonical data/ directory.

Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md

These tests verify that the session bootstrap in conftest.py:
  1. Sets KYC_DATA to a per-session temp dir.
  2. Patches services.config.DATA / PROJECTS to point there.
  3. Snapshots the canonical data/ tree at session start.
  4. Has installed a pytest_sessionfinish hook that asserts no canonical
     file was added, removed, or mutated during the run.

If any of these fail, a future agent has tampered with the isolation —
the next pytest run could pollute the real data/ directory and quote the
result as truth (this is exactly the 2026-06-04 incident).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from tests import conftest as _conftest


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DATA = (REPO_ROOT / "data").resolve()


def test_kyc_data_env_var_points_at_session_tmp_dir():
    assert "KYC_DATA" in os.environ, "conftest must set KYC_DATA before any test runs"
    val = Path(os.environ["KYC_DATA"]).resolve()
    assert val != CANONICAL_DATA, (
        f"KYC_DATA={val} is the canonical data/ directory. Pytest pollution "
        "would write to real disk."
    )
    assert val.exists(), f"KYC_DATA={val} does not exist"


def test_services_config_data_is_patched_off_canonical():
    from services import config as svc_config

    assert Path(svc_config.DATA).resolve() != CANONICAL_DATA, (
        f"services.config.DATA={svc_config.DATA} points at canonical data/. "
        "Tests will write to real disk."
    )
    assert Path(svc_config.PROJECTS).resolve() != (CANONICAL_DATA / "projects").resolve(), (
        "services.config.PROJECTS points at canonical data/projects/."
    )


def test_session_snapshot_was_taken_before_tests_started():
    assert hasattr(_conftest, "_CANONICAL_SNAPSHOT_BEFORE"), (
        "conftest._CANONICAL_SNAPSHOT_BEFORE is missing — the session-start "
        "tripwire was deleted. Restore it."
    )
    snap = _conftest._CANONICAL_SNAPSHOT_BEFORE
    assert isinstance(snap, dict), snap
    assert set(snap.keys()) >= {"intakes", "projects", "founding_beta", "ledger"}, (
        "tripwire snapshot missing one or more guarded subdirs"
    )


def test_sessionfinish_hook_is_installed():
    assert hasattr(_conftest, "pytest_sessionfinish"), (
        "conftest.pytest_sessionfinish hook missing — the canonical-data "
        "tripwire assertion will never run. Restore it."
    )


def test_writing_through_services_config_does_not_touch_canonical(tmp_path):
    """A sanity check — write via the live services.config.DATA pointer and
    confirm the file landed in the session tmp dir, not in canonical data/."""
    from services import config as svc_config

    sentinel = Path(svc_config.DATA) / "_isolation_sentinel.txt"
    sentinel.write_text("hello from pytest", encoding="utf-8")
    assert sentinel.exists()
    assert (
        Path(sentinel).resolve() != (CANONICAL_DATA / "_isolation_sentinel.txt").resolve()
    )
    canonical_sentinel = CANONICAL_DATA / "_isolation_sentinel.txt"
    assert not canonical_sentinel.exists(), (
        f"Write via services.config.DATA landed in canonical data/ at "
        f"{canonical_sentinel} — isolation is broken."
    )
    sentinel.unlink(missing_ok=True)

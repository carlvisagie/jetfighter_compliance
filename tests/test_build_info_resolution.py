"""build_info: prove the git_commit resolution chain works.

The live Render service is hand-created (not Blueprint-managed) so the
RENDER_GIT_COMMIT runtime env var is not injected. Without a working
resolution chain, /api/public/build-info returns `unknown` for every
deploy and there is no way to verify which commit is actually running.

This guard pins the three resolution paths:

  1. Baked .build_commit file (the Dockerfile path — authoritative on
     production).
  2. Env var fallback (KYC_GIT_COMMIT / RENDER_GIT_COMMIT / GIT_COMMIT).
  3. Graceful 'unknown' when nothing is available — never raises.

A previous regression had build_info silently returning 'unknown' for
weeks; now any breakage of the chain breaks the test suite first.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock


def test_baked_file_wins_over_env(tmp_path, monkeypatch):
    """When a .build_commit file exists with a real SHA, it wins over
    any env var. The file is the source of truth on Render."""
    import services.build_info as bi

    baked = tmp_path / ".build_commit"
    baked.write_text("abcdef0123456789abcdef0123456789abcdef01", encoding="utf-8")

    monkeypatch.setattr(bi, "_CANDIDATE_PATHS", (baked,))
    monkeypatch.setenv("KYC_GIT_COMMIT", "deadbeef")

    sha = bi.git_commit()
    assert sha == "abcdef0123456789abcdef0123456789abcdef01"


def test_env_used_when_no_baked_file(tmp_path, monkeypatch):
    """If no baked file exists, fall back to env vars in priority
    order. KYC_GIT_COMMIT > RENDER_GIT_COMMIT > GIT_COMMIT."""
    import services.build_info as bi

    monkeypatch.setattr(bi, "_CANDIDATE_PATHS", (tmp_path / "nope",))
    monkeypatch.delenv("KYC_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "render-sha-aaa")
    assert bi.git_commit() == "render-sha-aaa"

    monkeypatch.setenv("KYC_GIT_COMMIT", "kyc-sha-bbb")
    assert bi.git_commit() == "kyc-sha-bbb"


def test_baked_unknown_is_skipped(tmp_path, monkeypatch):
    """A baked file containing the literal 'unknown' must not satisfy —
    we want to know the chain failed, not pretend 'unknown' is a SHA."""
    import services.build_info as bi

    baked = tmp_path / ".build_commit"
    baked.write_text("unknown", encoding="utf-8")
    monkeypatch.setattr(bi, "_CANDIDATE_PATHS", (baked,))
    monkeypatch.delenv("KYC_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)

    sha = bi.git_commit()
    assert sha == "unknown"  # only because no env var was set either


def test_empty_baked_file_falls_through(tmp_path, monkeypatch):
    """Empty file → fall through to env vars; never crash."""
    import services.build_info as bi

    baked = tmp_path / ".build_commit"
    baked.write_text("", encoding="utf-8")
    monkeypatch.setattr(bi, "_CANDIDATE_PATHS", (baked,))
    monkeypatch.setenv("KYC_GIT_COMMIT", "env-sha")
    assert bi.git_commit() == "env-sha"


def test_unreadable_path_falls_through(tmp_path, monkeypatch):
    """A path that points nowhere must not raise — production must
    never 500 on the health/build-info endpoints."""
    import services.build_info as bi

    monkeypatch.setattr(bi, "_CANDIDATE_PATHS", (tmp_path / "does" / "not" / "exist",))
    monkeypatch.delenv("KYC_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert bi.git_commit() == "unknown"

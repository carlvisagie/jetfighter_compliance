"""Doctrine guardrail: VIO Level 1 backend honours docs/VIO_DOCTRINE.md.

These tests are the executable form of the doctrine — they pin the
backbone, the stage-state lexicon, the urgency formula, the company-name
sanitiser, and the stage-age semantics so a well-meaning refactor cannot
silently drift the operator's command surface.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import vio_overview as V


# ─────────────────────────────────────────────────────────────────────
# § 2 — Backbone constants
# ─────────────────────────────────────────────────────────────────────
def test_backbone_is_seven_canonical_stages_in_order() -> None:
    assert V.STAGE_BACKBONE == [
        "intake",
        "classification",
        "validation",
        "evidence_mapping",
        "review",
        "approval",
        "conversion",
    ]


def test_only_branch_is_client_followup() -> None:
    assert V.STAGE_BRANCH_CLIENT_FOLLOWUP == "client_followup"


# ─────────────────────────────────────────────────────────────────────
# § 3 — Stage-state lexicon
# ─────────────────────────────────────────────────────────────────────
def test_stage_state_lexicon_is_exactly_the_six_doctrinal_tokens() -> None:
    tokens = {
        V.STAGE_STATE_HEALTHY,
        V.STAGE_STATE_STALLED,
        V.STAGE_STATE_FAILED,
        V.STAGE_STATE_WAITING_CLIENT,
        V.STAGE_STATE_INCONSISTENT,
        V.STAGE_STATE_DONE,
    }
    assert tokens == {
        "healthy",
        "stalled",
        "failed",
        "waiting_client",
        "inconsistent",
        "done",
    }


# ─────────────────────────────────────────────────────────────────────
# § 4 — Urgency formula
# ─────────────────────────────────────────────────────────────────────
def _row(**overrides):
    base = {
        "intake_id": "T1",
        "created_utc": _iso_minus_hours(1),
        "last_movement_utc": _iso_minus_hours(1),
        "review_status": "pending_review",
        "file_count": 0,
    }
    base.update(overrides)
    return base


def _iso_minus_hours(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat().replace(
        "+00:00", "Z"
    )


def test_failure_outranks_normal_staleness_and_gaps() -> None:
    """A single failure must outrank any week-old stalled intake or any
    moderate gap count. The 1000× weight in the doctrine formula is the
    intentional separator — staleness only catches up at ~20 days, which
    is the doctrine's deliberate crossover point (a thing broken for that
    long deserves operator attention equal to a fresh failure)."""
    stage_failed = {
        "stage_state": V.STAGE_STATE_FAILED,
        "stage_index": 3,
        "on_branch": False,
    }
    stage_healthy = {
        "stage_state": V.STAGE_STATE_HEALTHY,
        "stage_index": 3,
        "on_branch": False,
    }
    score_failed = V._compute_urgency(
        _row(), {"extraction_failures": 1}, stage_failed
    )
    # Same row but 7 days stale with 5 gaps — these should not outrank a failure.
    score_clean = V._compute_urgency(
        _row(last_movement_utc=_iso_minus_hours(24 * 7)),
        {"missing_item_count": 5},
        stage_healthy,
    )
    assert score_failed > score_clean, (
        f"A single extraction failure ({score_failed}) must outscore a "
        f"7-day stale intake with 5 gaps ({score_clean}). Doctrine §4."
    )


def test_done_companies_sink_to_minus_one() -> None:
    stage = {"stage_state": V.STAGE_STATE_DONE, "stage_index": 6, "on_branch": False}
    assert V._compute_urgency(_row(), {}, stage) == -1


# ─────────────────────────────────────────────────────────────────────
# Stage-age (NOT intake-age) — this is what previously regressed
# ─────────────────────────────────────────────────────────────────────
def test_days_in_stage_uses_last_movement_not_intake_age() -> None:
    """A 30-day-old intake that just moved 1 hour ago must NOT score as 30 days."""
    fresh_after_old_intake = _row(
        created_utc=_iso_minus_hours(24 * 30),       # intake created 30 days ago
        last_movement_utc=_iso_minus_hours(1),       # but just moved 1 hour ago
    )
    age = V._stage_age_hours(fresh_after_old_intake)
    assert 0.5 <= age <= 2.0, (
        f"Stage age should reflect last_movement (~1h) not intake age "
        f"(720h). Got {age:.2f}h. Doctrine §4."
    )


def test_days_in_stage_falls_back_to_intake_age_when_no_movement() -> None:
    """Without a movement timestamp the urgency calc may still use intake age."""
    no_movement = _row(
        created_utc=_iso_minus_hours(48),
        last_movement_utc="",
    )
    age = V._stage_age_hours(no_movement)
    assert 47.0 <= age <= 49.0


def test_stalled_classification_uses_stage_age() -> None:
    """A 30-day-old intake that moved an hour ago must render HEALTHY, not STALLED."""
    row = _row(
        created_utc=_iso_minus_hours(24 * 30),
        last_movement_utc=_iso_minus_hours(1),
        file_count=2,
        review_status="pending_review",
        primary_category="cmmc",
    )
    ei = {"files_uploaded": 2, "files_analyzed": 0, "extraction_failures": 0}
    info = V._classify_stage(row, ei, state="new")
    assert info["stage_state"] == V.STAGE_STATE_HEALTHY, (
        f"30-day-old intake that just moved must render healthy. "
        f"Got {info['stage_state']!r}. Doctrine §3."
    )


def test_truly_stalled_intake_classified_as_stalled() -> None:
    """No movement in 7 days at the same review status -> stalled."""
    row = _row(
        created_utc=_iso_minus_hours(24 * 7),
        last_movement_utc=_iso_minus_hours(24 * 7),
        file_count=2,
        review_status="pending_review",
        primary_category="cmmc",
    )
    ei = {"files_uploaded": 2, "files_analyzed": 0, "extraction_failures": 0}
    info = V._classify_stage(row, ei, state="new")
    assert info["stage_state"] == V.STAGE_STATE_STALLED


# ─────────────────────────────────────────────────────────────────────
# § 7 — Defensive hygiene (company-name sanitiser)
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Acme Corp", "Acme Corp"),
        ("", "Unknown"),
        ("   ", "Unknown"),
        (None, "Unknown"),
    ],
)
def test_company_name_sanitiser_basics(raw, expected) -> None:
    assert V._clean_company_name(raw) == expected


def test_company_name_sanitiser_collapses_urls() -> None:
    cleaned = V._clean_company_name("http://www.example.com/path?q=1")
    # The doctrine says URLs collapse to the apex domain; the exact form
    # may vary by sanitiser revision but it must NOT display as a URL.
    assert "://" not in cleaned and "/" not in cleaned
    assert "example" in cleaned.lower()


def test_company_name_sanitiser_truncates_long_strings() -> None:
    long_name = "X" * 300
    cleaned = V._clean_company_name(long_name)
    assert len(cleaned) <= 120 + len("...")  # ellipsis budget

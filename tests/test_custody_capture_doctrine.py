"""Doctrine: provable chain of custody — every operator and pipeline
event from first click to delivered product is captured in the
transaction lifecycle ledger and surfaces via `build_custody_timeline`.

These tests guard against silent regressions where someone removes the
`append_transaction_event` write that anchors:

  * evidence-intelligence completion / failure (auto-pipeline)
  * operator review-status transitions
  * payment-link generation/send
  * binder export (the delivery moment)

If any of these stops being written, the L2 "chain of custody" frame
goes blank for those phases and the operator can no longer prove what
happened years later. That is a doctrine violation — the test fails.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest


# ─── helpers ────────────────────────────────────────────────────────────


def _load_transactions(intake_id: str) -> List[Dict[str, Any]]:
    from services.intake.transactions import load_transaction_log

    return load_transaction_log(intake_id, tail=500)


def _phases(rows: List[Dict[str, Any]]) -> List[str]:
    return [str(r.get("phase") or "") for r in rows]


# ─── tests ──────────────────────────────────────────────────────────────


def test_custody_timeline_surfaces_new_phases_in_lexicon(fb_env):
    """The custody-timeline phase lexicon knows about every phase the
    pipeline writes. If a new phase is added without a label, the L2
    custody row falls back to the raw phase string — readable but ugly.
    This test pins the lexicon to the doctrine."""
    from services.intake.custody_timeline import _PHASE_TO_EVENT

    required = {
        "evidence_intelligence_completed",
        "evidence_intelligence_failed",
        # Operator-triggered EI replay (FB-1dfab13c120b recovery, 2026-06-04).
        # Must surface in the L2 chain-of-custody tile as a first-class event
        # — operator-initiated reprocess is part of provable custody, not a
        # back-channel admin action. See VIO_DOCTRINE §12.
        "evidence_intelligence_reprocessed",
        "operator_action_approve_review",
        "operator_action_request_more_info",
        "operator_action_mark_high_value",
        "operator_action_archive",
        "operator_payment_link_sent",
        "binder_exported",
    }
    missing = required - set(_PHASE_TO_EVENT.keys())
    assert not missing, f"custody_timeline lexicon missing phases: {sorted(missing)}"


def test_operator_review_status_transition_writes_custody_event(fb_env):
    """When operator flips review_status (approve / archive / request
    info / high value), a `operator_action_*` event lands in the
    transaction log so the per-transition timestamp is preserved."""
    from services.intake.intake import _save_intake
    from services.intake.operator_actions import apply_operator_action

    intake_id = "FB-CUSTODYOP01"
    _save_intake(intake_id, {
        "intake_id":    intake_id,
        "email":        "op@test.local",
        "review_status": "pending_review",
        "status":        "pending_review",
    })

    apply_operator_action(intake_id, "approve_review", operator_note="ok")
    phases = _phases(_load_transactions(intake_id))
    assert "operator_action_approve_review" in phases, (
        "approve_review must write a custody event; got phases=%r" % (phases,)
    )

    apply_operator_action(intake_id, "archive", operator_note="done")
    phases = _phases(_load_transactions(intake_id))
    assert "operator_action_archive" in phases, (
        "archive must write a custody event; got phases=%r" % (phases,)
    )


def test_binder_export_writes_custody_event(fb_env, tmp_path: Path, monkeypatch):
    """Binder export is the delivery moment — must always land in the
    custody ledger with the merkle root."""
    import services.reports as reports
    from services.intake.transactions import load_transaction_log

    project_id = "FB-BINDEREXPORT1"
    pdir = reports._project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "meta.json").write_text('{"x":1}', encoding="utf-8")

    zpath = reports.export_binder(project_id)
    assert zpath.exists(), "binder zip must be produced"

    rows = load_transaction_log(project_id, tail=500)
    phases = [str(r.get("phase") or "") for r in rows]
    assert "binder_exported" in phases, (
        "binder export must write custody event; got phases=%r" % (phases,)
    )
    last = [r for r in rows if r.get("phase") == "binder_exported"][-1]
    meta = last.get("metadata") or {}
    assert meta.get("merkle_root_sha256"), "binder custody must carry merkle root"
    assert meta.get("binder_zip"),         "binder custody must carry zip filename"


def test_vio_company_detail_exposes_custody_block(fb_env):
    """L2 needs a `custody` block on company detail or the chain-of-
    custody tile/frame have nothing to render."""
    from services.intake.intake import _save_intake
    from services.intake.transactions import append_transaction_event
    from services.vio_company_detail import build_company_detail

    intake_id = "FB-VIOCUSTODY01"
    _save_intake(intake_id, {
        "intake_id":     intake_id,
        "email":         "c@test.local",
        "company_name":  "Custody Co.",
        "review_status": "pending_review",
        "status":        "pending_review",
    })
    append_transaction_event(intake_id, "upload_received",
                             metadata={"file_count": 1})

    detail = build_company_detail(intake_id)
    assert "custody" in detail, "detail must include `custody` block"
    ct = detail["custody"]
    assert ct["ok"] is True
    assert ct["event_count"] >= 1
    assert any(e.get("event") == "upload_received" for e in ct["events"])

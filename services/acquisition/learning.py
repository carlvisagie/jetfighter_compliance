"""Acquisition learning loop — winners, failures, experiments from real telemetry."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .intelligence_paths import (
    EXPERIMENTS_JSONL,
    FAILURES_JSONL,
    WINNERS_JSONL,
    ensure_intel_dirs,
)
from .memory import get_learned_weights, recompute_weights_from_outcomes, record_outcome
from .models import utc_now
from . import telemetry as acq_telemetry


def _append(filename: str, record: Dict[str, Any], base: Optional[Path] = None) -> Dict[str, Any]:
    root = ensure_intel_dirs(base)
    path = root / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _load(filename: str, base: Optional[Path] = None, limit: int = 500) -> List[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    path = root / filename
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def record_winner(
    *,
    reason: str,
    lead_id: str = "",
    target_id: str = "",
    campaign_id: str = "",
    variant: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "winner_id": f"WIN-{uuid.uuid4().hex[:8]}",
        "when_utc": utc_now(),
        "reason": reason,
        "lead_id": lead_id,
        "target_id": target_id,
        "campaign_id": campaign_id,
        "variant": variant,
        "metadata": metadata or {},
    }
    _append(WINNERS_JSONL, rec, base)
    acq_telemetry.emit("acquisition_winner", lead_id=lead_id, target_id=target_id, metadata=rec, base=base)
    _memory_learning("acquisition_winner", rec, base)
    return rec


def record_failure(
    *,
    reason: str,
    lead_id: str = "",
    campaign_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "failure_id": f"FAIL-{uuid.uuid4().hex[:8]}",
        "when_utc": utc_now(),
        "reason": reason,
        "lead_id": lead_id,
        "campaign_id": campaign_id,
        "metadata": metadata or {},
    }
    _append(FAILURES_JSONL, rec, base)
    acq_telemetry.emit(
        "acquisition_failure",
        lead_id=lead_id,
        severity="info",
        success=False,
        metadata=rec,
        base=base,
    )
    _memory_learning("acquisition_failure", rec, base)
    return rec


def record_experiment(
    *,
    name: str,
    hypothesis: str,
    variants: List[str],
    metric: str = "upload_completed",
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "experiment_id": f"EXP-{uuid.uuid4().hex[:8]}",
        "when_utc": utc_now(),
        "name": name,
        "hypothesis": hypothesis,
        "variants": variants,
        "metric": metric,
        "status": "active",
        "doctrine": "upload_first_intact",
    }
    _append(EXPERIMENTS_JSONL, rec, base)
    acq_telemetry.emit("acquisition_learning", metadata=rec, base=base)
    return rec


def record_conversion(
    *,
    stage: str,
    success: bool,
    lead_id: str = "",
    project_id: str = "",
    org_key: str = "",
    campaign_id: str = "",
    variant: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> None:
    """Bridge funnel events to outcomes + learning."""
    meta = dict(metadata or {})
    if campaign_id:
        meta["campaign_id"] = campaign_id
    if variant:
        meta["variant"] = variant
    record_outcome(
        lead_id=lead_id,
        project_id=project_id,
        org_key=org_key,
        stage=stage,
        success=success,
        metadata=meta,
        base=base,
    )
    event = "acquisition_conversion" if success else "acquisition_failure"
    acq_telemetry.emit(
        event,
        lead_id=lead_id,
        project_id=project_id,
        metadata={"stage": stage, **meta},
        base=base,
        success=success,
    )
    if success and stage in ("upload_completed", "workspace_created", "intake_completed"):
        record_winner(
            reason=f"conversion:{stage}",
            lead_id=lead_id,
            campaign_id=campaign_id,
            variant=variant,
            metadata=meta,
            base=base,
        )
    elif not success and stage.endswith("abandoned"):
        record_failure(reason=stage, lead_id=lead_id, campaign_id=campaign_id, metadata=meta, base=base)


def load_winners(base: Optional[Path] = None, limit: int = 50) -> List[Dict[str, Any]]:
    return _load(WINNERS_JSONL, base, limit)


def load_failures(base: Optional[Path] = None, limit: int = 50) -> List[Dict[str, Any]]:
    return _load(FAILURES_JSONL, base, limit)


def load_experiments(base: Optional[Path] = None, limit: int = 20) -> List[Dict[str, Any]]:
    return _load(EXPERIMENTS_JSONL, base, limit)


def run_learning_cycle(base: Optional[Path] = None) -> Dict[str, Any]:
    """Recompute weights from outcomes; summarize winners/failures."""
    weights = recompute_weights_from_outcomes(base)
    winners = _load(WINNERS_JSONL, base, limit=50)
    failures = _load(FAILURES_JSONL, base, limit=50)
    experiments = _load(EXPERIMENTS_JSONL, base, limit=20)
    acq_telemetry.emit(
        "acquisition_learning",
        metadata={"winners": len(winners), "failures": len(failures)},
        base=base,
    )
    _memory_learning(
        "acquisition_learning",
        {"weights_keys": list(weights.keys())[:10], "winner_count": len(winners)},
        base,
    )
    return {
        "ok": True,
        "weights": weights,
        "winner_count": len(winners),
        "failure_count": len(failures),
        "active_experiments": [e for e in experiments if e.get("status") == "active"],
        "learned_weights": get_learned_weights(base),
    }


def _memory_learning(event_type: str, payload: Dict[str, Any], base: Optional[Path] = None) -> None:
    try:
        from services.memory.central_memory import safe_link_acquisition_organism_event

        safe_link_acquisition_organism_event(event_type, payload, base=base)
    except Exception:
        pass

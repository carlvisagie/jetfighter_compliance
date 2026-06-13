"""Acquisition outcome memory and adaptive weight learning."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .intelligence_paths import OUTCOMES_JSONL, WEIGHTS_JSON, ensure_intel_dirs
from .models import utc_now

DEFAULT_WEIGHTS = {
    "segment_aerospace": 3.0,
    "segment_manufacturing": 2.5,
    "segment_government-subcontractor": 3.5,
    "urgency_keyword": 4.0,
    "business_email": 2.0,
    "intake_completed": 8.0,
    "inquiry_only": -2.0,
    "abandoned_intake": -5.0,
    "high_documentation_score": 5.0,
    "conversion_success": 10.0,
}


def _append_outcome(record: Dict[str, Any], base: Optional[Path] = None) -> None:
    root = ensure_intel_dirs(base)
    path = root / OUTCOMES_JSONL
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_outcomes(base: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = ensure_intel_dirs(base)
    path = root / OUTCOMES_JSONL
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def get_learned_weights(base: Optional[Path] = None) -> Dict[str, float]:
    """Load acquisition weights from central memory (ONE TRUE SOURCE).
    
    Fallback to weights.json for backwards compatibility only.
    """
    weights = dict(DEFAULT_WEIGHTS)
    
    # ONE BRAIN: Read from central memory FIRST
    try:
        from services.memory.learning import load_learning_state
        
        state = load_learning_state(base)
        acquired = state.get("acquisition_weights", {}).get("values", {})
        if acquired:
            weights.update({k: float(v) for k, v in acquired.items()})
            return weights
    except Exception:
        pass
    
    # Fallback to weights.json (backwards compatibility during migration)
    root = ensure_intel_dirs(base)
    path = root / WEIGHTS_JSON
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            weights.update({k: float(v) for k, v in stored.items()})
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    return weights


def save_learned_weights(weights: Dict[str, float], base: Optional[Path] = None) -> None:
    """Save acquisition weights to central memory (ONE TRUE SOURCE).
    
    Writes to central learning_state FIRST, then mirrors to weights.json
    for backwards compatibility. Central memory is the canonical brain.
    """
    # ONE BRAIN: Write to central memory FIRST
    try:
        from services.memory.learning import load_learning_state, save_learning_state
        from services.memory.entity_graph import utc_now

        state = load_learning_state(base)
        state["acquisition_weights"] = {
            "values":      {k: float(v) for k, v in weights.items()},
            "source":      "services.acquisition.memory.save_learned_weights",
            "updated_utc": utc_now(),
        }
        save_learning_state(state, base)
    except Exception:
        # CRITICAL: If central write fails, acquisition learning is lost
        from services.memory.telemetry import emit_telemetry
        emit_telemetry(
            "acquisition",
            "weights_write_failed",
            severity="critical",
            metadata={"error": "Central memory write failed"}
        )
        raise
    
    # Mirror to weights.json for backwards compatibility during migration
    try:
        root = ensure_intel_dirs(base)
        (root / WEIGHTS_JSON).write_text(json.dumps(weights, indent=2), encoding="utf-8")
    except Exception:
        # Best-effort mirror; central memory already has the truth
        pass


def record_outcome(
    *,
    lead_id: str = "",
    project_id: str = "",
    org_key: str = "",
    stage: str,
    success: bool,
    metadata: Optional[Dict[str, Any]] = None,
    base: Optional[Path] = None,
) -> Dict[str, Any]:
    rec = {
        "lead_id": lead_id,
        "project_id": project_id,
        "org_key": org_key,
        "stage": stage,
        "success": success,
        "when_utc": utc_now(),
        "metadata": metadata or {},
    }
    _append_outcome(rec, base)
    try:
        from services.memory.organism_integration import safe_write_after_acquisition_outcome

        safe_write_after_acquisition_outcome(
            lead_id=lead_id,
            project_id=project_id,
            org_key=org_key,
            stage=stage,
            success=success,
            metadata=metadata,
            base=base,
        )
    except Exception:
        pass
    return rec


def recompute_weights_from_outcomes(base: Optional[Path] = None) -> Dict[str, float]:
    """Adjust weights from accumulated outcomes (simple learning loop)."""
    outcomes = _load_outcomes(base)
    weights = get_learned_weights(base)
    if not outcomes:
        return weights

    conversions = [o for o in outcomes if o.get("stage") == "intake_completed" and o.get("success")]
    abandonments = [o for o in outcomes if o.get("stage") == "abandoned" or (not o.get("success") and "intake" in o.get("stage", ""))]
    inquiries = [o for o in outcomes if o.get("stage") == "inquiry_submitted"]

    if conversions:
        weights["conversion_success"] = min(15.0, weights["conversion_success"] + 0.5 * len(conversions))
        weights["intake_completed"] = min(12.0, weights["intake_completed"] + 0.3)
    if abandonments:
        weights["abandoned_intake"] = max(-10.0, weights["abandoned_intake"] - 0.2 * len(abandonments))
    if len(inquiries) > len(conversions) * 3 and inquiries:
        weights["inquiry_only"] = max(-6.0, weights["inquiry_only"] - 0.1)

    for o in outcomes:
        meta = o.get("metadata") or {}
        if meta.get("segment") == "aerospace" and o.get("success"):
            weights["segment_aerospace"] = min(6.0, weights["segment_aerospace"] + 0.1)
        if meta.get("urgency_indicators"):
            weights["urgency_keyword"] = min(8.0, weights["urgency_keyword"] + 0.05 * len(meta["urgency_indicators"]))

    save_learned_weights(weights, base)
    return weights


def correlate_lead_to_project(lead_id: str, project_id: str, base: Optional[Path] = None) -> None:
    if not lead_id or not project_id:
        return
    record_outcome(
        lead_id=lead_id,
        project_id=project_id,
        stage="correlated",
        success=True,
        metadata={"action": "lead_project_link"},
        base=base,
    )

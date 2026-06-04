"""Atomic JSON snapshot writer.

Used by every organism to persist its self-awareness snapshot to disk.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def write_snapshot(state: Dict[str, Any], *, path: Path) -> Optional[Path]:
    """Atomically write a JSON snapshot. Returns the path on success, else None.

    Never raises — failures are logged so a flaky disk does not block the
    organism from reporting its state via the HTTP endpoint.
    """
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(target)
        return target
    except OSError as exc:
        logger.warning("organism_core: snapshot write failed for %s: %s", path, exc)
        return None


# ── Append-only snapshot history ──────────────────────────────────
#
# 2026-06-04 forensic audit (Organism Awareness): docs reference
# `/api/operator/organism/history`, but only a single point-in-time
# snapshot was ever written. Operators could not answer "how did the
# organism look six hours ago?" or "when did this incident start?"
# without parsing telemetry. This writes a sidecar JSONL of the most
# important fields next to every snapshot.

def append_snapshot_history(
    state: Dict[str, Any],
    *,
    path: Path,
    max_lines: int = 5000,
) -> Optional[Path]:
    """Append a compact snapshot row to a JSONL sidecar.

    `path` is the snapshot JSON path; the history JSONL lives next to
    it as `<basename>.history.jsonl`. Never raises. Bounded to
    `max_lines` so we never grow without limit on a small disk.
    """
    try:
        target_json = Path(path)
        history = target_json.with_name(
            target_json.stem + ".history.jsonl"
        )
        history.parent.mkdir(parents=True, exist_ok=True)
        # Compact row — keep this stable; the operator UI reads it.
        row = {
            "captured_utc": state.get("snapshot_at_utc")
                            or state.get("computed_at_utc")
                            or datetime.now(timezone.utc)
                                       .isoformat()
                                       .replace("+00:00", "Z"),
            "health_state": state.get("health_state"),
            "bottleneck":   state.get("bottleneck"),
            "intake_count_total":    state.get("intake_count_total"),
            "intake_count_active":   state.get("intake_count_active"),
            "intake_count_archived": state.get("intake_count_archived"),
            "queue_depth":           state.get("queue_depth"),
            "uploaded_file_count":   state.get("uploaded_file_count"),
            "mismatch_count":        state.get("mismatch_count"),
            "environment":           state.get("environment"),
        }
        with history.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")
        # Trim to bound size; cheap because we only do this when the
        # file grows, but skip read-cost when it's still small.
        try:
            if history.stat().st_size > max_lines * 1024:
                _trim_history(history, max_lines=max_lines)
        except OSError:
            pass
        return history
    except OSError as exc:
        logger.warning(
            "organism_core: history append failed for %s: %s", path, exc
        )
        return None


def _trim_history(path: Path, *, max_lines: int) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= max_lines:
            return
        keep = lines[-max_lines:]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("organism_core: history trim failed for %s: %s",
                       path, exc)


def read_snapshot_history(
    path: Path, *, limit: int = 200
) -> List[Dict[str, Any]]:
    """Read the last `limit` history rows for the snapshot at `path`.

    Returned newest-last for natural time-axis rendering. Never raises.
    """
    target_json = Path(path)
    history = target_json.with_name(target_json.stem + ".history.jsonl")
    if not history.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = history.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("organism_core: history read failed for %s: %s",
                       history, exc)
        return []
    tail = lines[-limit:] if limit and limit > 0 else lines
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except (ValueError, TypeError):
            continue
    return rows

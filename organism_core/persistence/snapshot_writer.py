"""Atomic JSON snapshot writer.

Used by every organism to persist its self-awareness snapshot to disk.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

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

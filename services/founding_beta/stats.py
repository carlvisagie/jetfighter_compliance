"""Founding beta dashboard metrics for operator cockpit."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.config import DATA

from .mode import is_founding_beta_mode
from .messaging import beta_messaging_blocks


def _read_jsonl(path: Path, limit: int = 2000) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def get_founding_beta_status(base: Optional[Path] = None) -> Dict[str, Any]:
    root = DATA if base is None else base
    active = is_founding_beta_mode()
    blocks = beta_messaging_blocks()

    tel_path = root / "memory" / "telemetry.jsonl"
    beta_events = [
        r
        for r in _read_jsonl(tel_path)
        if r.get("subsystem") == "founding_beta" or (r.get("metadata") or {}).get("founding_beta")
    ]
    uploads_started = sum(1 for r in beta_events if r.get("event_type") == "beta_upload_started")
    uploads_completed = sum(1 for r in beta_events if r.get("event_type") == "beta_upload_completed")
    file_type_events = [r for r in beta_events if r.get("event_type") == "upload_file_types"]
    mapping_events = [r for r in beta_events if r.get("event_type") == "evidence_mapping_confidence"]
    confusion_events = [r for r in beta_events if r.get("event_type") == "onboarding_confusion"]

    sessions_dir = root / "customer_sessions"
    session_uploads = 0
    if sessions_dir.is_dir():
        for manifest in sessions_dir.glob("*/manifest.json"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                session_uploads += len(data.get("files") or [])
            except Exception:
                pass

    categories: Dict[str, int] = {}
    for ev in file_type_events[-50:]:
        for ext in (ev.get("metadata") or {}).get("extensions") or []:
            categories[ext] = categories.get(ext, 0) + 1

    avg_confidence = None
    if mapping_events:
        scores = [
            float((e.get("metadata") or {}).get("confidence", 0))
            for e in mapping_events
            if (e.get("metadata") or {}).get("confidence") is not None
        ]
        if scores:
            avg_confidence = round(sum(scores) / len(scores), 2)

    learning_signals: List[str] = []
    if uploads_completed:
        learning_signals.append(f"{uploads_completed} beta upload completion(s) recorded")
    if session_uploads:
        learning_signals.append(f"{session_uploads} file(s) in pre-contact sessions")
    if avg_confidence is not None:
        learning_signals.append(f"Avg evidence mapping confidence ~{avg_confidence}")
    if confusion_events:
        learning_signals.append(f"{len(confusion_events)} onboarding confusion signal(s)")
    if not learning_signals:
        learning_signals.append("Awaiting first founding beta paperwork uploads")

    completion_rate = (
        round(uploads_completed / uploads_started, 3) if uploads_started else None
    )

    return {
        "active": active,
        "label": "Founding Beta Mode Active" if active else "Founding Beta Mode Off",
        "messaging": blocks,
        "metrics": {
            "uploads_received": max(uploads_completed, session_uploads),
            "beta_uploads_started": uploads_started,
            "beta_uploads_completed": uploads_completed,
            "onboarding_completion_rate": completion_rate,
            "evidence_categories_mapped": categories,
            "evidence_mapping_confidence_avg": avg_confidence,
            "organism_learning_signals": learning_signals,
        },
        "success_metric": blocks["success_metric"],
    }

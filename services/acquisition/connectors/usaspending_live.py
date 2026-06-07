"""
Live connector #1: USASpending.gov public API.

Lawful federal open data — no API key, no login, no scraping private systems.
https://api.usaspending.gov/

Does NOT auto-send outreach. Draft messages only.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..finder import discover_usaspending_recipients
from ..models import utc_now
from .. import telemetry

logger = logging.getLogger(__name__)

CONNECTOR_ID = "usaspending_live"
SOURCE_ID = "usaspending_public_api"

# Compliance-relevant federal supply chain search terms
DEFAULT_QUERIES = [
    "defense manufacturing",
    "precision machining",
    "aerospace supplier",
    "government subcontractor",
    "metal fabrication defense",
]

# Inferred burden context for signal detection (public award recipients)
BURDEN_CONTEXT = (
    "federal contractor subcontractor CMMC DFARS compliance documentation "
    "audit evidence security questionnaire overwhelmed where do I start"
)


def run_usaspending_live_connector(
    *,
    queries: Optional[List[str]] = None,
    limit_per_query: int = 12,
    campaign_id: str = "upload-first",
    message_variant: str = "A",
    min_fit_score: int = 50,
    pause_seconds: float = 1.0,
    base=None,
) -> Dict[str, Any]:
    """
    Fetch live recipients from USASpending, score, route to upload-first, write targets.
    """
    from ..orchestration import ingest_discovery_candidate, load_recent_target_keys

    query_list = queries or list(DEFAULT_QUERIES)
    seen = load_recent_target_keys(base)
    stats: Dict[str, Any] = {
        "ok": True,
        "connector": CONNECTOR_ID,
        "queries_run": 0,
        "fetched": 0,
        "targets_created": 0,
        "duplicates_skipped": 0,
        "below_threshold": 0,
        "errors": 0,
        "when_utc": utc_now(),
    }

    telemetry.emit(
        "acquisition_target_detected",
        metadata={"connector": CONNECTOR_ID, "phase": "live_fetch_start", "queries": query_list},
        base=base,
    )

    for q in query_list:
        stats["queries_run"] += 1
        try:
            rows = discover_usaspending_recipients(q, limit=limit_per_query)
        except Exception as e:
            logger.warning("USASpending query failed %s: %s", q, e)
            stats["errors"] += 1
            continue

        stats["fetched"] += len(rows)
        for row in rows:
            name_key = (row.get("company_name") or "").strip().lower()
            if not name_key or name_key in seen:
                stats["duplicates_skipped"] += 1
                continue
            seen.add(name_key)

            notes = (row.get("notes") or "") + " " + BURDEN_CONTEXT
            row = dict(row)
            row["notes"] = notes.strip()
            try:
                from services.intake.paperwork_prediction import predict_federal_supplier_paperwork

                fb = predict_federal_supplier_paperwork(
                    row.get("company_name", ""),
                    notes=row.get("notes", ""),
                    segment=row.get("segment", ""),
                    industry=row.get("industry", ""),
                )
                row["founding_pilot_enrichment"] = fb
                row["notes"] = (row["notes"] + "\n\n" + fb.get("likely_paperwork_prediction", "")).strip()
            except Exception:
                pass

            try:
                out = ingest_discovery_candidate(
                    row,
                    campaign_id=campaign_id,
                    message_variant=message_variant,
                    min_fit_score=min_fit_score,
                    base=base,
                )
            except Exception as e:
                logger.warning("Ingest failed for %s: %s", name_key, e)
                stats["errors"] += 1
                continue

            if out.get("skipped"):
                reason = out.get("reason", "")
                if reason == "below_fit_threshold":
                    stats["below_threshold"] += 1
                else:
                    stats["duplicates_skipped"] += 1
                continue

            stats["targets_created"] += 1

        if pause_seconds > 0:
            time.sleep(pause_seconds)

    telemetry.emit(
        "acquisition_learning",
        metadata={"connector": CONNECTOR_ID, **stats},
        base=base,
    )
    stats["message"] = (
        f"Live USASpending: {stats['targets_created']} new targets "
        f"({stats['fetched']} fetched, {stats['duplicates_skipped']} skipped)."
    )
    return stats

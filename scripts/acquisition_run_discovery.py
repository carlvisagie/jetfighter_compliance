#!/usr/bin/env python3
"""Run lawful public lead discovery (USASpending API + optional public websites)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.acquisition.discovery import run_finder_discovery


def main() -> int:
    p = argparse.ArgumentParser(description="Lawful public lead discovery for KYC")
    p.add_argument("--query", action="append", default=[], help="USASpending recipient search term")
    p.add_argument("--website", action="append", default=[], help="Public company website URL to analyze")
    p.add_argument("--limit", type=int, default=15, help="Max results per query")
    args = p.parse_args()
    queries = args.query or ["precision machining", "aerospace supplier", "defense manufacturing"]
    print("Running public discovery (no auto-contact)...")
    stats = run_finder_discovery(
        usaspending_queries=queries,
        website_urls=args.website,
        limit_per_query=args.limit,
    )
    print(f"Imported: {stats.imported}")
    print(f"Duplicates skipped: {stats.duplicates_skipped}")
    print(f"Rejected: {stats.rejected_rows}")
    print("Report: data/acquisition/reports/latest_discovery_report.md")
    print("Review: data/acquisition/leads/review_queue.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

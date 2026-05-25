#!/usr/bin/env python3
"""Import lead candidates from data/acquisition/leads/import_candidates.csv."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.acquisition.discovery import run_csv_import
from services.acquisition.storage import IMPORT_CSV, leads_dir, reports_dir


def main() -> int:
    base = leads_dir()
    import_path = base / IMPORT_CSV
    print(f"Importing from: {import_path}")
    try:
        stats = run_csv_import(import_path=import_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print(f"Create {import_path} with header row. See docs/LEAD_DISCOVERY_ENGINE.md")
        return 1
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    report = reports_dir() / "latest_discovery_report.md"
    print(f"Imported: {stats.imported}")
    print(f"Duplicates skipped: {stats.duplicates_skipped}")
    print(f"Rejected: {stats.rejected_rows}")
    print(f"Review queue (fit>=65): see data/acquisition/leads/review_queue.csv")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

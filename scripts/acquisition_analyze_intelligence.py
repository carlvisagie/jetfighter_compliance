#!/usr/bin/env python3
"""Analyze accumulated forensic acquisition intelligence and write reports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.acquisition.analytics import (
    analyze_acquisition_intel,
    write_acquisition_analytics_report,
    write_forensic_intelligence_report,
)
from services.acquisition.memory import recompute_weights_from_outcomes


def main() -> int:
    weights = recompute_weights_from_outcomes()
    intel = analyze_acquisition_intel()
    fa = write_forensic_intelligence_report()
    aa = write_acquisition_analytics_report()
    print("Learned weights:", json.dumps(weights, indent=2))
    print(f"Forensic report: {fa}")
    print(f"Analytics report: {aa}")
    print(f"Outcomes: {intel['outcome_count']} | Conversions: {intel['conversions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

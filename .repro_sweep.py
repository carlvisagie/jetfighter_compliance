"""Reproduce whatever's making /api/ops/ei-freshness return 500."""
import os
import sys
import traceback

# Mirror conftest's KYC_DATA pinning so the freshness module uses a
# real path it can scan. Use a tmp dir so we don't touch real data.
import tempfile
os.environ["KYC_DATA"] = tempfile.mkdtemp(prefix="ei-freshness-repro-")

try:
    from services.evidence_intelligence.freshness import sweep_intakes_for_staleness
    print("import OK")
    summary = sweep_intakes_for_staleness(dry_run=True)
    print("sweep OK:", summary)
except Exception:
    traceback.print_exc()
    sys.exit(2)

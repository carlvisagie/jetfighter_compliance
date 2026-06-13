"""Investigate compliance_intel failures."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

# Check telemetry for compliance_intel errors
TELEMETRY = Path("E:/JetFighter_Compliance/data/memory/telemetry.jsonl")

if TELEMETRY.is_file():
    lines = TELEMETRY.read_text(encoding="utf-8").strip().split("\n")
    
    print("=" * 80)
    print("COMPLIANCE_INTEL FAILURES - LAST 20")
    print("=" * 80)
    
    compliance_errors = []
    for line in reversed(lines):
        try:
            event = json.loads(line)
            if event.get("subsystem") == "compliance_intel" and not event.get("ok", True):
                compliance_errors.append(event)
                if len(compliance_errors) >= 20:
                    break
        except:
            pass
    
    for i, err in enumerate(reversed(compliance_errors), 1):
        print(f"\n[{i}] {err.get('when_utc', '')}")
        print(f"    Event: {err.get('event', '')}")
        print(f"    Detail: {err.get('detail', '')}")
        print(f"    Error: {err.get('error', '')}")
        if 'metadata' in err:
            meta = err['metadata']
            print(f"    Source: {meta.get('source_id', '')}")
            print(f"    URL: {meta.get('url', '')}")
            print(f"    Status: {meta.get('status_code', '')}")
else:
    print("No telemetry file found")

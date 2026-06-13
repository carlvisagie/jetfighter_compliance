"""Check recent errors from failing subsystems."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.lazy_io import iter_jsonl_lines

telem_file = Path("data/memory/telemetry.jsonl")

if not telem_file.exists():
    print(f"Telemetry file not found: {telem_file}")
    exit(1)

print("=" * 80)
print("FAILING SUBSYSTEM TELEMETRY ERRORS")
print("=" * 80)

failing_components = ['evidence_intelligence', 'compliance_intel', 'email']
errors = []

for event in iter_jsonl_lines(telem_file, tail_lines=500):
    component = event.get('component', '')
    severity = event.get('severity', '')
    
    if component in failing_components and severity in ('critical', 'error', 'warning'):
        errors.append(event)

print(f"\nFound {len(errors)} recent errors/warnings from failing subsystems")

if not errors:
    print("No errors found. Subsystems may have self-healed.")
else:
    print("\nRecent errors (last 15):")
    for e in errors[-15:]:
        comp = e.get('component', 'unknown')
        event_type = e.get('event_type', 'unknown')
        severity = e.get('severity', 'unknown')
        metadata = e.get('metadata', {})
        timestamp = e.get('timestamp_utc', 'unknown')
        
        print(f"\n[{severity.upper()}] {comp} / {event_type}")
        print(f"  Time: {timestamp}")
        if metadata:
            for k, v in list(metadata.items())[:3]:
                print(f"  {k}: {v}")

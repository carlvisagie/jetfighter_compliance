"""Check age of subsystem failures flagged by telemetry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.lazy_io import iter_jsonl_lines
from datetime import datetime, timezone, timedelta

telem_file = Path("data/memory/telemetry.jsonl")

print("=" * 80)
print("SUBSYSTEM FAILURE TIMELINE")
print("=" * 80)

failing_components = ['evidence_intelligence', 'compliance_intel', 'email']

# Check last 1000 events
all_events = list(iter_jsonl_lines(telem_file, tail_lines=1000))
print(f"\nAnalyzing last {len(all_events)} telemetry events...")

now = datetime.now(timezone.utc)
cutoff_24h = now - timedelta(hours=24)
cutoff_1h = now - timedelta(hours=1)

errors_by_component = {}
for comp in failing_components:
    errors_by_component[comp] = {
        'total': 0,
        'last_24h': 0,
        'last_1h': 0,
        'most_recent': None,
        'most_recent_age': None
    }

for event in all_events:
    component = event.get('component', '')
    severity = event.get('severity', '')
    timestamp_str = event.get('timestamp_utc', '')
    
    if component in failing_components and severity in ('critical', 'error'):
        errors_by_component[component]['total'] += 1
        
        try:
            event_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            if event_time > cutoff_24h:
                errors_by_component[component]['last_24h'] += 1
            
            if event_time > cutoff_1h:
                errors_by_component[component]['last_1h'] += 1
            
            if errors_by_component[component]['most_recent'] is None or event_time > errors_by_component[component]['most_recent']:
                errors_by_component[component]['most_recent'] = event_time
                age_hours = (now - event_time).total_seconds() / 3600
                errors_by_component[component]['most_recent_age'] = age_hours
        except Exception:
            pass

print("\n" + "=" * 80)
print("ERROR COUNTS BY SUBSYSTEM")
print("=" * 80)

for comp, data in errors_by_component.items():
    print(f"\n{comp}:")
    print(f"  Total errors in last 1000 events: {data['total']}")
    print(f"  Errors in last 24 hours: {data['last_24h']}")
    print(f"  Errors in last 1 hour: {data['last_1h']}")
    
    if data['most_recent']:
        print(f"  Most recent error: {data['most_recent'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Age: {data['most_recent_age']:.1f} hours ago")
    else:
        print(f"  Most recent error: NONE FOUND")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)

total_recent_errors = sum(d['last_24h'] for d in errors_by_component.values())

if total_recent_errors == 0:
    print("\nNO ERRORS in last 24 hours from these subsystems.")
    print("Telemetry is flagging HISTORICAL failures as 'recent'.")
    print("\nRECOMMENDATION: These subsystems have self-healed.")
    print("The 'degraded' status is based on stale failure detection.")
else:
    print(f"\nFound {total_recent_errors} errors in last 24 hours.")
    print("These subsystems are actively failing.")

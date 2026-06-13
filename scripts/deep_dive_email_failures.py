"""Deep dive into email failures in local telemetry."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.lazy_io import iter_jsonl_lines
from datetime import datetime, timezone, timedelta

telem_file = Path("data/memory/telemetry.jsonl")

print("=" * 80)
print("EMAIL SUBSYSTEM FAILURE ANALYSIS")
print("=" * 80)

if not telem_file.exists():
    print("Telemetry file not found!")
    exit(1)

# Get all events
all_events = list(iter_jsonl_lines(telem_file, tail_lines=2000))
print(f"\nAnalyzing last {len(all_events)} events...")

now = datetime.now(timezone.utc)
cutoff_24h = now - timedelta(hours=24)

# Find ALL email-related events
email_events = []
for event in all_events:
    subsystem = event.get('subsystem', '')
    component = event.get('component', '')
    
    if 'email' in subsystem.lower() or 'email' in component.lower():
        email_events.append(event)

print(f"\nTotal email-related events: {len(email_events)}")

# Find failures
email_failures = []
for event in email_events:
    if event.get('success') is False:
        ts_str = event.get('observed_at_utc', '')
        try:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            age_hours = (now - ts).total_seconds() / 3600
            
            email_failures.append({
                'timestamp': ts_str,
                'age_hours': age_hours,
                'in_window': ts > cutoff_24h,
                'event_type': event.get('event_type'),
                'message': event.get('message', '')[:100],
                'error_code': event.get('error_code'),
                'metadata': event.get('metadata', {})
            })
        except Exception as e:
            print(f"Error parsing timestamp: {e}")

print(f"Total email failures found: {len(email_failures)}")

if email_failures:
    print("\nEmail failures (most recent first):")
    email_failures.sort(key=lambda x: x['age_hours'])
    
    for i, failure in enumerate(email_failures[:10]):
        print(f"\n{i+1}. {failure['timestamp']}")
        print(f"   Age: {failure['age_hours']:.1f} hours")
        print(f"   In 24h window: {failure['in_window']}")
        print(f"   Event: {failure['event_type']}")
        print(f"   Message: {failure['message']}")
        if failure['error_code']:
            print(f"   Error Code: {failure['error_code']}")
    
    recent_failures = [f for f in email_failures if f['in_window']]
    print(f"\n" + "=" * 80)
    print(f"FAILURES IN LAST 24 HOURS: {len(recent_failures)}")
    
    if recent_failures:
        print("\nThese are actively failing - need to fix!")
    else:
        print("\nAll failures are OLDER than 24 hours - historical only!")
        print("The 24-hour filter is working correctly.")
else:
    print("\nNO EMAIL FAILURES FOUND - telemetry should be clean!")

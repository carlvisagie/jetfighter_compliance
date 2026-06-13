"""Check telemetry health issue."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.telemetry_diagnostics import build_telemetry_status

print("=" * 80)
print("TELEMETRY DIAGNOSTICS")
print("=" * 80)

try:
    status = build_telemetry_status()
    print(f"\nTelemetry Health: {status.get('telemetry_health')}")
    print(f"Telemetry Pulse: {status.get('telemetry_pulse')}")
    print(f"Stale Threshold Exceeded: {status.get('stale_threshold_exceeded')}")
    print(f"Sample Count: {status.get('telemetry_sample_count')}")
    print(f"Last Write: {status.get('last_telemetry_write_utc')}")
    print(f"Queue Depth: {status.get('queue_depth')}")
    
    degraded = status.get('degraded_reasons', [])
    if degraded:
        print(f"\nDegraded Reasons ({len(degraded)}):")
        for r in degraded:
            print(f"  - {r.get('code')}: {r.get('message')}")
            print(f"    Action: {r.get('recommended_action')}")
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

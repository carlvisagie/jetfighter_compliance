"""Test telemetry diagnostics after fix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.telemetry_diagnostics import build_telemetry_status

print("=" * 80)
print("TELEMETRY DIAGNOSTICS AFTER FIX")
print("=" * 80)

status = build_telemetry_status()

print(f"\nTelemetry Health: {status.get('telemetry_health')}")
print(f"Telemetry Pulse: {status.get('telemetry_pulse')}")
print(f"Failing Subsystems: {status.get('failing_subsystems')}")
print(f"Queue Depth: {status.get('queue_depth')}")

degraded = status.get('degraded_reasons', [])
print(f"\nDegraded Reasons: {len(degraded)}")

if degraded:
    for r in degraded:
        print(f"\n  Code: {r.get('code')}")
        print(f"  Message: {r.get('message')}")
        print(f"  Action: {r.get('recommended_action')}")
else:
    print("\n✓ NO degraded reasons - telemetry is HEALTHY!")

print("\n" + "=" * 80)
if status.get('telemetry_health') == 'healthy':
    print("SUCCESS: Telemetry should now show GREEN!")
else:
    print(f"Status: {status.get('telemetry_health')} - still degraded")

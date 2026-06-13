"""Check final telemetry and organism health."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("FINAL ORGANISM HEALTH CHECK")
print("=" * 80)

# Check telemetry
r = client.get(f"{base_url}/api/telemetry/diagnostics", timeout=20)
if r.status_code == 200:
    tel = r.json()
    print(f"\nTelemetry Health: {tel.get('health')}")
    print(f"Status: {tel.get('status')}")
    print(f"Pulse: {tel.get('pulse')}")
    
    failing = tel.get('failing_subsystems', [])
    print(f"\nFailing subsystems: {failing if failing else 'NONE'}")
    
    recent_errors = tel.get('recent_errors', [])
    ci_errors = [e for e in recent_errors if 'compliance' in e.get('event', '').lower()]
    print(f"\nCompliance intelligence errors: {len(ci_errors)}")
    if ci_errors:
        for err in ci_errors[:5]:
            print(f"  - {err.get('event')}: {err.get('detail')}")

# Check compliance intelligence status
r = client.get(f"{base_url}/api/operator/compliance-intelligence", timeout=20)
if r.status_code == 200:
    ci = r.json()
    unreachable = ci.get('unreachable_sources', [])
    print(f"\nUnreachable sources: {unreachable if unreachable else 'NONE'}")

print("\n" + "=" * 80)

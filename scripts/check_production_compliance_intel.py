"""Check production telemetry for compliance_intel failures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("CHECKING PRODUCTION TELEMETRY FOR COMPLIANCE_INTEL FAILURES")
print("=" * 80)

# Get telemetry diagnostics
r = client.get(f"{base_url}/api/telemetry/diagnostics", timeout=20)
if r.status_code == 200:
    data = r.json()
    print(f"\nHealth: {data.get('health')}")
    print(f"Status: {data.get('status')}")
    print(f"Pulse: {data.get('pulse')}")
    
    failing = data.get('failing_subsystems', [])
    if 'compliance_intel' in failing:
        print("\n[CONFIRMED] compliance_intel is failing")
    
    recent = data.get('recent_errors', [])
    print(f"\nRecent errors: {len(recent)}")
    
    ci_errors = [e for e in recent if 'compliance' in e.get('event', '').lower()]
    if ci_errors:
        print("\n[COMPLIANCE_INTEL ERRORS]")
        for err in ci_errors[:10]:
            print(f"  - {err.get('event')}: {err.get('detail')}")

# Get actual compliance intelligence status
print("\n" + "=" * 80)
print("CHECKING COMPLIANCE INTELLIGENCE SUBSYSTEM")
print("=" * 80)

r = client.get(f"{base_url}/api/operator/compliance-intelligence", timeout=20)
if r.status_code == 200:
    data = r.json()
    print(f"\nSources tracked: {data.get('sources_count')}")
    print(f"Unreachable sources: {len(data.get('unreachable_sources', []))}")
    
    unreachable = data.get('unreachable_sources', [])
    if unreachable:
        print("\n[UNREACHABLE SOURCES]")
        for src in unreachable:
            print(f"  - {src}")
    
    stale = data.get('stale_sources', [])
    if stale:
        print(f"\nStale sources: {len(stale)}")
        for src in stale:
            print(f"  - {src}")

print("\n" + "=" * 80)

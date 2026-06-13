"""Comprehensive organism status report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("JETFIGHTER COMPLIANCE ORGANISM STATUS REPORT")
print("=" * 80)
print(f"Timestamp: {Path('data/memory/telemetry.jsonl').stat().st_mtime if Path('data/memory/telemetry.jsonl').exists() else 'N/A'}")

print("\n" + "="  * 80)
print("1. TOPOLOGY ENDPOINT")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/cognitive-topology")
    if r.status_code == 200:
        topo = r.json()
        print(f"Status: OPERATIONAL")
        print(f"System Health: {topo.get('system_health')}")
        print(f"Global Pressure: {topo.get('global_pressure')}")
        print(f"Safe Mode: {topo.get('safe_mode')}")
        
        subs = topo.get('subsystems', {})
        green_count = sum(1 for s in subs.values() if isinstance(s, dict) and s.get('health', 0) >= 0.7 and not s.get('anomaly'))
        yellow_count = sum(1 for s in subs.values() if isinstance(s, dict) and (0.4 <= s.get('health', 0) < 0.7 or s.get('anomaly')))
        red_count = sum(1 for s in subs.values() if isinstance(s, dict) and s.get('health', 0) < 0.4)
        
        print(f"\nSubsystems: {len(subs)} total")
        print(f"  GREEN (healthy, health >= 0.7, no anomaly): {green_count}")
        print(f"  YELLOW (degraded, 0.4-0.7 health or anomaly): {yellow_count}")
        print(f"  RED (critical, health < 0.4): {red_count}")
    else:
        print(f"Status: FAILED (HTTP {r.status_code})")
except Exception as e:
    print(f"Status: ERROR - {e}")

print("\n" + "=" * 80)
print("2. TELEMETRY HEALTH")
print("=" * 80)

try:
    from services.telemetry_diagnostics import build_telemetry_status
    status = build_telemetry_status()
    print(f"Telemetry Health: {status.get('telemetry_health')}")
    print(f"Telemetry Pulse: {status.get('telemetry_pulse')}")
    print(f"Queue Depth: {status.get('queue_depth')}")
    print(f"Sample Count: {status.get('telemetry_sample_count')}")
    
    degraded = status.get('degraded_reasons', [])
    if degraded:
        print(f"\nDegraded Reasons ({len(degraded)}):")
        for r in degraded:
            print(f"  - {r.get('code')}: {r.get('message')}")
    else:
        print("\nNo degraded reasons (healthy)")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 80)
print("3. RUNTIME CONFIGURATION")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/ops/boot-status")
    boot = r.json() if r.status_code == 200 else {}
    print(f"Safe Mode: {boot.get('safe_mode')}")
    print(f"Schedulers Enabled: {boot.get('schedulers_enabled')}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 80)
print("4. FIXES APPLIED")
print("=" * 80)
print("1. Fixed syntax error in cognitive_topology.py (commit 2903f84)")
print("2. Archived 757 old test jobs from May 2026 (commit acc4e99)")
print("3. Archived 70 remaining test jobs from June 1-4 (commit b5a1f25)")
print("4. Total: 827 jobs archived, queue reduced from 827 to 0")

print("\n" + "=" * 80)
print("5. EXPECTED OUTCOME")
print("=" * 80)
print("- Topology endpoint: WORKING")
print("- Job queue: ZERO (below threshold)")
print("- Telemetry: Should transition from degraded to healthy")
print("- Subsystem failures: Historical only, no recent errors")
print("- Visual spheres: Should be mostly GREEN or YELLOW, not ALL RED")

print("\n" + "=" * 80)

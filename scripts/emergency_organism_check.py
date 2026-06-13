"""Emergency organism state check."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()

base_url = diag.base_url

print("=" * 80)
print("ORGANISM TOPOLOGY STATE")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/cognitive-topology")
    r.raise_for_status()
    topology = r.json()
    
    print(f"\nOK: {topology.get('ok')}")
    print(f"System Health: {topology.get('system_health')}")
    print(f"Global Pressure: {topology.get('global_pressure')}")
    print(f"Safe Mode: {topology.get('safe_mode')}")
    
    print("\n" + "=" * 80)
    print("SUBSYSTEM STATES")
    print("=" * 80)
    
    subs = topology.get('subsystems', {})
    for name, data in sorted(subs.items()):
        if isinstance(data, dict):
            health = data.get('health', 'N/A')
            pressure = data.get('pressure', 'N/A')
            anomaly = data.get('anomaly', False)
            paused = data.get('paused', False)
            status_flags = []
            if anomaly:
                status_flags.append('ANOMALY')
            if paused:
                status_flags.append('PAUSED')
            flags = f" [{', '.join(status_flags)}]" if status_flags else ""
            print(f"{name:20} | Health: {health:6} | Pressure: {pressure:6}{flags}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("ORGANISM STATE")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/operator/organism/state")
    r.raise_for_status()
    state = r.json()
    
    print(f"\nHealth State: {state.get('health_state')}")
    print(f"Current Bottleneck: {state.get('current_bottleneck')}")
    print(f"Next Action: {state.get('next_recommended_action')}")
    
    checks = state.get('checks', [])
    print(f"\nTotal Checks: {len(checks)}")
    
    failed = [c for c in checks if c.get('status') != 'pass']
    if failed:
        print(f"\nFAILED CHECKS ({len(failed)}):")
        for check in failed[:10]:
            print(f"  - {check.get('category')}: {check.get('message')}")
            print(f"    Status: {check.get('status')} | Severity: {check.get('severity')}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

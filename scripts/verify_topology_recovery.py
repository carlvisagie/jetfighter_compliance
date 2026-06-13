"""Wait for deployment and verify organism recovery."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("WAITING FOR DEPLOYMENT TO COMPLETE")
print("=" * 80)
print(f"Target commit: 2903f84")
print(f"Checking build info every 15 seconds...\n")

target_commit = "2903f84"
max_attempts = 20  # 5 minutes
attempt = 0

while attempt < max_attempts:
    attempt += 1
    try:
        r = client.get(f"{base_url}/api/public/build-info")
        if r.status_code == 200:
            build = r.json()
            current_commit = build.get("git_commit", "unknown")[:7]
            print(f"[{attempt}/{max_attempts}] Current commit: {current_commit}")
            
            if current_commit == target_commit:
                print("\n" + "=" * 80)
                print("DEPLOYMENT COMPLETE!")
                print("=" * 80)
                break
        else:
            print(f"[{attempt}/{max_attempts}] Build info unavailable (status {r.status_code})")
    except Exception as e:
        print(f"[{attempt}/{max_attempts}] Error checking build: {e}")
    
    if attempt < max_attempts:
        time.sleep(15)
else:
    print("\nTimeout waiting for deployment. Checking topology anyway...\n")

print("\n" + "=" * 80)
print("VERIFYING TOPOLOGY ENDPOINT")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/cognitive-topology")
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"\nSUCCESS! Topology is working!")
        print(f"OK: {data.get('ok')}")
        print(f"System Health: {data.get('system_health')}")
        print(f"Global Pressure: {data.get('global_pressure')}")
        print(f"Safe Mode: {data.get('safe_mode')}")
        
        subs = data.get('subsystems', {})
        print(f"\nSubsystems ({len(subs)}):")
        for name in ['acquisition', 'knowledge', 'observability', 'upload_pipeline', 
                     'evidence_processing', 'learning', 'telemetry', 'alerts']:
            if name in subs:
                s = subs[name]
                health = s.get('health', 'N/A')
                paused = ' [PAUSED]' if s.get('paused') else ''
                anomaly = ' [ANOMALY]' if s.get('anomaly') else ''
                print(f"  {name:20} | Health: {health:6}{paused}{anomaly}")
    else:
        print(f"\nERROR: Still returning {r.status_code}")
        print(r.text[:500])
        
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("CHECKING ORGANISM STATE")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/operator/organism/state")
    if r.status_code == 200:
        state = r.json()
        print(f"\nHealth State: {state.get('health_state')}")
        print(f"Bottleneck: {state.get('current_bottleneck')}")
        print(f"Next Action: {state.get('next_recommended_action')}")
    else:
        print(f"ERROR: Status {r.status_code}")
except Exception as e:
    print(f"ERROR: {e}")

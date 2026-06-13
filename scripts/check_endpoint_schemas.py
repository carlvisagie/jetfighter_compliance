"""Check what these endpoints actually return."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("CHECKING ENDPOINT SCHEMAS")
print("=" * 80)

# Check Organism Observability
print("\n[1] Organism Observability")
try:
    r = client.get(f"{base_url}/api/operator/organism-observability?limit=5", timeout=20)
    if r.status_code == 200:
        data = r.json()
        print(f"Keys: {list(data.keys())}")
        if "events" not in data and "recent_events" not in data:
            print("ISSUE: No events field")
    else:
        print(f"ERROR: {r.status_code}")
except Exception as e:
    print(f"ERROR: {e}")

# Check Operational Alerts
print("\n[2] Operational Alerts")
try:
    r = client.get(f"{base_url}/api/operator/operational-alerts", timeout=20)
    if r.status_code == 200:
        data = r.json()
        print(f"Keys: {list(data.keys())}")
        if "items" not in data and "alerts" not in data:
            print("ISSUE: No items or alerts field")
    else:
        print(f"ERROR: {r.status_code}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 80)

"""Check actual acquisition intelligence and reddit endpoints."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("ACQUISITION INTELLIGENCE & REDDIT STATUS")
print("=" * 80)

# Check Acquisition Intelligence
print("\n1. ACQUISITION INTELLIGENCE")
print("-" * 80)

try:
    r = client.get(f"{base_url}/api/operator/acquisition-intelligence")
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"\nResponse:")
        print(json.dumps(data, indent=2)[:500])
    else:
        print(f"Error: {r.text[:200]}")
except Exception as e:
    print(f"Exception: {e}")

# Check Reddit Acquisition
print("\n" + "=" * 80)
print("2. REDDIT ACQUISITION")
print("-" * 80)

try:
    r = client.get(f"{base_url}/api/operator/reddit-acquisition")
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"\nResponse:")
        print(json.dumps(data, indent=2)[:500])
    else:
        print(f"Error: {r.text[:200]}")
except Exception as e:
    print(f"Exception: {e}")

print("\n" + "=" * 80)

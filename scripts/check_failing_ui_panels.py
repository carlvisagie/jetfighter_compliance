"""Check the actual production endpoints that are failing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("CHECKING FAILING ENDPOINTS IN PRODUCTION")
print("=" * 80)

# Check Acquisition Intelligence
print("\n[1] Acquisition Intelligence:")
r = client.get(f"{base_url}/api/operator/acquisition-intelligence")
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(f"Error: {r.text[:500]}")
else:
    data = r.json()
    print(f"Response ok: {data.get('ok')}")
    if not data.get('ok'):
        print(f"Error: {data.get('error')}")
        print(f"Detail: {data.get('detail')}")
    else:
        print(f"Data keys: {list(data.keys())}")

# Check Reddit Acquisition
print("\n[2] Reddit Acquisition:")
r = client.get(f"{base_url}/api/operator/reddit-acquisition")
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print(f"Error: {r.text[:500]}")
else:
    data = r.json()
    print(f"Response ok: {data.get('ok')}")
    if not data.get('ok'):
        print(f"Error: {data.get('error')}")
        print(f"Detail: {data.get('detail')}")
    else:
        print(f"Data keys: {list(data.keys())}")

print("\n" + "=" * 80)

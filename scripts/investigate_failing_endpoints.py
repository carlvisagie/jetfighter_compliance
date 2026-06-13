"""Investigate failing endpoints in detail."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("INVESTIGATING FAILING ENDPOINTS")
print("=" * 80)

# Check Evidence Intelligence
print("\n[1] Evidence Intelligence Endpoint:\n")
r = client.get(f"{base_url}/api/operator/evidence-intelligence")
print(f"Status: {r.status_code}")
print(f"Response: {json.dumps(r.json(), indent=2)}")

# Check Customer Friction
print("\n[2] Customer Friction Endpoint:\n")
try:
    r = client.get(f"{base_url}/api/operator/customer-friction")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)

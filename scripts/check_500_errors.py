"""Check what's causing the 500 errors."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("Checking 500 errors...")

for endpoint in ["/api/operator/acquisition-intelligence", "/api/operator/reddit-acquisition"]:
    r = client.get(f"{base_url}{endpoint}")
    print(f"\n{endpoint}")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")

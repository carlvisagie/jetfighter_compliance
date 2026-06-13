"""Check endpoint error details."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("Checking endpoint error details...")

r = client.get(f"{base_url}/api/operator/acquisition/pending")
print(f"\nStatus: {r.status_code}")
print(f"Response: {r.text}")

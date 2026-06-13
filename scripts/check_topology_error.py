"""Get detailed error from cognitive topology endpoint."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("Attempting to call /api/cognitive-topology...")
print(f"Base URL: {base_url}")

try:
    r = client.get(f"{base_url}/api/cognitive-topology")
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print("\nResponse body:")
    print(r.text[:2000])
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

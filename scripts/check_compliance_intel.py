"""Check compliance intelligence response."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

r = client.get(f"{base_url}/api/operator/compliance-intelligence", timeout=20)
print(f"Status: {r.status_code}")

import json
data = r.json()
print("\nResponse keys:")
for key in sorted(data.keys()):
    val = data[key]
    if isinstance(val, (list, dict)):
        print(f"  {key}: {type(val).__name__} (len={len(val)})")
    else:
        print(f"  {key}: {val}")

print("\nFull response:")
print(json.dumps(data, indent=2)[:1000])

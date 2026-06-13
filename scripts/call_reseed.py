"""Call reseed endpoint to refresh cached sources."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("FORCING RE-SEED OF COMPLIANCE INTELLIGENCE SOURCES")
print("=" * 80)

r = client.post(f"{base_url}/api/operator/compliance-intelligence/reseed-sources", timeout=20)

if r.status_code == 200:
    data = r.json()
    print(f"\nOK: {data.get('ok')}")
    print(f"Sources count: {data.get('sources_count')}")
    
    print("\nUpdated sources:")
    for src in data.get('sources', []):
        print(f"  {src['source_id']}: {src['url']}")
else:
    print(f"\nERROR: {r.status_code}")
    print(r.text[:500])

print("\n" + "=" * 80)

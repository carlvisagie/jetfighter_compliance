"""Force re-seed compliance intelligence sources in production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("Force re-seeding compliance intelligence sources...")
print("This will update cached sources with the new URLs")

# Get current sources
r = client.get(f"{base_url}/api/operator/compliance-intelligence", timeout=20)
if r.status_code == 200:
    data = r.json()
    print(f"\nCurrent sources: {data.get('sources_count')}")
    print(f"Unreachable: {len(data.get('unreachable_sources', []))}")

# The sources are cached in data/compliance_intelligence/sources.json
# The only way to refresh them is to update them individually or delete and re-seed
# Since we can't delete files via API, let's use the update endpoint if it exists

print("\nWAITING for deployment to propagate...")
print("The new DEFAULT_SOURCES need to be loaded by the deployed code")

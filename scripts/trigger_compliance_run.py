"""Trigger compliance intelligence run to refresh sources."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("Triggering compliance intelligence check...")

r = client.post(
    f"{base_url}/api/operator/compliance-intelligence/run",
    json={"polling_filter": ""},
    timeout=60
)

if r.status_code == 200:
    data = r.json()
    print(f"OK - Run completed: {data.get('ok')}")
    if 'summary' in data:
        summary = data['summary']
        print(f"Sources checked: {summary.get('sources_checked', 0)}")
        print(f"Changes detected: {summary.get('changes_detected', 0)}")
        print(f"Errors: {summary.get('errors', 0)}")
else:
    print(f"ERROR: {r.status_code}")
    print(r.text[:500])

"""Check PRODUCTION intake queue for PATCH entries."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("PRODUCTION INTAKE QUEUE - PATCH SEARCH")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/operator/intake/queue")
    r.raise_for_status()
    data = r.json()
    
    queue = data.get('queue', [])
    print(f"\nTotal intakes in production queue: {len(queue)}")
    
    # Find any with PATCH in company name
    patch_entries = []
    for entry in queue:
        company = entry.get('company', '')
        if 'PATCH' in company.upper() or 'patch' in company:
            patch_entries.append({
                'intake_id': entry.get('intake_id'),
                'company': company,
                'email': entry.get('email'),
                'status': entry.get('review_status')
            })
    
    if patch_entries:
        print(f"\nFOUND {len(patch_entries)} PATCH ENTRIES IN PRODUCTION:")
        print("=" * 80)
        for entry in patch_entries:
            print(f"\nIntake ID: {entry['intake_id']}")
            print(f"  Company: {entry['company']}")
            print(f"  Email: {entry['email']}")
            print(f"  Status: {entry['status']}")
    else:
        print("\nNo PATCH entries found in production queue.")
        
    # Also check ALL entries for any test patterns
    print("\n" + "=" * 80)
    print("ALL QUEUE ENTRIES")
    print("=" * 80)
    for entry in queue[:20]:  # First 20
        print(f"{entry.get('intake_id')} - {entry.get('company')} - {entry.get('review_status')}")
    
    if len(queue) > 20:
        print(f"... and {len(queue) - 20} more")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

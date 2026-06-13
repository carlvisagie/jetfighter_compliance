"""Archive the 3 PATCH intakes from production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("ARCHIVING PATCH INTAKES FROM PRODUCTION")
print("=" * 80)

patch_intakes = [
    "FB-ef534aac1a91",  # PATCH13A4C Verify 20260611_102958
    "FB-02c704711107",  # PATCH13A4C Verify 20260611_102820
    "FB-e35494cabff2",  # PATCH13A4C Verify 20260611_102735
]

print(f"\nArchiving {len(patch_intakes)} PATCH intakes...\n")

archived_count = 0
failed_count = 0

for intake_id in patch_intakes:
    try:
        r = client.post(
            f"{base_url}/api/operator/intake/action",
            json={
                "intake_id": intake_id,
                "action": "archive",
                "operator_note": "Test data cleanup - PATCH identifier removal"
            }
        )
        r.raise_for_status()
        result = r.json()
        
        if result.get('ok'):
            print(f"[OK] Archived: {intake_id}")
            print(f"     Status: {result.get('review_status')}")
            archived_count += 1
        else:
            print(f"[FAIL] {intake_id}: {result}")
            failed_count += 1
            
    except Exception as e:
        print(f"[ERROR] {intake_id}: {e}")
        failed_count += 1

print("\n" + "=" * 80)
print(f"ARCHIVE COMPLETE")
print("=" * 80)
print(f"Archived: {archived_count}")
print(f"Failed: {failed_count}")

# Verify they're gone from queue
print("\n" + "=" * 80)
print("VERIFYING QUEUE")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/operator/intake/queue")
    r.raise_for_status()
    data = r.json()
    
    queue = data.get('queue', [])
    print(f"\nTotal intakes in queue: {len(queue)}")
    
    remaining_patch = []
    for entry in queue:
        company = entry.get('company', '')
        if 'PATCH' in company.upper() or 'patch' in company:
            remaining_patch.append({
                'intake_id': entry.get('intake_id'),
                'company': company,
            })
    
    if remaining_patch:
        print(f"\nWARNING: Still {len(remaining_patch)} PATCH entries in queue:")
        for entry in remaining_patch:
            print(f"  - {entry['intake_id']}: {entry['company']}")
    else:
        print("\nSUCCESS: No PATCH entries remain in queue!")
        
except Exception as e:
    print(f"ERROR verifying queue: {e}")

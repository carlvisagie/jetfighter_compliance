"""Archive ALL remaining test intakes from production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ops_client import authenticate_production

client, headers, diag = authenticate_production()
base_url = diag.base_url

print("=" * 80)
print("ARCHIVING ALL TEST INTAKES FROM PRODUCTION")
print("=" * 80)

test_intakes = [
    "FB-7c74b5f9233c",   # Aegis
    "FB-2da73c738274",   # Aegis
    "FB-c56ce04b469c",   # Audit Test Company
    "FB-f2b751c50ef3",   # Aegis Defense Systems
    "FB-1a4a469f832a",   # Aegis Defense Systems
    "FB-97bbf7703e74",   # Aegis Defense Systems LLC
    "FB-8f2e7d8b12eb",   # Aegis 13A4F Verification
    "FB-97c640777787",   # Aegis 13A4F Verification
    "FB-3bd13bb472ac",   # (empty company)
    "FB-15e0e4ea9c73",   # (empty company)
]

print(f"\nArchiving {len(test_intakes)} test intakes...\n")

archived_count = 0
failed_count = 0

for intake_id in test_intakes:
    try:
        r = client.post(
            f"{base_url}/api/operator/intake/action",
            json={
                "intake_id": intake_id,
                "action": "archive",
                "operator_note": "Test data cleanup - all test entries removed before first client onboarding"
            }
        )
        r.raise_for_status()
        result = r.json()
        
        if result.get('ok'):
            company = result.get('classification', {}).get('company_name', 'unknown')
            print(f"[OK] Archived: {intake_id} ({company})")
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

# Verify queue is completely empty
print("\n" + "=" * 80)
print("FINAL VERIFICATION")
print("=" * 80)

try:
    r = client.get(f"{base_url}/api/operator/intake/queue")
    r.raise_for_status()
    data = r.json()
    
    queue = data.get('queue', [])
    print(f"\nTotal intakes remaining in queue: {len(queue)}")
    
    if len(queue) == 0:
        print("\n🎯 SUCCESS: Production intake queue is now COMPLETELY CLEAN!")
        print("Ready for first real client onboarding.")
    else:
        print(f"\nWARNING: {len(queue)} intakes still in queue:")
        for entry in queue:
            print(f"  - {entry.get('intake_id')}: {entry.get('company')}")
        
except Exception as e:
    print(f"ERROR verifying queue: {e}")

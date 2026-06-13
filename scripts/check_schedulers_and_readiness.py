"""Check scheduler status and validation quality."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.runtime_boot import schedulers_enabled
from services.production import readiness_checks

print("=" * 80)
print("SCHEDULER STATUS")
print("=" * 80)

enabled = schedulers_enabled()
print(f"\nSchedulers enabled: {enabled}")

print("\n" + "=" * 80)
print("READINESS CHECKS")
print("=" * 80)

checks = readiness_checks()
print(f"\nTotal checks: {len(checks)}")

failed = [c for c in checks if c.get('status') != 'pass']
print(f"Failed checks: {len(failed)}")

if failed:
    print("\nFailed checks detail:")
    for check in failed:
        print(f"\n  Category: {check.get('category')}")
        print(f"  Status: {check.get('status')}")
        print(f"  Severity: {check.get('severity')}")
        print(f"  Message: {check.get('message')}")
        print(f"  Detail: {check.get('detail', 'N/A')}")

# Check for cognition_validation_quality specifically
cog_checks = [c for c in checks if 'cognition' in c.get('category', '').lower() or 'validation' in c.get('category', '').lower() or 'quality' in c.get('category', '').lower()]
if cog_checks:
    print("\n" + "=" * 80)
    print("COGNITION/VALIDATION/QUALITY CHECKS")
    print("=" * 80)
    for check in cog_checks:
        print(f"\n  {check.get('category')}: {check.get('status')}")
        print(f"  Message: {check.get('message')}")

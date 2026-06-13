"""Check organism unified status blockers."""
import sys
sys.path.insert(0, ".")

from services.memory.organism_integration import ENGINE_REGISTRY
from pathlib import Path

# Check critical_outside
outside = [(e_id, e) for e_id, e in ENGINE_REGISTRY.items() if e.get("classification") == "outside"]
critical_outside = [
    (e_id, e) for e_id, e in outside
    if e_id not in ("emails", "health", "reports_export", "ui_ops")
    and e.get("orphan_risk") in ("high", "medium")
]

print(f"=== UNIFIED STATUS BLOCKERS ===\n")
print(f"Total outside subsystems: {len(outside)}")
print(f"Critical outside (blocks unified): {len(critical_outside)}")

if critical_outside:
    print("\nCRITICAL BLOCKING SUBSYSTEMS:")
    for e_id, e in critical_outside:
        print(f"  - {e_id}: {e.get('label', 'N/A')}")
        print(f"    Orphan risk: {e.get('orphan_risk', 'unknown')}")
        print(f"    Paths: {e.get('paths', [])}")
        # Check if path exists
        for path in e.get("paths", []):
            p = Path(path)
            exists = p.exists() if "/" not in str(p) else "N/A"
            print(f"      {path}: {'EXISTS' if exists == True else 'DELETED' if exists == False else exists}")
else:
    print("\nNO CRITICAL BLOCKERS - Ready for unified!")

# Check duplicate islands
plugged_partial = [e for e_id, e in ENGINE_REGISTRY.items() if e.get("classification") in ("plugged", "partial")]
duplicate_islands = [e for e in plugged_partial if e.get("duplicate_truth_risk") == "high"]
print(f"\nDuplicate truth islands (must be <=1): {len(duplicate_islands)}")
if duplicate_islands:
    for e in duplicate_islands:
        print(f"  - {e.get('label', 'N/A')}")

print(f"\n=== VERDICT ===")
unified = len(critical_outside) == 0 and len(duplicate_islands) <= 1
print(f"organism_unified: {unified}")
if not unified:
    print(f"Blockers: {len(critical_outside)} critical outside, {len(duplicate_islands)} duplicate islands")

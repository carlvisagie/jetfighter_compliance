import sys
sys.path.insert(0, ".")
from services.memory.organism_integration import run_integration_audit
import json

audit = run_integration_audit()

print("=== ORGANISM INTEGRATION STATUS ===\n")
print(f"Verdict: {audit['verdict']}")
print(f"Unified: {'YES' if audit['verdict'] == 'organism_unified' else 'NO - PARTIAL ONLY'}\n")

print("=== SUBSYSTEM WIRING STATUS ===\n")

# Check each subsystem
for subsystem in audit['plugged']:
    orphan = subsystem['orphan_risk']
    dup = subsystem['duplicate_truth_risk']
    fix = subsystem['fix_needed']
    
    if orphan in ('high', 'medium') or dup in ('high', 'medium') or fix:
        status = "WARNING"
        print(f"{status:20} {subsystem['label']:50}")
        if orphan != 'low':
            print(f"                     - Orphan risk: {orphan}")
        if dup != 'low' and dup != 'none':
            print(f"                     - Duplicate truth risk: {dup}")
        if fix:
            print(f"                     - Fix needed: {fix}")
        print()
    else:
        status = "OK"
        print(f"{status:20} {subsystem['label']}")

print("\n=== OUTSIDE/LEGACY (NOT CONNECTED) ===\n")
for subsystem in audit['outside']:
    if subsystem['id'] != 'organism_sqlite':  # Skip if not the dead code one
        continue
    print(f"DEAD CODE           {subsystem['label']}")
    print(f"                     - {subsystem.get('fix_needed', 'Legacy SQLite - not wired to central memory')}")

print(f"\n=== WARNINGS ===\n")
for warning in audit['warnings']:
    print(f"WARNING: {warning}")

print(f"\n=== VERDICT ===")
if audit['verdict'] == 'organism_unified':
    print("ALL SUBSYSTEMS PROPERLY WIRED")
else:
    print("ORGANISM NOT FULLY UNIFIED - WIRING ISSUES EXIST")

import sys
sys.path.insert(0, ".")
from services.memory.self_healing import run_self_healing_scan

print("Running self-healing scan...")
result = run_self_healing_scan(write_suggestions=True)

print(f"\nOrphan projects: {len(result.get('orphan_projects', []))}")
print(f"Orphan inquiries: {len(result.get('orphan_inquiries', []))}")
print(f"Unlinked forensic projects: {len(result.get('unlinked_forensic_projects', []))}")
print(f"Unlinked RFQ projects: {len(result.get('unlinked_rfq_projects', []))}")
print(f"Pending orphans: {len(result.get('pending_orphans', []))}")
print(f"\nSuggestions written: {result.get('suggestion_count', 0)}")
print("\nSelf-healing complete.")

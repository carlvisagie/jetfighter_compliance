"""Check for misplaced defensive_wiring imports."""
import re
from pathlib import Path

ROOT = Path("E:/JetFighter_Compliance")
SERVICES = ROOT / "services"

print("=" * 80)
print("CHECKING FOR MISPLACED DEFENSIVE_WIRING IMPORTS")
print("=" * 80)

# Pattern: import block with defensive_wiring inside
pattern = re.compile(
    r'from [^\(]+\(\s*\n'  # Start of import block
    r'(?:.*\n)*?'  # Any lines
    r'(from services\.defensive_wiring import.*\n)'  # MISPLACED IMPORT
    r'(?:.*\n)*?'  # More lines
    r'\)',  # End of import block
    re.MULTILINE
)

files_to_check = [
    "services/customer_friction.py",
    "services/acquisition/connectors/reddit/learning.py",
    "services/alerts_center.py",
    "services/intake/evidence_registry.py",
    "services/external_verification/storage.py",
    "services/compliance_intelligence/snapshots.py",
    "services/compliance_health/assessment.py",
    "services/alerts/throttling.py",
    "services/alerts/dedupe.py",
    "services/acquisition/connectors/reddit/poster.py",
    "services/acquisition/ideal_customer_profile.py",
    "services/durable_storage.py",
    "services/project_deliverables.py",
    "services/final_release_scan.py",
    "services/knowledge_cockpit/import_pipeline.py",
    "services/intake/learning_hooks.py",
    "services/intake/durable_root.py",
    "services/intake/classification.py",
    "services/evidence_intelligence/storage.py",
    "services/compliance_health/registry.py",
    "services/compliance_intelligence/sources.py",
    "services/compliance_intelligence/__init__.py",
    "services/alerts/paths.py",
    "services/alerts/digest.py",
    "services/acquisition/social_intelligence/subreddit_culture.py",
    "services/acquisition/outreach_safety.py",
    "services/acquisition/connectors/reddit/__init__.py",
    "services/acquisition/export.py",
]

issues = []

for rel_path in files_to_check:
    file_path = ROOT / rel_path
    if not file_path.is_file():
        continue
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue
    
    # Look for defensive_wiring import inside another import block
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if 'from services.defensive_wiring import' in line:
            # Check if previous line has an open paren without matching close
            context_start = max(0, i - 5)
            context_lines = lines[context_start:i+5]
            context = '\n'.join(context_lines)
            
            # Check if we're inside an import block
            paren_count = 0
            for j in range(max(0, i-10), i):
                paren_count += lines[j].count('(') - lines[j].count(')')
            
            if paren_count > 0:
                issues.append((rel_path, i, line.strip()))
                print(f"\n[ISSUE] {rel_path}:{i}")
                print(f"        {line.strip()}")
                print(f"        ^ INSIDE ANOTHER IMPORT BLOCK")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\nFiles checked: {len(files_to_check)}")
print(f"Files with issues: {len(issues)}")

if issues:
    print("\n[ACTION REQUIRED] Fix the misplaced imports above")
else:
    print("\n[SUCCESS] No misplaced imports found")

print("\n" + "=" * 80)

"""Comprehensive defensive wiring migration - all patterns."""
import re
from pathlib import Path
from typing import List, Tuple

def add_defensive_import(content: str) -> str:
    """Add defensive_wiring import if not present."""
    if "from services.defensive_wiring import" in content or "from ..defensive_wiring import" in content:
        return content
    
    # Find first import block
    lines = content.split('\n')
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import_idx = i
    
    # Insert after last import
    if last_import_idx > 0:
        lines.insert(last_import_idx + 1, "from services.defensive_wiring import safe_write_text, safe_write_json")
        return '\n'.join(lines)
    return content

def migrate_file(filepath: Path, component: str, context_prefix: str) -> bool:
    """Migrate a single file to defensive wiring."""
    if not filepath.exists():
        return False
    
    content = filepath.read_text(encoding="utf-8")
    original = content
    
    # Pattern 1: path.write_text(json.dumps(...), encoding="utf-8")
    pattern1 = r'(\s+)(\w+)\.write_text\(json\.dumps\(([^,)]+)(?:,\s*indent=\d+)?\),\s*encoding="utf-8"\)'
    def replace1(m):
        indent, varname, data = m.groups()
        return (
            f'{indent}safe_write_json(\n'
            f'{indent}    {varname},\n'
            f'{indent}    {data},\n'
            f'{indent}    component="{component}",\n'
            f'{indent}    context="{context_prefix}"\n'
            f'{indent})'
        )
    content = re.sub(pattern1, replace1, content)
    
    # Pattern 2: path.write_text(content, encoding="utf-8")
    pattern2 = r'(\s+)(\w+)\.write_text\(([^,)]+),\s*encoding="utf-8"\)'
    def replace2(m):
        indent, varname, data = m.groups()
        return (
            f'{indent}safe_write_text(\n'
            f'{indent}    {varname},\n'
            f'{indent}    {data},\n'
            f'{indent}    component="{component}",\n'
            f'{indent}    context="{context_prefix}"\n'
            f'{indent})'
        )
    content = re.sub(pattern2, replace2, content)
    
    # Pattern 3: with open(..., "w") as f: json.dump(...)
    pattern3 = r'(\s+)with open\(([^,]+), "w"[^)]*\) as (\w+):\s*\n\s+json\.dump\(([^,)]+),'
    def replace3(m):
        indent, path_var, f_var, data = m.groups()
        return (
            f'{indent}safe_write_json(\n'
            f'{indent}    {path_var},\n'
            f'{indent}    {data},\n'
            f'{indent}    component="{component}",\n'
            f'{indent}    context="{context_prefix}"\n'
            f'{indent}) #'
        )
    content = re.sub(pattern3, replace3, content, flags=re.MULTILINE)
    
    if content != original:
        content = add_defensive_import(content)
        filepath.write_text(content, encoding="utf-8")
        return True
    return False

# All remaining files with their metadata
files_to_migrate: List[Tuple[str, str, str]] = [
    # Acquisition (5 remaining)
    ("services/acquisition/ideal_customer_profile.py", "acquisition_icp", "ICP record"),
    ("services/acquisition/outreach_safety.py", "acquisition_safety", "safety check"),
    ("services/acquisition/connectors/reddit/learning.py", "reddit_learning", "learning state"),
    ("services/acquisition/connectors/reddit/poster.py", "reddit_poster", "post state"),
    ("services/acquisition/social_intelligence/subreddit_culture.py", "subreddit_culture", "culture state"),
    
    # Alerts (4 files)
    ("services/alerts/digest.py", "alerts_digest", "digest generation"),
    ("services/alerts/dedupe.py", "alerts_dedupe", "deduplication"),
    ("services/alerts/throttling.py", "alerts_throttle", "throttle state"),
    ("services/alerts/paths.py", "alerts_paths", "path config"),
    
    # Compliance intelligence (4 files)
    ("services/compliance_intelligence/__init__.py", "compliance_intel", "snapshot"),
    ("services/compliance_intelligence/snapshots.py", "compliance_intel", "snapshot write"),
    ("services/compliance_intelligence/sources.py", "compliance_intel", "sources"),
    
    # Compliance health (2 files)
    ("services/compliance_health/assessment.py", "compliance_health", "assessment"),
    ("services/compliance_health/registry.py", "compliance_health", "registry"),
    
    # Evidence intelligence (2 files)
    ("services/evidence_intelligence/storage.py", "evidence_intel", "storage"),
    
    # Intake (4 files)
    ("services/intake/classification.py", "intake_classify", "classification"),
    ("services/intake/durable_root.py", "intake_durable", "durable root"),
    ("services/intake/evidence_registry.py", "intake_evidence", "evidence registry"),
    ("services/intake/learning_hooks.py", "intake_learning", "learning hooks"),
    
    # Knowledge cockpit (1 file)
    ("services/knowledge_cockpit/import_pipeline.py", "knowledge_import", "import"),
    
    # External verification (1 file)
    ("services/external_verification/storage.py", "external_verification", "verification storage"),
    
    # Root services (6 files)
    ("services/cognitive_topology.py", "cognitive_topology", "topology state"),
    ("services/customer_friction.py", "customer_friction", "friction log"),
    ("services/final_release_scan.py", "release_scan", "scan result"),
    ("services/project_deliverables.py", "deliverables", "deliverable generation"),
    ("services/durable_storage.py", "durable_storage", "storage probe"),
    ("services/alerts_center.py", "alerts_center", "alert generation"),
]

print("=== COMPREHENSIVE DEFENSIVE WIRING MIGRATION ===\n")
migrated = 0
skipped = 0

for filepath, component, context in files_to_migrate:
    path = Path(filepath)
    if migrate_file(path, component, context):
        print(f"OK: {filepath}")
        migrated += 1
    else:
        print(f"SKIP: {filepath}")
        skipped += 1

print(f"\n=== SUMMARY ===")
print(f"Migrated: {migrated}")
print(f"Skipped: {skipped}")
print(f"Total: {len(files_to_migrate)}")

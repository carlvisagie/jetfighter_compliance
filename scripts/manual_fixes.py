"""Manual fixes for the 10 remaining complex files."""
from pathlib import Path
import re

# Read each file, apply specific fix based on its pattern
fixes = []

# 1. ideal_customer_profile.py - complex json.dumps with .to_dict()
path = Path("services/acquisition/ideal_customer_profile.py")
content = path.read_text(encoding="utf-8")
old = 'path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")'
new = '''from services.defensive_wiring import safe_write_json
    safe_write_json(path, record.to_dict(), component="acquisition_icp", context="ICP record save")'''
if old in content:
    content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")
    fixes.append("ideal_customer_profile.py")

# 2-10: Add import and replace patterns for each
file_fixes = [
    ("services/acquisition/connectors/reddit/poster.py", "reddit_poster", "post state"),
    ("services/alerts/dedupe.py", "alerts_dedupe", "dedup state"),
    ("services/alerts/throttling.py", "alerts_throttle", "throttle state"),
    ("services/compliance_health/assessment.py", "compliance_health", "assessment result"),
    ("services/compliance_intelligence/snapshots.py", "compliance_intel", "snapshot"),
    ("services/external_verification/storage.py", "external_verification", "verification result"),
    ("services/intake/evidence_registry.py", "intake_evidence", "evidence registry"),
    ("services/customer_friction.py", "customer_friction", "friction log"),
    ("services/alerts_center.py", "alerts_center", "alert"),
]

for filepath, component, context in file_fixes:
    path = Path(filepath)
    if not path.exists():
        continue
        
    content = path.read_text(encoding="utf-8")
    
    # Add import if missing
    if "from services.defensive_wiring import" not in content and "from ..defensive_wiring import" not in content:
        # Find last import
        lines = content.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import = i
        if last_import > 0:
            lines.insert(last_import + 1, "from services.defensive_wiring import safe_write_text, safe_write_json, safe_append_jsonl")
            content = '\n'.join(lines)
    
    # Replace all write patterns
    # Pattern: path.write_text(json.dumps(...), ...)
    content = re.sub(
        r'(\w+)\.write_text\(json\.dumps\(([^)]+)\)(?:,\s*indent=\d+)?\s*,\s*encoding="utf-8"\)',
        rf'safe_write_json(\1, \2, component="{component}", context="{context}")',
        content
    )
    
    # Pattern: path.write_text(content, encoding="utf-8")
    content = re.sub(
        r'(\w+)\.write_text\(([^,]+),\s*encoding="utf-8"\)',
        rf'safe_write_text(\1, \2, component="{component}", context="{context}")',
        content
    )
    
    # Pattern: with open(..., "a") as f: f.write(json.dumps(...))
    content = re.sub(
        r'with open\(([^,]+),\s*"a"[^)]*\) as \w+:\s*\n\s+\w+\.write\(json\.dumps\(([^)]+)\)[^)]*\)',
        rf'safe_append_jsonl(\1, \2, component="{component}", context="{context}")',
        content,
        flags=re.MULTILINE
    )
    
    path.write_text(content, encoding="utf-8")
    fixes.append(filepath)

print(f"Fixed {len(fixes)} files:")
for f in fixes:
    print(f"  - {f}")

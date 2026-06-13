"""Filter to PRODUCTION service files only."""
import re
from pathlib import Path

def check_file(path):
    try:
        content = path.read_text(encoding='utf-8')
    except:
        return None
    
    # Count writes
    write_count = (
        len(re.findall(r'\.write_text\(', content)) +
        len(re.findall(r'open\([^)]+["\']w|open\([^)]+["\']a', content)) +
        len(re.findall(r'json\.dump\(', content))
    )
    
    if write_count == 0:
        return None
    
    # Check wiring
    has_telemetry = 'emit_telemetry' in content
    has_timeline = 'append_timeline' in content or 'link_entity' in content
    has_bridge = 'safe_write_after' in content
    
    return {
        'path': str(path),
        'writes': write_count,
        'wired': has_telemetry or has_timeline or has_bridge
    }

# ONLY check services/ directory (production code)
print("=== PRODUCTION SERVICES WRITE VERIFICATION ===\n")

results = []
for pyfile in Path('services').rglob('*.py'):
    result = check_file(pyfile)
    if result:
        results.append(result)

wired = [r for r in results if r['wired']]
silent = [r for r in results if not r['wired']]

print(f"Total service files with writes: {len(results)}")
print(f"Wired: {len(wired)}")
print(f"SILENT: {len(silent)}\n")

if silent:
    print("=== SILENT PRODUCTION SERVICES ===\n")
    for r in sorted(silent, key=lambda x: x['writes'], reverse=True):
        print(f"{r['path']:60} {r['writes']} writes")

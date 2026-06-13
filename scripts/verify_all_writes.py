"""Comprehensive wiring verification - check EVERY file write operation."""
import re
from pathlib import Path
from collections import defaultdict

def check_file(path):
    """Check a Python file for file writes and wiring."""
    try:
        content = path.read_text(encoding='utf-8')
    except:
        return None
    
    # Find all file write operations
    writes = []
    
    # Pattern 1: .write_text()
    for match in re.finditer(r'\.write_text\(', content):
        line_num = content[:match.start()].count('\n') + 1
        writes.append(('write_text', line_num))
    
    # Pattern 2: open(..., 'w') or open(..., 'a')
    for match in re.finditer(r'open\([^)]+["\']w|open\([^)]+["\']a', content):
        line_num = content[:match.start()].count('\n') + 1
        writes.append(('open_write', line_num))
    
    # Pattern 3: json.dump to file
    for match in re.finditer(r'json\.dump\(', content):
        line_num = content[:match.start()].count('\n') + 1
        writes.append(('json_dump', line_num))
    
    if not writes:
        return None
    
    # Check for wiring signals
    has_telemetry = 'emit_telemetry' in content
    has_timeline = 'append_timeline' in content or 'link_entity' in content
    has_organism_bridge = 'safe_write_after' in content or 'organism_integration' in content
    
    return {
        'path': str(path),
        'writes': writes,
        'has_telemetry': has_telemetry,
        'has_timeline': has_timeline,
        'has_organism_bridge': has_organism_bridge,
        'wired': has_telemetry or has_timeline or has_organism_bridge
    }

# Scan all Python files
results = []
for pyfile in Path('.').rglob('*.py'):
    if 'archive' in str(pyfile) or 'venv' in str(pyfile) or '.git' in str(pyfile):
        continue
    
    result = check_file(pyfile)
    if result:
        results.append(result)

# Categorize
wired = [r for r in results if r['wired']]
silent = [r for r in results if not r['wired']]

print(f"=== FILE WRITE VERIFICATION ===\n")
print(f"Total files with writes: {len(results)}")
print(f"Wired (has telemetry/timeline/bridge): {len(wired)}")
print(f"SILENT (no organism connection): {len(silent)}\n")

if silent:
    print(f"=== SILENT FILE WRITERS (RISK) ===\n")
    for r in silent[:30]:
        print(f"FILE: {r['path']}")
        print(f"  Writes: {len(r['writes'])} operations")
        print(f"  Lines: {[w[1] for w in r['writes'][:5]]}")
        print()

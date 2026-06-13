"""Verify defensive wiring coverage (recognizes new patterns)."""
import re
from pathlib import Path

def check_file(path):
    """Check if file has defensive wiring or raw writes."""
    try:
        content = path.read_text(encoding='utf-8')
    except:
        return None
    
    # Count OLD DANGEROUS writes
    old_writes = (
        len(re.findall(r'(?<!safe_)write_text\(', content)) +
        len(re.findall(r'open\([^)]+["\']w(?!ith safe_)', content)) +
        len(re.findall(r'json\.dump\((?!.*safe_)', content))
    )
    
    # Count NEW DEFENSIVE writes
    new_writes = (
        content.count('safe_write_text(') +
        content.count('safe_write_json(') +
        content.count('safe_append_jsonl(')
    )
    
    # Check for telemetry patterns
    has_telemetry = 'emit_telemetry' in content
    has_defensive = new_writes > 0 or 'defensive_wiring' in content
    
    if old_writes == 0 and new_writes == 0:
        return None  # No writes at all
    
    return {
        'path': str(path),
        'old_writes': old_writes,
        'new_writes': new_writes,
        'has_telemetry': has_telemetry,
        'has_defensive': has_defensive,
        'wired': (old_writes == 0 and new_writes > 0) or has_telemetry
    }

# Scan all Python files in services/
print("=== DEFENSIVE WIRING COVERAGE REPORT ===\n")

results = []
for pyfile in Path('services').rglob('*.py'):
    result = check_file(pyfile)
    if result:
        results.append(result)

wired = [r for r in results if r['wired']]
dangerous = [r for r in results if r['old_writes'] > 0 and not r['has_defensive']]

print(f"Total service files with writes: {len(results)}")
print(f"SAFE (defensive wiring or telemetry): {len(wired)} ({100*len(wired)//len(results) if results else 0}%)")
print(f"DANGEROUS (raw writes, no defense): {len(dangerous)} ({100*len(dangerous)//len(results) if results else 0}%)\n")

if dangerous:
    print("=== STILL DANGEROUS (NO DEFENSIVE WIRING) ===\n")
    for r in sorted(dangerous, key=lambda x: -x['old_writes'])[:20]:
        print(f"{r['path']:60} {r['old_writes']} raw writes")
    print()

print("=== DEFENSIVE WIRING SUMMARY ===")
print(f"Files with safe_write_text: {sum(1 for r in results if r['new_writes'] > 0)}")
print(f"Files with emit_telemetry: {sum(1 for r in results if r['has_telemetry'])}")
print(f"Files with defensive_wiring import: {sum(1 for r in results if r['has_defensive'])}")

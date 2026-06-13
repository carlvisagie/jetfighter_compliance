"""Check for common UI/JavaScript issues."""
import re
from pathlib import Path

ROOT = Path("E:/JetFighter_Compliance")
UI_DIR = ROOT / "ui"

print("=" * 80)
print("UI/JAVASCRIPT ISSUE SCAN")
print("=" * 80)

issues = []

# 1. Check for console.log() statements (shouldn't be in production)
print("\n[1] Checking for console.log statements...")
html_files = list(UI_DIR.glob("*.html"))
js_files = list((UI_DIR / "assets" / "js").glob("*.js"))

console_logs = []
for f in html_files + js_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r'console\.(log|error|warn)\(', content)
    if matches:
        console_logs.append((str(f.relative_to(ROOT)), len(matches)))

if console_logs:
    print(f"[WARN] Found console statements in {len(console_logs)} files:")
    for path, count in console_logs[:10]:
        print(f"  {path}: {count} statements")
    if len(console_logs) > 10:
        print(f"  ... and {len(console_logs) - 10} more files")
else:
    print("[OK] No console statements found")

# 2. Check for undefined variables
print("\n[2] Checking for common undefined variable patterns...")
undefined_patterns = [
    (r'window\.(\w+)\s*\&\&', "Optional chaining check"),
    (r'typeof\s+(\w+)\s*!==\s*["\']undefined', "Typeof check"),
]

# 3. Check for try-catch blocks without error handling
print("\n[3] Checking for empty catch blocks...")
empty_catches = []
for f in html_files + js_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    # Look for catch blocks with only comments or whitespace
    matches = re.findall(r'catch\s*\([^)]*\)\s*\{[\s]*(?://[^\n]*)?\s*\}', content)
    if matches:
        empty_catches.append((str(f.relative_to(ROOT)), len(matches)))

if empty_catches:
    print(f"[WARN] Found {len(empty_catches)} files with empty catch blocks:")
    for path, count in empty_catches[:10]:
        print(f"  {path}: {count} empty catches")
else:
    print("[OK] No problematic catch blocks found")

# 4. Check for hardcoded URLs (should use relative paths)
print("\n[4] Checking for hardcoded URLs...")
hardcoded_urls = []
for f in html_files + js_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r'https?://(?!compliance\.keepyourcontracts\.com)[\w\-\.]+', content)
    if matches:
        unique = set(matches)
        if unique:
            hardcoded_urls.append((str(f.relative_to(ROOT)), list(unique)))

if hardcoded_urls:
    print(f"[WARN] Found hardcoded URLs in {len(hardcoded_urls)} files:")
    for path, urls in hardcoded_urls[:5]:
        print(f"  {path}: {urls[:3]}")
else:
    print("[OK] No problematic hardcoded URLs found")

# 5. Check for missing error messages in UI
print("\n[5] Checking for 'unavailable' messages without user guidance...")
unavailable_msgs = []
for f in html_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    # Look for "unavailable" messages
    if 'unavailable' in content.lower():
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'unavailable' in line.lower():
                # Check if there's helpful guidance nearby
                context = '\n'.join(lines[max(0, i-3):min(len(lines), i+3)])
                if 'contact' not in context.lower() and 'try' not in context.lower() and 'refresh' not in context.lower():
                    unavailable_msgs.append((str(f.relative_to(ROOT)), i, line.strip()[:80]))

if unavailable_msgs:
    print(f"[WARN] Found {len(unavailable_msgs)} 'unavailable' messages without user guidance:")
    for path, line_num, snippet in unavailable_msgs[:10]:
        print(f"  {path}:{line_num}")
        print(f"    {snippet}")
else:
    print("[OK] All unavailable messages have user guidance")

# 6. Check for fetch() without timeout
print("\n[6] Checking for fetch() calls without timeout...")
fetch_no_timeout = []
for f in html_files + js_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if 'fetch(' in line:
            # Check next 5 lines for timeout/signal
            context = '\n'.join(lines[i:min(len(lines), i+5)])
            if 'signal' not in context and 'timeout' not in context.lower():
                fetch_no_timeout.append((str(f.relative_to(ROOT)), i))

if fetch_no_timeout:
    print(f"[WARN] Found {len(fetch_no_timeout)} fetch calls without timeout:")
    for path, line_num in fetch_no_timeout[:10]:
        print(f"  {path}:{line_num}")
    if len(fetch_no_timeout) > 10:
        print(f"  ... and {len(fetch_no_timeout) - 10} more")
else:
    print("[OK] All fetch calls have timeout handling")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_issues = (
    len(console_logs) +
    len(empty_catches) +
    len(hardcoded_urls) +
    len(unavailable_msgs) +
    len(fetch_no_timeout)
)

print(f"\nTotal potential issues: {total_issues}")
print(f"  Console statements: {len(console_logs)}")
print(f"  Empty catch blocks: {len(empty_catches)}")
print(f"  Hardcoded URLs: {len(hardcoded_urls)}")
print(f"  Unavailable messages without guidance: {len(unavailable_msgs)}")
print(f"  Fetch calls without timeout: {len(fetch_no_timeout)}")

if total_issues > 0:
    print("\n[ACTION] Review and fix the issues listed above")
else:
    print("\n[SUCCESS] No major UI issues found")

print("\n" + "=" * 80)

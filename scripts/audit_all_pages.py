"""COMPREHENSIVE UI PAGE AUDIT - Find ALL issues across ALL pages."""
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

UI_DIR = Path("E:/JetFighter_Compliance/ui")
SERVER_FILE = Path("E:/JetFighter_Compliance/server.py")

print("=" * 80)
print("COMPREHENSIVE UI PAGE AUDIT - ALL PAGES")
print("=" * 80)

# Get all HTML files
html_files = list(UI_DIR.rglob("*.html"))
print(f"\n[INFO] Found {len(html_files)} HTML pages to audit\n")

# Load server endpoints
server_content = SERVER_FILE.read_text(encoding="utf-8")
server_endpoints = set()
endpoint_def_pattern = re.compile(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']')
for match in endpoint_def_pattern.finditer(server_content):
    endpoint = match.group(2)
    normalized = re.sub(r'\{[^}]+\}', '*', endpoint)
    server_endpoints.add((endpoint, normalized))

print("[1] SERVER ENDPOINT MAP LOADED")
print(f"    {len(server_endpoints)} endpoints defined\n")

# Audit patterns
api_pattern = re.compile(r'["\'](/api/[^"\'?\s]+)')
script_pattern = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']')
css_pattern = re.compile(r'<link[^>]+href=["\']([^"\']+\.css)["\']')

issues = defaultdict(list)
pages_checked = 0

for html_file in sorted(html_files):
    rel_path = str(html_file.relative_to(UI_DIR))
    pages_checked += 1
    
    try:
        content = html_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        issues[rel_path].append(f"ERROR: Cannot read file - {e}")
        continue
    
    # Check API endpoints
    for match in api_pattern.finditer(content):
        endpoint = match.group(1)
        if "{" in endpoint:
            continue  # Skip template variables
        
        # Check if endpoint exists
        exact_match = any(ep == endpoint for ep, _ in server_endpoints)
        wildcard_match = any(
            endpoint.startswith(norm.replace('*', ''))
            for ep, norm in server_endpoints
            if '*' in norm
        )
        
        if not exact_match and not wildcard_match:
            issues[rel_path].append(f"MISSING API: {endpoint}")
    
    # Check JavaScript files
    for match in script_pattern.finditer(content):
        src = match.group(1)
        if src.startswith('http'):
            continue  # External
        
        # Normalize path
        if src.startswith('/ui/'):
            js_path = UI_DIR / src[4:]
        elif src.startswith('/'):
            js_path = Path("E:/JetFighter_Compliance") / src[1:]
        else:
            js_path = html_file.parent / src
        
        if not js_path.is_file():
            issues[rel_path].append(f"MISSING JS: {src}")
    
    # Check CSS files
    for match in css_pattern.finditer(content):
        href = match.group(1)
        if href.startswith('http'):
            continue  # External
        
        # Normalize path
        if href.startswith('/ui/'):
            css_path = UI_DIR / href[4:]
        elif href.startswith('/'):
            css_path = Path("E:/JetFighter_Compliance") / href[1:]
        else:
            css_path = html_file.parent / href
        
        if not css_path.is_file():
            issues[rel_path].append(f"MISSING CSS: {href}")
    
    # Check for common UI errors
    if 'OperatorCockpit' in content and 'operator-cockpit.js' not in content:
        issues[rel_path].append(f"MISSING: operator-cockpit.js dependency")
    
    # Check for fetch() calls without error handling
    fetch_calls = re.findall(r'fetch\([^)]+\)(?!\s*\.then|\s*\.catch)', content)
    if fetch_calls and len(fetch_calls) > 2:
        issues[rel_path].append(f"WARNING: {len(fetch_calls)} fetch() calls without error handling")

print("=" * 80)
print("[2] PAGE AUDIT RESULTS")
print("=" * 80)

clean_pages = []
broken_pages = []

for page in sorted(html_files):
    rel_path = str(page.relative_to(UI_DIR))
    page_issues = issues.get(rel_path, [])
    
    if page_issues:
        broken_pages.append((rel_path, page_issues))
    else:
        clean_pages.append(rel_path)

print(f"\n[CLEAN] {len(clean_pages)} pages with no issues")
print(f"[BROKEN] {len(broken_pages)} pages with issues\n")

if broken_pages:
    print("=" * 80)
    print("BROKEN PAGES - ISSUES FOUND")
    print("=" * 80)
    
    for page, page_issues in broken_pages:
        print(f"\n{page}")
        print(f"  Issues: {len(page_issues)}")
        for issue in page_issues[:10]:  # Show first 10 issues per page
            print(f"  - {issue}")
        if len(page_issues) > 10:
            print(f"  ... and {len(page_issues) - 10} more issues")

print("\n" + "=" * 80)
print("AUDIT SUMMARY")
print("=" * 80)
print(f"\nPages checked: {pages_checked}")
print(f"Clean pages: {len(clean_pages)}")
print(f"Broken pages: {len(broken_pages)}")
print(f"Total issues: {sum(len(issues) for issues in issues.values())}")

if broken_pages:
    print("\n[ACTION REQUIRED] Fix the broken pages listed above.")
else:
    print("\n[SUCCESS] All pages are clean!")

print("\n" + "=" * 80)

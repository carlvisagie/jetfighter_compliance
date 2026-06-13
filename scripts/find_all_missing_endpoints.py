"""COMPREHENSIVE ENDPOINT AUDIT - Find ALL missing API endpoints."""
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

# Scan all UI files for API endpoint calls
UI_DIR = Path("E:/JetFighter_Compliance/ui")
SERVER_FILE = Path("E:/JetFighter_Compliance/server.py")

print("=" * 80)
print("COMPREHENSIVE ENDPOINT AUDIT")
print("=" * 80)

# Step 1: Find all API endpoints called in UI
print("\n[1] Scanning UI files for API endpoint calls...\n")

api_calls = defaultdict(list)
api_pattern = re.compile(r'["\'](/api/[^"\'?\s]+)')

for ui_file in UI_DIR.rglob("*.html"):
    content = ui_file.read_text(encoding="utf-8", errors="ignore")
    for match in api_pattern.finditer(content):
        endpoint = match.group(1)
        # Skip dynamic endpoints with {variables}
        if "{" not in endpoint:
            api_calls[endpoint].append(str(ui_file.relative_to(UI_DIR)))

for ui_file in UI_DIR.rglob("*.js"):
    content = ui_file.read_text(encoding="utf-8", errors="ignore")
    for match in api_pattern.finditer(content):
        endpoint = match.group(1)
        # Skip dynamic endpoints with {variables}
        if "{" not in endpoint:
            api_calls[endpoint].append(str(ui_file.relative_to(UI_DIR)))

print(f"Found {len(api_calls)} unique API endpoints called in UI\n")

# Step 2: Find all API endpoints defined in server.py
print("[2] Scanning server.py for endpoint definitions...\n")

server_content = SERVER_FILE.read_text(encoding="utf-8")
server_endpoints = set()

# Match @app.get("/api/...") and @app.post("/api/...")
endpoint_def_pattern = re.compile(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']')
for match in endpoint_def_pattern.finditer(server_content):
    endpoint = match.group(2)
    # Normalize dynamic path params like {project_id} to appear as wildcards
    normalized = re.sub(r'\{[^}]+\}', '*', endpoint)
    server_endpoints.add((endpoint, normalized))

print(f"Found {len(server_endpoints)} endpoint definitions in server.py\n")

# Step 3: Find missing endpoints
print("=" * 80)
print("[3] ANALYZING MISMATCHES")
print("=" * 80)

missing = []
found = []

for called_endpoint in sorted(api_calls.keys()):
    # Check exact match
    exact_match = any(endpoint == called_endpoint for endpoint, _ in server_endpoints)
    
    # Check wildcard match for dynamic params
    wildcard_match = any(
        called_endpoint.startswith(normalized.replace('*', ''))
        for endpoint, normalized in server_endpoints
        if '*' in normalized
    )
    
    if exact_match or wildcard_match:
        found.append(called_endpoint)
    else:
        missing.append((called_endpoint, api_calls[called_endpoint]))

# Report
print(f"\n[OK] {len(found)} endpoints exist in server.py")
print(f"[MISSING] {len(missing)} endpoints NOT FOUND in server.py")

if missing:
    print("\n" + "=" * 80)
    print("MISSING ENDPOINTS - REQUIRE IMMEDIATE ATTENTION")
    print("=" * 80)
    
    for endpoint, files in missing:
        print(f"\nMISSING: {endpoint}")
        unique_files = list(set(files))
        print(f"  Called in: {', '.join(unique_files[:3])}")
        if len(files) > 3:
            print(f"  ... and {len(files) - 3} more files")

print("\n" + "=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)
print(f"\nTotal API calls scanned: {sum(len(v) for v in api_calls.values())}")
print(f"Unique endpoints called: {len(api_calls)}")
print(f"Endpoints defined in server.py: {len(server_endpoints)}")
print(f"Missing endpoints: {len(missing)}")

if missing:
    print("\n[ACTION REQUIRED] Create the missing endpoints listed above.")
else:
    print("\n[SUCCESS] All UI-called endpoints exist in server.py!")
